"""
@file: diagtools/value_check.py
@description: CLI utility to validate odds provider snapshots and basic value metrics.
@dependencies: asyncio, config, app.value_service
@created: 2025-09-24
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.bot.services import PredictionFacade
from app.lines.aggregator import AggregatingLinesProvider, LinesAggregator, parse_provider_weights
from app.lines.mapper import LinesMapper
from app.lines.providers import CSVLinesProvider, HTTPLinesProvider
from app.lines.providers.base import LinesProvider
from app.lines.storage import OddsSQLiteStore
from app.metrics import (
    value_backtest_last_run_ts,
    value_backtest_samples,
    value_backtest_sharpe,
    value_calibrated_pairs_total,
)
from app.value_calibration import (
    BacktestConfig,
    BacktestRunner,
    BacktestSample,
    CalibrationRecord,
    CalibrationService,
)
from app.value_detector import ValueDetector
from app.value_service import ValueService
from config import settings

_CLI_ARGS: argparse.Namespace | None = None


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Value detector sanity check")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Force calibration backtest even when no odds are fetched",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Limit calibration samples to the latest N days",
    )
    args, _ = parser.parse_known_args(argv)
    return args


@dataclass(slots=True)
class _DummyProvider:
    mapper: LinesMapper

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[Any]:  # pragma: no cover - fallback path
        return []


def _parse_markets() -> tuple[str, ...]:
    raw = getattr(settings, "VALUE_MARKETS", "1X2,OU_2_5,BTTS")
    return tuple(item.strip() for item in str(raw).split(",") if item.strip())


def _build_detector() -> ValueDetector:
    return ValueDetector(
        min_edge_pct=float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0)),
        min_confidence=float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6)),
        max_picks=int(getattr(settings, "VALUE_MAX_PICKS", 5)),
        markets=_parse_markets(),
        overround_method=str(getattr(settings, "ODDS_OVERROUND_METHOD", "proportional")),
    )


def _create_provider(mapper: LinesMapper) -> LinesProvider:
    provider_names = _resolve_provider_names()
    providers: dict[str, LinesProvider] = {}
    for name in provider_names:
        providers[name] = _instantiate_provider(name, mapper)
    active = {
        name: provider
        for name, provider in providers.items()
        if not isinstance(provider, _DummyProvider)
    }
    if not active:
        return next(iter(providers.values()), _DummyProvider(mapper))
    weights = parse_provider_weights(getattr(settings, "ODDS_PROVIDER_WEIGHTS", None))
    aggregator = LinesAggregator(
        method=str(getattr(settings, "ODDS_AGG_METHOD", "median")),
        provider_weights=weights,
        store=OddsSQLiteStore(),
        retention_days=int(getattr(settings, "ODDS_SNAPSHOT_RETENTION_DAYS", 14)),
        movement_window_minutes=int(getattr(settings, "CLV_WINDOW_BEFORE_KICKOFF_MIN", 120)),
    )
    return AggregatingLinesProvider(active, aggregator=aggregator)


def _resolve_provider_names() -> list[str]:
    raw = str(getattr(settings, "ODDS_PROVIDERS", "") or "").strip()
    names = [token.strip().lower() for token in raw.split(",") if token.strip()]
    if not names:
        fallback = str(getattr(settings, "ODDS_PROVIDER", "dummy") or "dummy")
        names = [fallback.lower()]
    return names


def _instantiate_provider(name: str, mapper: LinesMapper) -> LinesProvider:
    if name == "csv":
        fixtures_root = os.getenv("ODDS_FIXTURES_PATH")
        if fixtures_root:
            path = Path(fixtures_root)
        else:
            base = getattr(settings, "DATA_ROOT", "/data")
            path = Path(base) / "odds"
        return CSVLinesProvider(fixtures_dir=path, mapper=mapper)
    if name == "http":
        base_url = os.getenv("ODDS_HTTP_BASE_URL", "").strip()
        if not base_url:
            raise RuntimeError("ODDS_HTTP_BASE_URL не задан")
        return HTTPLinesProvider(
            base_url=base_url,
            token=getattr(settings, "ODDS_API_KEY", "") or None,
            timeout=float(getattr(settings, "ODDS_TIMEOUT_SEC", 8.0)),
            retry_attempts=int(getattr(settings, "ODDS_RETRY_ATTEMPTS", 4)),
            backoff_base=float(getattr(settings, "ODDS_BACKOFF_BASE", 0.4)),
            rps_limit=float(getattr(settings, "ODDS_RPS_LIMIT", 3.0)),
            mapper=mapper,
        )
    return _DummyProvider(mapper)


async def _run_check_async() -> dict[str, Any]:
    mapper = LinesMapper()
    provider = _create_provider(mapper)
    detector = _build_detector()
    facade = PredictionFacade()
    service = ValueService(facade=facade, provider=provider, detector=detector, mapper=mapper)
    target_date = date.today()
    meta: dict[str, dict[str, object]] = {}
    predictions = await facade.today(target_date)
    outcomes = list(service._build_model_outcomes(predictions, meta))
    date_from = datetime.combine(target_date, time.min, tzinfo=UTC)
    date_to = datetime.combine(target_date, time.max, tzinfo=UTC)
    odds = await provider.fetch_odds(date_from=date_from, date_to=date_to)
    picks = detector.detect(model=outcomes, market=odds)
    edges = [float(p.edge_pct) for p in picks]
    invalid_prices = [snap.price_decimal for snap in odds if getattr(snap, "price_decimal", 0.0) <= 1.0]
    cards = [
        {
            "match": meta.get(pick.match_key, {}),
            "market": pick.market,
            "selection": pick.selection,
            "edge_pct": pick.edge_pct,
            "provider": pick.provider,
        }
        for pick in picks
    ]
    force_calibration = bool(_CLI_ARGS and getattr(_CLI_ARGS, "calibrate", False))
    days = _resolve_days_override(_CLI_ARGS, force_calibration)
    summary_backtest = _load_cached_backtest_report()
    if force_calibration:
        summary_backtest = run_backtest_calibration(days=days)
    elif summary_backtest.get("reason") == "no_cached_report":
        summary_backtest = {"records": [], "status": "SKIP", "reason": "calibration_skipped"}
    summary_backtest["source"] = "calibrated" if force_calibration else "cached"
    close_fn = getattr(provider, "close", None)
    if close_fn:
        result = close_fn()
        if asyncio.iscoroutine(result):
            await result
    aggregation = {}
    if isinstance(provider, AggregatingLinesProvider):
        meta = provider.aggregator.last_metadata
        avg_count = (
            sum(item.provider_count for item in meta.values()) / len(meta)
            if meta
            else 0.0
        )
        aggregation = {"pairs": len(meta), "avg_provider_count": avg_count}
    return {
        "predictions": len(predictions),
        "odds_count": len(odds),
        "picks": len(picks),
        "edges": edges,
        "invalid_prices": invalid_prices,
        "cards": cards[:5],
        "backtest": summary_backtest,
        "aggregation": aggregation,
    }


def _resolve_days_override(args: argparse.Namespace | None, force: bool) -> int | None:
    if args and args.days:
        return int(args.days)
    if force:
        return _settings_backtest_days()
    return None


def run_backtest_calibration(*, days: int | None = None) -> dict[str, Any]:
    samples = _load_backtest_samples()
    if days:
        boundary = datetime.now(UTC) - timedelta(days=abs(int(days)))
        samples = [sample for sample in samples if sample.pulled_at >= boundary]
    if not samples:
        return {"records": [], "status": "WARN", "reason": "no_samples"}
    config = _build_backtest_config(samples)
    runner = BacktestRunner(samples)
    results = runner.calibrate(config)
    timestamp = datetime.now(UTC)
    value_backtest_last_run_ts.set(timestamp.timestamp())
    value_calibrated_pairs_total.set(len(results))
    service = CalibrationService(
        default_edge_pct=float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0)),
        default_confidence=float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6)),
    )
    records: list[dict[str, Any]] = []
    to_store: list[CalibrationRecord] = []
    status = "WARN" if not results else "OK"
    for item in results:
        record_status = _status_for_record(item, config)
        status = _max_status(status, record_status)
        value_backtest_sharpe.labels(item.league, item.market).set(item.metrics.sharpe)
        value_backtest_samples.labels(item.league, item.market).set(item.metrics.samples)
        to_store.append(
            CalibrationRecord(
                league=item.league,
                market=item.market,
                tau_edge=item.tau_edge,
                gamma_conf=item.gamma_conf,
                samples=item.metrics.samples,
                metric=item.metric,
                updated_at=timestamp,
            )
        )
        records.append(
            {
                "league": item.league,
                "market": item.market,
                "tau_edge": item.tau_edge,
                "gamma_conf": item.gamma_conf,
                "samples": item.metrics.samples,
                "sharpe": item.metrics.sharpe,
                "log_gain": item.metrics.avg_log_gain,
                "status": record_status,
            }
        )
    if to_store:
        service.bulk_upsert(to_store)
    report = {"records": records, "status": status, "source": "calibrated"}
    _write_backtest_report(report)
    return report


def _settings_backtest_days() -> int | None:
    try:
        raw = getattr(settings, "BACKTEST_DAYS", None)
    except Exception:  # pragma: no cover - defensive guard
        return None
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return max(value, 1)


def _load_cached_backtest_report() -> dict[str, Any]:
    diag_root = Path(getattr(settings, "REPORTS_DIR", "/data/reports")) / "diagnostics"
    json_path = diag_root / "value_calibration.json"
    if not json_path.exists():
        return {"records": [], "status": "SKIP", "reason": "no_cached_report"}
    try:
        with json_path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"records": [], "status": "WARN", "reason": "no_cached_report"}
    if not isinstance(payload, dict):
        return {"records": [], "status": "SKIP", "reason": "no_cached_report"}
    payload.setdefault("status", "WARN")
    payload.setdefault("records", [])
    return payload


def _load_backtest_samples() -> list[BacktestSample]:
    samples: list[BacktestSample] = []
    for path in _backtest_candidate_paths():
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    samples.append(
                        BacktestSample(
                            pulled_at=datetime.fromisoformat(str(row["pulled_at"])),
                            kickoff_utc=datetime.fromisoformat(str(row["kickoff_utc"])),
                            league=str(row["league"]),
                            market=str(row["market"]),
                            selection=str(row["selection"]),
                            match_key=str(row["match_key"]),
                            price_decimal=float(row["price_decimal"]),
                            edge_pct=float(row["edge_pct"]),
                            confidence=float(row["confidence"]),
                            result=int(row["result"]),
                        )
                    )
                except (KeyError, ValueError):
                    continue
        if samples:
            break
    return samples


def _backtest_candidate_paths() -> Sequence[Path]:
    data_root = Path(getattr(settings, "DATA_ROOT", "/data"))
    repo_root = Path(__file__).resolve().parents[1]
    return (
        data_root / "value_backtest.csv",
        data_root / "value_backtest" / "samples.csv",
        repo_root / "tests" / "fixtures" / "value_backtest" / "samples_basic.csv",
    )


def _build_backtest_config(samples: Sequence[BacktestSample]) -> BacktestConfig:
    edge_grid = sorted({round(max(sample.edge_pct, float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0))), 1) for sample in samples})
    conf_grid = sorted({round(max(sample.confidence, float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6))), 2) for sample in samples})
    if not edge_grid:
        edge_grid = [float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0))]
    if not conf_grid:
        conf_grid = [float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6))]
    validation = str(getattr(settings, "BACKTEST_VALIDATION", "time_kfold"))
    walk_step = max(len(samples) // 4, 1) if validation == "walk_forward" else None
    min_samples = min(len(samples), int(getattr(settings, "BACKTEST_MIN_SAMPLES", 300)))
    return BacktestConfig(
        min_samples=max(min_samples, 1),
        validation=validation,
        optim_target=str(getattr(settings, "BACKTEST_OPTIM_TARGET", "sharpe")),
        edge_grid=edge_grid,
        confidence_grid=conf_grid,
        folds=4,
        walk_step=walk_step,
    )


def _status_for_record(result: Any, config: BacktestConfig) -> str:
    min_samples = int(getattr(settings, "BACKTEST_MIN_SAMPLES", 300))
    warn = float(getattr(settings, "GATES_VALUE_SHARPE_WARN", 0.1))
    fail = float(getattr(settings, "GATES_VALUE_SHARPE_FAIL", 0.0))
    if result.metrics.samples < min_samples or result.metrics.sharpe < fail:
        return "FAIL"
    if result.metrics.sharpe < warn:
        return "WARN"
    return "OK"


def _max_status(current: str, new: str) -> str:
    order = {"OK": 0, "WARN": 1, "FAIL": 2}
    return new if order.get(new, 0) > order.get(current, 0) else current


def _write_backtest_report(report: dict[str, Any]) -> None:
    if not report:
        return
    diag_root = Path(getattr(settings, "REPORTS_DIR", "/data/reports")) / "diagnostics"
    diag_root.mkdir(parents=True, exist_ok=True)
    json_path = diag_root / "value_calibration.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    md_lines = ["# Value Calibration", ""]
    for record in report.get("records", []):
        md_lines.append(
            f"- {record['league']} {record['market']}: τ={record['tau_edge']:.1f}% γ={record['gamma_conf']:.2f} "
            f"samples={record['samples']} sharpe={record['sharpe']:.3f} status={record['status']}"
        )
    if not report.get("records"):
        md_lines.append(f"Нет данных: {report.get('reason', '—')}")
    md_path = diag_root / "value_calibration.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")


def main() -> None:
    global _CLI_ARGS
    if _CLI_ARGS is None:
        _CLI_ARGS = _parse_args()
    exit_code = 0
    try:
        summary = asyncio.run(_run_check_async())
    except Exception as exc:  # pragma: no cover - unexpected runtime failure
        print(f"value_check failed: {exc}")
        raise SystemExit(2) from exc
    print("Value & Odds summary:")
    for key in ("predictions", "odds_count", "picks"):
        print(f"  {key}: {summary.get(key)}")
    if summary.get("edges"):
        edges = summary["edges"]
        print(f"  edge_max: {max(edges):.2f}% edge_mean: {sum(edges)/len(edges):.2f}%")
    if summary.get("cards"):
        print("  top picks:")
        for card in summary["cards"]:
            match = card.get("match", {})
            title = f"{match.get('home', '?')} vs {match.get('away', '?')}"
            print(
                f"    {title} • {card['market']} {card['selection']} edge={card['edge_pct']:.1f}% provider={card['provider']}"
            )
    if summary.get("invalid_prices") or summary.get("odds_count", 0) == 0:
        print("Provider validation failed: no odds or invalid prices detected")
        exit_code = max(exit_code, 1)
    backtest = summary.get("backtest") or {}
    records = backtest.get("records", [])
    status_flag = backtest.get("status")
    source = backtest.get("source")
    print("Backtest & Calibration:")
    if records:
        for record in records:
            print(
                "  "
                + f"{record['league']} {record['market']} τ={record['tau_edge']:.1f}% γ={record['gamma_conf']:.2f}"
                + f" samples={record['samples']} sharpe={record['sharpe']:.3f} status={record['status']}"
            )
            if record["status"] == "FAIL" and source == "calibrated":
                exit_code = max(exit_code, 2)
            elif record["status"] == "WARN" and source == "calibrated":
                exit_code = max(exit_code, 1)
    else:
        reason = backtest.get("reason", "no data")
        print(f"  нет данных ({reason})")
        if status_flag == "FAIL":
            exit_code = max(exit_code, 2)
        elif status_flag in {"WARN"} and source == "calibrated":
            exit_code = max(exit_code, 1)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
