"""
/**
 * @file: diagtools/run_diagnostics.py
 * @description: End-to-end diagnostics harness for Telegram bot, ML models and ops glue.
 * @dependencies: argparse, asyncio, json, math, os, pathlib, statistics, subprocess, textwrap,
 *                 pandas, numpy, matplotlib, seaborn, sklearn
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from types import ModuleType

if TYPE_CHECKING:  # pragma: no cover - for static typing only
    import numpy as np  # type: ignore
    import pandas as pd  # type: ignore
else:
    class _LazyModule:
        def __init__(self, module_name: str) -> None:
            self._module_name = module_name
            self._module: ModuleType | None = None

        def _load(self) -> ModuleType:
            if self._module is None:
                self._module = importlib.import_module(self._module_name)
            return self._module

        def __getattr__(self, item: str) -> Any:  # pragma: no cover - trivial proxy
            return getattr(self._load(), item)

        def __dir__(self) -> list[str]:  # pragma: no cover - trivial proxy
            return dir(self._load())

    np = _LazyModule("numpy")
    pd = _LazyModule("pandas")

try:
    from matplotlib import pyplot as plt
    from matplotlib.ticker import PercentFormatter

    HAS_MPL = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency in CI
    plt = None  # type: ignore[assignment]
    PercentFormatter = None  # type: ignore[assignment]
    HAS_MPL = False

from sklearn.calibration import calibration_curve
from sklearn.linear_model import Ridge
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from app.bot.services import PredictionFacade
from app.data_quality import run_quality_suite
from app.diagnostics import (
    bipoisson_swap_check,
    monte_carlo_coverage,
    reliability_table,
    scoreline_symmetry,
)
try:  # pragma: no cover - reliability_v2 может отсутствовать в оффлайн-сборках
    from app.lines import reliability_v2  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - диагностический fallback
    class _ReliabilityV2Stub:
        @staticmethod
        def get_provider_scores(*_args, **_kwargs) -> list[dict[str, object]]:
            return []

        @staticmethod
        def explain_components(*_args, **_kwargs) -> dict[str, object]:
            return {}

    reliability_v2 = _ReliabilityV2Stub()
from app.lines.aggregator import AggregatingLinesProvider, LinesAggregator, parse_provider_weights
from app.lines.anomaly import OddsAnomalyDetector
from app.lines.reliability import ProviderReliabilityTracker
from app.lines.reliability_v2 import ProviderReliabilityV2, get_tracker as get_reliab_tracker
from app.lines.storage import OddsSQLiteStore
from app.lines.mapper import LinesMapper
from app.lines.providers import CSVLinesProvider, HTTPLinesProvider
from app.lines.providers.base import LinesProvider
from app.value_detector import ValueDetector
from app.value_service import ValueService
from diagtools import bench as bench_module
from diagtools import drift as drift_module
from diagtools import golden_regression as golden_module
from diagtools import reports_html
from diagtools import settlement_check as settlement_module
from diagtools.freshness import evaluate_sportmonks_freshness
from diagtools.value_check import run_backtest_calibration
from metrics.metrics import record_diagnostics_summary

# Ленивая загрузка heavy-модулей проекта, чтобы избежать побочных эффектов до настройки окружения.


@contextmanager
def _temp_env(overrides: dict[str, str] | None = None) -> Iterable[None]:
    env = os.environ.copy()
    overrides = overrides or {}
    try:
        os.environ.update(overrides)
        yield
    finally:
        # Удаляем ключи, которых не было ранее
        for key in overrides:
            if key in env:
                os.environ[key] = env[key]
            else:
                os.environ.pop(key, None)


def _load_settings() -> Any:
    from config import settings

    return settings


def _resolve_reports_dir(settings: Any, override: str | None = None) -> Path:
    base = Path(override or settings.REPORTS_DIR)
    base.mkdir(parents=True, exist_ok=True)
    diag_dir = base / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    return diag_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run diagnostics suite and persist artifacts")
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=None,
        help="Override reports directory (defaults to settings.REPORTS_DIR)",
    )
    parser.add_argument(
        "--pytest",
        action="store_true",
        help="Re-run pytest even if diagnostics already invoked inside CI",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip smoke run (useful when running inside constrained CI job)",
    )
    parser.add_argument(
        "--data-quality",
        action="store_true",
        help="Run only data quality checks and exit",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Force running the entire diagnostics suite even when --data-quality is set",
    )
    return parser.parse_args()


def _collect_entry_flags() -> dict[str, Any]:
    import inspect

    import main as main_module

    source = inspect.getsource(main_module.parse_args)
    flags = sorted(set(re.findall(r"\"--([\w-]+)\"", source)))
    return {
        "entry_point": "python -m main",
        "script": str(Path(main_module.__file__).resolve()),
        "flags": flags,
    }


def _collect_env_contract(root: Path) -> dict[str, Any]:
    env_example = root / ".env.example"
    example_keys: set[str] = set()
    for line in env_example.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" in raw:
            key = raw.split("=", 1)[0].strip()
            if key:
                example_keys.add(key)

    import ast

    getenv_keys: set[str] = set()
    for py_path in root.rglob("*.py"):
        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "os" and func.attr in {"getenv"}:
                        if node.args and isinstance(node.args[0], ast.Constant):
                            getenv_keys.add(str(node.args[0].value))
                    if func.value.id == "os" and func.attr == "environ":
                        # Handle os.environ.get(...) pattern
                        if node.attr == "get" and node.args and isinstance(node.args[0], ast.Constant):
                            getenv_keys.add(str(node.args[0].value))
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Call):
                    # например Path(os.getenv("FOO"))
                    inner = func.value
                    if (
                        isinstance(inner.func, ast.Attribute)
                        and isinstance(inner.func.value, ast.Name)
                        and inner.func.value.id == "os"
                        and inner.func.attr == "getenv"
                        and inner.args
                        and isinstance(inner.args[0], ast.Constant)
                    ):
                        getenv_keys.add(str(inner.args[0].value))

    from config import Settings

    settings_fields = set(Settings.model_fields.keys())
    return {
        "example_keys": sorted(example_keys),
        "getenv_keys": sorted(getenv_keys),
        "settings_fields": sorted(settings_fields),
        "missing_in_example": sorted(getenv_keys - example_keys),
        "extra_in_example": sorted(example_keys - (getenv_keys | settings_fields)),
        "settings_only": sorted(settings_fields - example_keys),
    }


def _ensure_paths(settings: Any) -> list[str]:
    paths = [
        ("DB_PATH", Path(settings.DB_PATH).resolve()),
        ("REPORTS_DIR", Path(settings.REPORTS_DIR).resolve()),
        ("MODEL_REGISTRY_PATH", Path(settings.MODEL_REGISTRY_PATH).resolve()),
        ("LOG_DIR", Path(settings.LOG_DIR).resolve()),
        ("BACKUP_DIR", Path(settings.BACKUP_DIR).resolve()),
        ("RUNTIME_LOCK_PATH", Path(settings.RUNTIME_LOCK_PATH).resolve()),
    ]
    notes: list[str] = []
    for label, path in paths:
        target = path if path.is_dir() else path.parent
        target.mkdir(parents=True, exist_ok=True)
        notes.append(f"{label} -> {path}")
    return notes


def _run_subprocess(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    log_path: Path | None = None,
    timeout: int | None = None,
) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if log_path:
        log_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    return result.returncode, result.stdout, result.stderr


def _run_pytest(diag_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    log_path = diag_dir / "pytest.log"
    code, stdout, stderr = _run_subprocess([sys.executable, "-m", "pytest", "-q"], env=env, log_path=log_path)
    return {
        "returncode": code,
        "stdout_tail": "\n".join(stdout.splitlines()[-10:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-10:]),
        "log": str(log_path),
    }


def _run_smoke(diag_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    log_path = diag_dir / "smoke.log"
    cmd = [
        sys.executable,
        "-m",
        "main",
        "--dry-run",
    ]
    code, stdout, stderr = _run_subprocess(cmd, env=env, log_path=log_path, timeout=300)
    notes = []
    for marker in ("/health", "/ready"):
        if marker in stdout or marker in stderr:
            notes.append(f"log contains {marker}")
    return {
        "returncode": code,
        "stdout_tail": "\n".join(stdout.splitlines()[-10:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-10:]),
        "log": str(log_path),
        "notes": notes,
    }


def _parse_value_markets(settings: Any) -> tuple[str, ...]:
    raw = getattr(settings, "VALUE_MARKETS", "1X2,OU_2_5,BTTS")
    return tuple(item.strip() for item in str(raw).split(",") if item.strip())


def _build_value_detector_settings(settings: Any) -> ValueDetector:
    return ValueDetector(
        min_edge_pct=float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0)),
        min_confidence=float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6)),
        max_picks=int(getattr(settings, "VALUE_MAX_PICKS", 5)),
        markets=_parse_value_markets(settings),
        overround_method=str(getattr(settings, "ODDS_OVERROUND_METHOD", "proportional")),
    )


@dataclass
class _DummyDiagProvider:
    mapper: LinesMapper

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[Any]:  # pragma: no cover - fallback path
        return []


def _create_lines_provider_diag(settings: Any, mapper: LinesMapper) -> LinesProvider | None:
    provider_names = _resolve_provider_names(settings)
    providers: dict[str, LinesProvider] = {}
    for name in provider_names:
        instance = _instantiate_provider_diag(name, settings, mapper)
        if instance:
            providers[name] = instance
    active = {
        name: provider
        for name, provider in providers.items()
        if not isinstance(provider, _DummyDiagProvider)
    }
    if not active:
        return next(iter(providers.values()), None)
    weights = parse_provider_weights(getattr(settings, "ODDS_PROVIDER_WEIGHTS", None))
    if getattr(settings, "RELIAB_V2_ENABLE", False):
        reliability_tracker = get_reliab_tracker()
    else:
        reliability_tracker = ProviderReliabilityTracker(
            decay=float(getattr(settings, "RELIABILITY_DECAY", 0.9)),
            max_freshness_sec=float(getattr(settings, "RELIABILITY_MAX_FRESHNESS_SEC", 600.0)),
        )
    anomaly_detector = OddsAnomalyDetector(
        z_max=float(getattr(settings, "ANOMALY_Z_MAX", 3.0)),
    )
    aggregator = LinesAggregator(
        method=str(getattr(settings, "ODDS_AGG_METHOD", "median")),
        provider_weights=weights,
        store=OddsSQLiteStore(),
        retention_days=int(getattr(settings, "ODDS_SNAPSHOT_RETENTION_DAYS", 14)),
        movement_window_minutes=int(getattr(settings, "CLV_WINDOW_BEFORE_KICKOFF_MIN", 120)),
        reliability=reliability_tracker,
        anomaly_detector=anomaly_detector,
        known_providers=active.keys(),
        best_price_lookback_min=int(getattr(settings, "BEST_PRICE_LOOKBACK_MIN", 15)),
        best_price_min_score=float(getattr(settings, "BEST_PRICE_MIN_SCORE", 0.6)),
    )
    return AggregatingLinesProvider(active, aggregator=aggregator)


def _resolve_provider_names(settings: Any) -> list[str]:
    raw = str(getattr(settings, "ODDS_PROVIDERS", "") or "").strip()
    names = [token.strip().lower() for token in raw.split(",") if token.strip()]
    if not names:
        fallback = str(getattr(settings, "ODDS_PROVIDER", "dummy") or "dummy")
        names = [fallback.lower()]
    return names


def _instantiate_provider_diag(name: str, settings: Any, mapper: LinesMapper) -> LinesProvider | None:
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
            raise RuntimeError("ODDS_HTTP_BASE_URL не задан для HTTP-провайдера")
        return HTTPLinesProvider(
            base_url=base_url,
            token=getattr(settings, "ODDS_API_KEY", "") or None,
            timeout=float(getattr(settings, "ODDS_TIMEOUT_SEC", 8.0)),
            retry_attempts=int(getattr(settings, "ODDS_RETRY_ATTEMPTS", 4)),
            backoff_base=float(getattr(settings, "ODDS_BACKOFF_BASE", 0.4)),
            rps_limit=float(getattr(settings, "ODDS_RPS_LIMIT", 3.0)),
            mapper=mapper,
        )
    return _DummyDiagProvider(mapper)


def _summarize_reliability(
    aggregator: LinesAggregator, settings: Any
) -> dict[str, Any]:
    tracker = aggregator.reliability_tracker
    if tracker is None:
        return {}
    stats = tracker.snapshot()
    if not stats:
        return {"entries": 0, "below_threshold": []}
    min_score_threshold = float(getattr(settings, "RELIABILITY_MIN_SCORE", 0.5))
    min_coverage_threshold = float(getattr(settings, "RELIABILITY_MIN_COVERAGE", 0.6))
    min_samples_threshold = int(getattr(settings, "RELIAB_MIN_SAMPLES", 200))
    if isinstance(tracker, ProviderReliabilityV2):
        avg_score = sum(item.score for item in stats) / len(stats)
        min_score = min(item.score for item in stats)
        avg_fresh = sum(item.fresh_component for item in stats) / len(stats)
        avg_latency = sum(item.latency_component for item in stats) / len(stats)
        failures: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for item in stats:
            entry = {
                "provider": item.provider,
                "market": item.market,
                "league": item.league,
                "score": item.score,
                "samples": item.samples,
            }
            if item.score < min_score_threshold:
                failures.append(entry)
            elif item.samples < min_samples_threshold:
                warnings.append(entry)
        return {
            "entries": len(stats),
            "avg_score": avg_score,
            "avg_coverage": avg_fresh,
            "avg_latency_component": avg_latency,
            "min_score": min_score,
            "below_threshold": failures,
            "low_samples": warnings,
            "thresholds": {
                "score": min_score_threshold,
                "samples": min_samples_threshold,
            },
        }
    avg_score = sum(item.score for item in stats) / len(stats)
    avg_coverage = sum(item.coverage for item in stats) / len(stats)
    avg_lag = sum(item.lag_ms for item in stats) / len(stats)
    min_score = min(item.score for item in stats)
    failures = [
        {
            "provider": item.provider,
            "market": item.market,
            "league": item.league,
            "score": item.score,
            "coverage": item.coverage,
        }
        for item in stats
        if item.score < min_score_threshold or item.coverage < min_coverage_threshold
    ]
    return {
        "entries": len(stats),
        "avg_score": avg_score,
        "avg_coverage": avg_coverage,
        "avg_latency_component": avg_lag,
        "min_score": min_score,
        "below_threshold": failures,
        "low_samples": [],
        "thresholds": {
            "score": min_score_threshold,
            "coverage": min_coverage_threshold,
        },
    }


def _summarize_best_price(
    aggregator: LinesAggregator, settings: Any, now: datetime | None = None
) -> dict[str, Any]:
    meta = aggregator.last_metadata
    available = len(meta)
    summary: dict[str, Any] = {
        "routes": 0,
        "available": available,
        "skipped": available,
        "avg_score": 0.0,
        "avg_improvement_pct": 0.0,
        "provider_usage": {},
        "flagged_total": 0,
        "samples": [],
    }
    if not meta:
        return summary
    store = aggregator.store
    if store is None:
        return summary
    now = now or datetime.now(UTC)
    lookback = int(
        getattr(
            aggregator,
            "_best_price_lookback_min",
            getattr(settings, "BEST_PRICE_LOOKBACK_MIN", 15),
        )
    )
    cutoff = now - timedelta(minutes=max(lookback, 1))
    anomaly = aggregator.anomaly_detector
    provider_usage: Counter[str] = Counter()
    best_routes: list[dict[str, Any]] = []
    flagged_total = 0
    for item in meta.values():
        market_upper = item.market.upper()
        selection_upper = item.selection.upper()
        quotes = [
            quote
            for quote in store.latest_quotes(
                match_key=item.match_key,
                market=market_upper,
                selection=selection_upper,
            )
            if quote.pulled_at >= cutoff
        ]
        flagged: set[str] = set()
        if anomaly and quotes:
            flagged = anomaly.filter_anomalies(quotes, emit_metrics=False)
        flagged_total += len(flagged)
        route = aggregator.pick_best_route(
            match_key=item.match_key,
            market=item.market,
            selection=item.selection,
            league=item.league,
            now=now,
        )
        if not route:
            continue
        improvement_pct = 0.0
        if item.price_decimal > 0:
            improvement_pct = (
                float(route.get("price_decimal", 0.0)) / float(item.price_decimal) - 1.0
            ) * 100.0
        best_routes.append(
            {
                "match_key": item.match_key,
                "market": item.market,
                "selection": item.selection,
                "provider": route.get("provider"),
                "score": float(route.get("score", 0.0)),
                "price_decimal": float(route.get("price_decimal", 0.0)),
                "consensus_price": float(item.price_decimal),
                "improvement_pct": improvement_pct,
                "flagged": sorted(flagged),
            }
        )
        provider = route.get("provider")
        if provider:
            provider_usage[str(provider)] += 1
    routes = len(best_routes)
    summary.update(
        {
            "routes": routes,
            "available": available,
            "skipped": max(available - routes, 0),
            "flagged_total": flagged_total,
            "provider_usage": dict(provider_usage),
            "samples": best_routes[:5],
            "thresholds": {
                "lookback_min": lookback,
                "min_score": float(
                    getattr(
                        aggregator,
                        "_best_price_min_score",
                        getattr(settings, "BEST_PRICE_MIN_SCORE", 0.6),
                    )
                ),
            },
        }
    )
    if not routes:
        return summary
    summary["avg_score"] = sum(item["score"] for item in best_routes) / routes
    summary["avg_improvement_pct"] = (
        sum(item["improvement_pct"] for item in best_routes) / routes
    )
    return summary


def _run_value_section(diag_dir: Path, settings: Any) -> dict[str, Any]:
    mapper = LinesMapper()
    detector = _build_value_detector_settings(settings)
    provider = None
    try:
        provider = _create_lines_provider_diag(settings, mapper)
    except Exception as exc:  # pragma: no cover - configuration issues
        return {"status": "❌", "note": f"provider init failed: {exc}"}
    facade = PredictionFacade()
    fallback_provider = _DummyDiagProvider(mapper)
    service = ValueService(
        facade=facade,
        provider=provider or fallback_provider,
        detector=detector,
        mapper=mapper,
    )

    async def _collect() -> tuple[list[Any], list[Any], list[Any], dict[str, dict[str, object]]]:
        target_date = date.today()
        predictions = await facade.today(target_date)
        meta: dict[str, dict[str, object]] = {}
        outcomes = list(service._build_model_outcomes(predictions, meta))
        if provider is None:
            return predictions, [], [], meta
        date_from = datetime.combine(target_date, dt_time.min, tzinfo=UTC)
        date_to = datetime.combine(target_date, dt_time.max, tzinfo=UTC)
        odds = await provider.fetch_odds(date_from=date_from, date_to=date_to)
        picks = detector.detect(model=outcomes, market=odds)
        return predictions, odds, picks, meta

    try:
        predictions, odds, picks, meta = asyncio.run(_collect())
    except Exception as exc:  # pragma: no cover - unexpected runtime error
        return {"status": "❌", "note": f"value collect failed: {exc}"}
    finally:
        if provider is not None:
            close_fn = getattr(provider, "close", None)
            if close_fn:
                try:
                    result = close_fn()
                    if asyncio.iscoroutine(result):
                        asyncio.run(result)
                except Exception:
                    pass

    edges = [float(pick.edge_pct) for pick in picks]
    edge_stats = {
        "count": len(edges),
        "max": max(edges) if edges else 0.0,
        "min": min(edges) if edges else 0.0,
        "mean": statistics.mean(edges) if edges else 0.0,
    }
    cards = [
        {
            "match": meta.get(pick.match_key, {}),
            "market": pick.market,
            "selection": pick.selection,
            "edge_pct": pick.edge_pct,
            "provider": pick.provider,
            "market_price": pick.market_price,
            "fair_price": pick.fair_price,
        }
        for pick in picks
    ]
    odds_count = len(odds) if provider is not None else 0
    status = "✅" if odds_count > 0 else "⚠️"
    note = f"odds={odds_count} predictions={len(predictions)} picks={len(cards)}"
    aggregation_stats: dict[str, object] = {}
    reliability_stats: dict[str, Any] = {}
    best_price_stats: dict[str, Any] = {}
    if isinstance(provider, AggregatingLinesProvider):
        aggregator = provider.aggregator
        meta = aggregator.last_metadata
        if meta:
            counts = [item.provider_count for item in meta.values()]
            avg_count = sum(counts) / len(counts)
            trend_counts = Counter(item.trend for item in meta.values())
        else:
            avg_count = 0.0
            trend_counts = Counter()
        aggregation_stats = {
            "method": aggregator.method,
            "pairs": len(meta),
            "avg_provider_count": avg_count,
            "trend_counts": dict(trend_counts),
        }
        reliability_stats = _summarize_reliability(aggregator, settings)
        best_price_stats = _summarize_best_price(aggregator, settings)
        if aggregation_stats["pairs"]:
            note += f" avg_providers={avg_count:.1f}"
        if best_price_stats.get("available"):
            note += (
                " best_price="
                f"{int(best_price_stats.get('routes', 0))}/"
                f"{int(best_price_stats.get('available', 0))}"
            )
    clv_summary = {"entries": 0, "avg_clv": 0.0, "positive_share": 0.0}
    db_path = Path(settings.DB_PATH)
    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT clv_pct FROM picks_ledger WHERE clv_pct IS NOT NULL"
                ).fetchall()
        except sqlite3.DatabaseError:  # pragma: no cover - defensive guard
            rows = []
        values = [float(row["clv_pct"]) for row in rows]
        if values:
            avg = sum(values) / len(values)
            positive = sum(1 for value in values if value >= 0.0) / len(values)
            clv_summary = {
                "entries": len(values),
                "avg_clv": avg,
                "positive_share": positive,
            }
    return {
        "status": status,
        "note": note,
        "edges": edges,
        "edge_stats": edge_stats,
        "picks": cards,
        "odds_count": odds_count,
        "predictions": len(predictions),
        "aggregation": aggregation_stats,
        "best_price": best_price_stats,
        "reliability": reliability_stats,
        "clv": clv_summary,
    }


def _run_settlement_section(settings: Any) -> dict[str, Any]:
    db_path = str(getattr(settings, "DB_PATH", ""))
    window_days = int(getattr(settings, "PORTFOLIO_ROLLING_DAYS", 60))
    min_coverage = float(getattr(settings, "RELIABILITY_MIN_COVERAGE", 0.6))
    roi_threshold = float(getattr(settings, "CLV_FAIL_THRESHOLD_PCT", -1.0))
    try:
        summary = settlement_module._load_summary(db_path, window_days)
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "status": "⚠️",
            "note": f"settlement load failed: {exc}",
            "summary": {},
        }
    payload = dataclasses.asdict(summary)
    payload.update(
        {
            "window_days": window_days,
            "thresholds": {"coverage": min_coverage, "roi": roi_threshold},
        }
    )
    if summary.total == 0:
        status = "⚠️"
        note = "нет сигналов"
    else:
        status = "✅"
        if summary.coverage < min_coverage or summary.window_roi < roi_threshold:
            status = "❌"
        note = (
            f"coverage={summary.coverage:.2f}"
            f" roi={summary.window_roi:.2f}% avg={summary.avg_roi:.2f}%"
        )
    return {"status": status, "note": note, "summary": payload}


def _run_value_calibration_section(settings: Any) -> dict[str, Any]:
    raw_days = getattr(settings, "BACKTEST_DAYS", None)
    try:
        days = int(raw_days) if raw_days is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        days = None
    if days is not None and days <= 0:
        days = None
    report = run_backtest_calibration(days=days)
    status_map = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}
    status = status_map.get(report.get("status", "WARN"), "⚠️")
    records = report.get("records", [])
    if records:
        top = max(records, key=lambda row: row.get("sharpe", 0.0))
        note = (
            f"{len(records)} пар, best {top['league']}/{top['market']} "
            f"τ={top['tau_edge']:.1f}% γ={top['gamma_conf']:.2f} sharpe={top['sharpe']:.3f}"
        )
    else:
        note = report.get("reason", "нет данных")
    return {"status": status, "note": note, "report": report}
@dataclass
class LevelAMetrics:
    folds: list[dict[str, float]]
    best_alpha: float
    feature_ranking: list[tuple[str, float]]
    lambda_stats: dict[str, float]
    artifact: Path


def _simulate_dataset(n_rows: int = 180, seed: int = 20240920) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-08-01", periods=n_rows, freq="D")
    leagues = rng.choice(["EPL", "LaLiga", "SerieA", "Bundesliga"], size=n_rows)
    home_team = rng.integers(100, 200, size=n_rows)
    away_team = rng.integers(200, 300, size=n_rows)
    rest_home = rng.integers(2, 8, size=n_rows)
    rest_away = rng.integers(2, 8, size=n_rows)
    motivation = rng.normal(0.0, 0.4, size=n_rows)
    fatigue = rng.normal(0.0, 0.3, size=n_rows)
    injuries = rng.normal(0.0, 0.2, size=n_rows)
    home_xg = rng.gamma(2.0, 0.7, size=n_rows)
    away_xg = rng.gamma(2.1, 0.6, size=n_rows)
    home_xga = rng.gamma(2.0, 0.5, size=n_rows)
    away_xga = rng.gamma(2.2, 0.45, size=n_rows)
    ppda_home = rng.normal(10, 2, size=n_rows)
    ppda_away = rng.normal(10.5, 2, size=n_rows)
    oppda_home = rng.normal(12, 2.5, size=n_rows)
    oppda_away = rng.normal(11.5, 2.5, size=n_rows)
    mismatch_home = rng.normal(0, 1, size=n_rows)
    mismatch_away = rng.normal(0, 1, size=n_rows)
    z_att_home = rng.normal(0, 1, size=n_rows)
    z_att_away = rng.normal(0, 1, size=n_rows)
    z_def_home = rng.normal(0, 1, size=n_rows)
    z_def_away = rng.normal(0, 1, size=n_rows)

    lambda_home = np.clip(
        1.1
        + 0.4 * (home_xg - away_xga)
        + 0.08 * motivation
        - 0.12 * fatigue
        - 0.05 * injuries
        + 0.03 * z_att_home
        - 0.04 * z_def_away,
        0.3,
        4.5,
    )
    lambda_away = np.clip(
        0.9
        + 0.35 * (away_xg - home_xga)
        + 0.06 * (-motivation)
        - 0.1 * (-fatigue)
        - 0.04 * injuries
        + 0.04 * z_att_away
        - 0.03 * z_def_home,
        0.2,
        4.0,
    )
    goals_home = rng.poisson(lambda_home)
    goals_away = rng.poisson(lambda_away)

    df = pd.DataFrame(
        {
            "date": dates,
            "league_id": leagues,
            "home_team_id": home_team,
            "away_team_id": away_team,
            "home_rest_days": rest_home,
            "away_rest_days": rest_away,
            "motivation": motivation,
            "fatigue": fatigue,
            "injuries": injuries,
            "home_km_trip": rng.uniform(10, 600, size=n_rows),
            "away_km_trip": rng.uniform(10, 600, size=n_rows),
            "home_xg": home_xg,
            "away_xg": away_xg,
            "home_xga": home_xga,
            "away_xga": away_xga,
            "home_ppda": ppda_home,
            "away_ppda": ppda_away,
            "home_oppda": oppda_home,
            "away_oppda": oppda_away,
            "home_mismatch": mismatch_home,
            "away_mismatch": mismatch_away,
            "home_league_zscore_attack": z_att_home,
            "away_league_zscore_attack": z_att_away,
            "home_league_zscore_defense": z_def_home,
            "away_league_zscore_defense": z_def_away,
            "home_goals": goals_home,
            "away_goals": goals_away,
            "lambda_home_true": lambda_home,
            "lambda_away_true": lambda_away,
        }
    )
    return df


def _to_quality_frame(df: pd.DataFrame) -> pd.DataFrame:
    seasons = df["date"].dt.year
    frame = pd.DataFrame(
        {
            "match_id": np.arange(1, len(df) + 1),
            "home_team": df["home_team_id"].apply(lambda x: f"Team {int(x)}"),
            "away_team": df["away_team_id"].apply(lambda x: f"Team {int(x)}"),
            "home_team_code": df["home_team_id"].astype(str),
            "away_team_code": df["away_team_id"].astype(str),
            "league": df["league_id"],
            "league_code": df["league_id"],
            "season": seasons.astype(str) + "/" + (seasons + 1).astype(str),
            "season_start": seasons.astype(int),
            "season_end": (seasons + 1).astype(int),
            "kickoff_utc": df["date"].dt.tz_localize("UTC"),
            "home_xg": df["home_xg"],
            "away_xg": df["away_xg"],
            "home_xga": df["home_xga"],
            "away_xga": df["away_xga"],
            "home_timezone": "Europe/London",
            "away_timezone": "Europe/London",
        }
    )
    return frame


def _poisson_1x2_prob(lambda_home: np.ndarray, lambda_away: np.ndarray) -> np.ndarray:
    max_goals = 10
    probs = np.zeros((lambda_home.size, 3))
    for idx, (lam_h, lam_a) in enumerate(zip(lambda_home, lambda_away, strict=False)):
        pmf_cache: dict[int, float] = {}
        total_prob = 0.0
        home = 0.0
        draw = 0.0
        away = 0.0
        for h in range(max_goals + 1):
            pmf_h = math.exp(-lam_h) * lam_h**h / math.factorial(h)
            pmf_cache[h] = pmf_h
        for a in range(max_goals + 1):
            pmf_a = math.exp(-lam_a) * lam_a**a / math.factorial(a)
            for h, pmf_h in pmf_cache.items():
                prob = pmf_h * pmf_a
                total_prob += prob
                if h > a:
                    home += prob
                elif h == a:
                    draw += prob
                else:
                    away += prob
        probs[idx] = [home, draw, away]
        if total_prob < 0.999:
            # Нормализация на случай обрезания хвостов
            probs[idx] = probs[idx] / max(total_prob, 1e-9)
    return probs


def _run_data_quality(dataset: pd.DataFrame, diag_dir: Path) -> dict[str, Any]:
    quality_dir = diag_dir / "data_quality"
    quality_df = _to_quality_frame(dataset)
    report = run_quality_suite(quality_df, output_dir=quality_dir)
    return {
        "status": report.overall_status,
        "note": f"summary={report.summary_path.name}",
        "summary_path": str(report.summary_path),
        "csv_artifacts": {name: str(path) for name, path in report.csv_artifacts.items()},
        "issue_counts": report.issue_counts,
        "issue_total": int(sum(report.issue_counts.values())),
    }


def _run_golden(reports_root: Path) -> dict[str, Any]:
    baseline_path = reports_root / "golden" / "baseline.json"
    snapshot = golden_module.build_snapshot()
    existing = golden_module.load_snapshot(baseline_path)
    if existing is None:
        golden_module.write_snapshot(baseline_path, snapshot)
        return {
            "status": "⚠️",
            "note": "baseline created",
            "baseline_path": str(baseline_path),
        }
    diff = golden_module.compare_snapshots(snapshot, existing)
    status = diff.get("status", "⚠️")
    golden_module.write_snapshot(baseline_path, snapshot)
    return {
        "status": status,
        "note": f"max_coef_delta={diff['checks']['coefficients_home']['max_delta']:.4f}",
        "baseline_path": str(baseline_path),
        "diff": diff,
    }


def _run_drift(diag_dir: Path, dataset: pd.DataFrame) -> dict[str, Any]:
    drift_dir = diag_dir / "drift"
    thresholds = drift_module.DriftThresholds(
        psi_warn=float(os.getenv("DRIFT_PSI_WARN", "0.1")),
        psi_fail=float(os.getenv("DRIFT_PSI_FAIL", "0.25")),
        ks_p_warn=float(os.getenv("DRIFT_KS_P_WARN", "0.05")),
        ks_p_fail=float(os.getenv("DRIFT_KS_P_FAIL", "0.01")),
    )
    config = drift_module.DriftConfig(
        reports_dir=drift_dir,
        ref_days=int(os.getenv("DRIFT_REF_DAYS", "90")),
        ref_rolling_days=int(os.getenv("DRIFT_ROLLING_DAYS", "30")),
        thresholds=thresholds,
    )
    result = drift_module.run(config, dataset=dataset)
    status_map = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}
    status_emoji = status_map.get(result.worst_status, "⚠️")
    scope_notes = []
    for reference, scopes in sorted(result.status_by_reference.items()):
        overall = scopes.get("overall", "OK")
        scope_notes.append(f"{reference}:{overall}")
    psi_max: dict[str, float] = {}
    for scope in {"global", "league", "season"}:
        values = [m.psi for m in result.metrics if m.scope == scope and not math.isnan(m.psi)]
        if values:
            psi_max[scope] = max(values)
    return {
        "status": status_emoji,
        "note": ", ".join(scope_notes) or "no-scope-data",
        "summary_path": str(result.summary_path),
        "json_path": str(result.json_path),
        "psi_max": psi_max,
        "status_raw": result.status_by_reference,
    }


def _run_calibration_section(dataset: pd.DataFrame, diag_dir: Path) -> dict[str, Any]:
    calib_dir = diag_dir / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)
    probs = _poisson_1x2_prob(dataset["lambda_home_true"].to_numpy(), dataset["lambda_away_true"].to_numpy())
    outcomes_idx = np.where(
        dataset["home_goals"] > dataset["away_goals"],
        0,
        np.where(dataset["home_goals"] == dataset["away_goals"], 1, 2),
    )
    calibration_payload: dict[str, Any] = {}
    for label, column in {"home": 0, "draw": 1, "away": 2}.items():
        target = (outcomes_idx == column).astype(int)
        result = reliability_table(probs[:, column], target, bins=10)
        plot_path = calib_dir / f"reliability_{label}.png"
        try:
            from app.diagnostics.calibration import plot_reliability

            plot_reliability(result, plot_path)
        except Exception:  # pragma: no cover - plotting is optional
            plot_path = Path("")
        calibration_payload[label] = {
            "ece": result.ece,
            "bins": [bin.__dict__ for bin in result.bins],
            "plot": str(plot_path) if plot_path else "",
        }

    totals_lambda = dataset["lambda_home_true"].to_numpy() + dataset["lambda_away_true"].to_numpy()
    totals_outcomes = (dataset["home_goals"] + dataset["away_goals"] > 2).astype(int)
    prob_over25 = 1 - np.exp(-totals_lambda) * (1 + totals_lambda + (totals_lambda**2) / 2)
    over_result = reliability_table(prob_over25, totals_outcomes, bins=10)
    calibration_payload["over25"] = {"ece": over_result.ece}

    btts_outcomes = ((dataset["home_goals"] > 0) & (dataset["away_goals"] > 0)).astype(int)
    prob_btts = 1 - np.exp(-dataset["lambda_home_true"]) - np.exp(-dataset["lambda_away_true"]) + np.exp(
        -(dataset["lambda_home_true"] + dataset["lambda_away_true"])
    )
    btts_result = reliability_table(prob_btts, btts_outcomes, bins=10)
    calibration_payload["btts"] = {"ece": btts_result.ece}

    rng = np.random.default_rng(20240921)
    samples = (dataset["home_goals"] + dataset["away_goals"]).to_numpy()
    lower_80: list[float] = []
    upper_80: list[float] = []
    lower_90: list[float] = []
    upper_90: list[float] = []
    for lam in totals_lambda:
        draws = rng.poisson(lam, size=500)
        lower_80.append(float(np.quantile(draws, 0.1)))
        upper_80.append(float(np.quantile(draws, 0.9)))
        lower_90.append(float(np.quantile(draws, 0.05)))
        upper_90.append(float(np.quantile(draws, 0.95)))
    coverage_80 = monte_carlo_coverage(samples, lower_80, upper_80, target=0.8, tolerance=0.02)
    coverage_90 = monte_carlo_coverage(samples, lower_90, upper_90, target=0.9, tolerance=0.02)

    return {
        "status": "✅" if coverage_80.status == "✅" and coverage_90.status == "✅" else "⚠️",
        "note": f"ece_home={calibration_payload['home']['ece']:.3f}",
        "calibration": calibration_payload,
        "coverage": {
            "c80": coverage_80.__dict__,
            "c90": coverage_90.__dict__,
        },
    }


def _run_invariance_checks(dataset: pd.DataFrame) -> dict[str, Any]:
    lam_home = float(dataset["lambda_home_true"].mean())
    lam_away = float(dataset["lambda_away_true"].mean())
    swap = bipoisson_swap_check(lam_home, lam_away)
    score = scoreline_symmetry(lam_home, lam_away)
    status = "✅" if swap.status == "✅" and score.status == "✅" else "⚠️"
    return {
        "status": status,
        "note": f"swap_delta={swap.max_delta:.2e}",
        "swap": swap.__dict__,
        "score": score.__dict__,
    }


def _run_benchmarks(diag_dir: Path) -> dict[str, Any]:
    bench_dir = diag_dir / "bench"
    bench_dir.mkdir(parents=True, exist_ok=True)
    iterations = int(os.getenv("BENCH_ITER", "30"))
    budget_ms = float(os.getenv("BENCH_P95_BUDGET_MS", "800"))
    results = bench_module.run_benchmarks(iterations=iterations)
    json_path = bench_dir / "bench.json"
    payload = {
        "budget_ms": budget_ms,
        "cases": {
            name: {
                "p50_ms": result.p50_ms,
                "p95_ms": result.p95_ms,
                "peak_memory_kb": result.peak_memory_kb,
                "iterations": result.iterations,
            }
            for name, result in results.items()
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_lines = ["# Benchmarks", "", "| Case | p95 (ms) | Peak memory (KB) |", "| --- | --- | --- |"]
    worst_status = "✅"
    for name, result in results.items():
        summary_lines.append(f"| {name} | {result.p95_ms:.1f} | {result.peak_memory_kb:.1f} |")
        if result.p95_ms > budget_ms:
            worst_status = "⚠️"
    summary_path = bench_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return {
        "status": worst_status,
        "note": f"budget={budget_ms}ms",
        "summary_path": str(summary_path),
        "json_path": str(json_path),
    }


def _run_static_analysis(diag_dir: Path) -> dict[str, Any]:
    analysis_dir = diag_dir / "static"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    checks = {
        "mypy": ("mypy", [sys.executable, "-m", "mypy", "--config-file", "mypy.ini", "app", "app/bot"]),
        "bandit": ("bandit", [sys.executable, "-m", "bandit", "-r", "app", "-lll"]),
        "pip-audit": ("pip_audit", [sys.executable, "-m", "pip_audit", "-r", "requirements.txt"]),
    }
    results: dict[str, Any] = {}
    overall = "✅"
    for name, (module_name, cmd) in checks.items():
        if importlib.util.find_spec(module_name) is None:
            results[name] = {
                "status": "⚠️",
                "returncode": None,
                "log": "",
                "note": f"module {module_name} not installed",
            }
            if overall != "❌":
                overall = "⚠️"
            continue
        log_path = analysis_dir / f"{name}.log"
        code, stdout, stderr = _run_subprocess(cmd, log_path=log_path)
        if code == 0:
            status = "✅"
        elif name == "mypy":
            status = "❌"
            overall = "❌"
        else:
            status = "⚠️"
            if overall != "❌":
                overall = "⚠️"
        results[name] = {
            "status": status,
            "returncode": code,
            "log": str(log_path),
        }

    secret_pattern = re.compile(r"(TOKEN|KEY|PASSWORD)=([^\s]+)", re.IGNORECASE)
    leaks: list[str] = []
    for log_file in analysis_dir.glob("*.log"):
        try:
            content = log_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in secret_pattern.finditer(content):
            value = match.group(2)
            if value and value.lower() not in {"stub-token", "stub-odds", "dummy"}:
                leaks.append(f"{log_file.name}:{match.group(0)}")
    if leaks:
        overall = "❌"
    return {
        "status": overall,
        "note": "; ".join(leaks) if leaks else "static analysis completed",
        "results": results,
        "secrets": leaks,
    }


def _safe_log_loss(outcomes: np.ndarray, probs: np.ndarray) -> float:
    clipped = np.clip(probs, 1e-9, 1 - 1e-9)
    clipped = clipped / clipped.sum(axis=1, keepdims=True)
    return float(log_loss(outcomes, clipped, labels=[0, 1, 2]))


def _multiclass_brier(y_true: np.ndarray, probs: np.ndarray) -> float:
    one_hot = np.eye(3)[y_true]
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def _train_level_a(df: pd.DataFrame, diag_dir: Path) -> LevelAMetrics:
    features = [
        "home_rest_days",
        "away_rest_days",
        "home_xg",
        "away_xg",
        "home_xga",
        "away_xga",
        "home_ppda",
        "away_ppda",
        "home_oppda",
        "away_oppda",
        "home_league_zscore_attack",
        "away_league_zscore_attack",
        "home_league_zscore_defense",
        "away_league_zscore_defense",
        "motivation",
        "fatigue",
        "injuries",
    ]
    X = df[features].to_numpy()
    y_home = df["home_goals"].to_numpy()
    y_away = df["away_goals"].to_numpy()
    log_y_home = np.log1p(y_home)
    log_y_away = np.log1p(y_away)
    folds: list[dict[str, float]] = []
    coefs_home: list[np.ndarray] = []
    coefs_away: list[np.ndarray] = []
    lambda_preds_home = np.zeros_like(y_home, dtype=float)
    lambda_preds_away = np.zeros_like(y_away, dtype=float)
    tscv = TimeSeriesSplit(n_splits=4, test_size=max(10, len(df) // 8))
    alphas = np.geomspace(0.001, 0.5, num=5)
    best_alpha = None
    best_score = float("inf")
    for alpha in alphas:
        cv_scores = []
        lambda_cv_home = np.zeros_like(y_home, dtype=float)
        lambda_cv_away = np.zeros_like(y_away, dtype=float)
        for _fold_id, (train_idx, test_idx) in enumerate(tscv.split(X)):
            model_home = Ridge(alpha=alpha)
            model_away = Ridge(alpha=alpha)
            model_home.fit(X[train_idx], log_y_home[train_idx])
            model_away.fit(X[train_idx], log_y_away[train_idx])
            preds_home = np.clip(np.expm1(model_home.predict(X[test_idx])), 0.1, 6.0)
            preds_away = np.clip(np.expm1(model_away.predict(X[test_idx])), 0.1, 6.0)
            lambda_cv_home[test_idx] = preds_home
            lambda_cv_away[test_idx] = preds_away
            probs = _poisson_1x2_prob(preds_home, preds_away)
            outcomes = np.where(y_home[test_idx] > y_away[test_idx], 0, np.where(y_home[test_idx] == y_away[test_idx], 1, 2))
            fold_logloss = _safe_log_loss(outcomes, probs)
            fold_brier = _multiclass_brier(outcomes, probs)
            cv_scores.append(fold_logloss)
            if alpha == alphas[0]:
                # Сохраняем коэффициенты только для первой итерации, далее усредним после выбора alpha.
                pass
        mean_score = float(np.mean(cv_scores))
        if mean_score < best_score:
            best_score = mean_score
            best_alpha = float(alpha)
            lambda_preds_home = lambda_cv_home
            lambda_preds_away = lambda_cv_away

    if best_alpha is None:
        best_alpha = float(alphas[0])

    # Повторно прогоняем с лучшим alpha, чтобы собрать fold-метрики и коэффициенты
    for fold_id, (train_idx, test_idx) in enumerate(tscv.split(X)):
        model_home = Ridge(alpha=best_alpha)
        model_away = Ridge(alpha=best_alpha)
        model_home.fit(X[train_idx], log_y_home[train_idx])
        model_away.fit(X[train_idx], log_y_away[train_idx])
        preds_home = np.clip(np.expm1(model_home.predict(X[test_idx])), 0.1, 6.0)
        preds_away = np.clip(np.expm1(model_away.predict(X[test_idx])), 0.1, 6.0)
        probs = _poisson_1x2_prob(preds_home, preds_away)
        outcomes = np.where(y_home[test_idx] > y_away[test_idx], 0, np.where(y_home[test_idx] == y_away[test_idx], 1, 2))
        fold_logloss = _safe_log_loss(outcomes, probs)
        fold_brier = _multiclass_brier(outcomes, probs)
        folds.append({"fold": fold_id, "logloss": fold_logloss, "brier": fold_brier})
        coefs_home.append(model_home.coef_)
        coefs_away.append(model_away.coef_)

    coef_mean = (np.mean(coefs_home, axis=0) + np.mean(coefs_away, axis=0)) / 2
    feature_ranking = sorted(
        zip(features, np.abs(coef_mean), strict=False), key=lambda item: item[1], reverse=True
    )
    lambda_stats = {
        "lambda_home_mean": float(np.mean(lambda_preds_home)),
        "lambda_away_mean": float(np.mean(lambda_preds_away)),
        "lambda_home_std": float(np.std(lambda_preds_home)),
        "lambda_away_std": float(np.std(lambda_preds_away)),
        "mae_home": float(np.mean(np.abs(lambda_preds_home - df["lambda_home_true"].to_numpy()))),
        "mae_away": float(np.mean(np.abs(lambda_preds_away - df["lambda_away_true"].to_numpy()))),
    }

    artifact = diag_dir / "level_a_predictions.csv"
    export_df = df.copy()
    export_df["lambda_home_hat"] = lambda_preds_home
    export_df["lambda_away_hat"] = lambda_preds_away
    export_df.to_csv(artifact, index=False)

    return LevelAMetrics(folds=folds, best_alpha=best_alpha, feature_ranking=feature_ranking, lambda_stats=lambda_stats, artifact=artifact)


@dataclass
class LevelBMetrics:
    monotonic_checks: dict[str, float]
    ablation: dict[str, Any]
    artifact: Path


def _train_modifiers(df: pd.DataFrame, level_a: LevelAMetrics, diag_dir: Path) -> LevelBMetrics:
    from ml.modifiers_model import ModifiersModel

    feature_cols = ["motivation", "fatigue", "injuries"]
    X = df[feature_cols]
    lam_home_base = df["lambda_home_true"].to_numpy()
    lam_away_base = df["lambda_away_true"].to_numpy()
    y_home = np.clip(lam_home_base * (1 + 0.05 * df["motivation"].to_numpy()), 0.2, 5.0)
    y_away = np.clip(lam_away_base * (1 - 0.04 * df["motivation"].to_numpy()), 0.2, 5.0)

    model = ModifiersModel(alpha=0.5).fit(X, y_home, y_away)
    lam_home_mod, lam_away_mod = model.transform(level_a.lambda_stats["lambda_home_mean"] * np.ones_like(y_home), level_a.lambda_stats["lambda_away_mean"] * np.ones_like(y_away), X)

    monotonic_checks = {}
    for feature, sign in {"motivation": 1, "fatigue": -1, "injuries": -1}.items():
        feature_values = X[feature].to_numpy()
        if hasattr(statistics, "correlation"):
            try:
                corr_home = statistics.correlation(feature_values, lam_home_mod)
            except statistics.StatisticsError:
                corr_home = 0.0
        else:
            corr_home = float(np.corrcoef(feature_values, lam_home_mod)[0, 1])
            if np.isnan(corr_home):
                corr_home = 0.0
        monotonic_checks[f"home_{feature}"] = float(corr_home * sign)

    probs_base = _poisson_1x2_prob(level_a.lambda_stats["lambda_home_mean"] * np.ones_like(y_home), level_a.lambda_stats["lambda_away_mean"] * np.ones_like(y_away))
    outcomes = np.where(df["home_goals"] > df["away_goals"], 0, np.where(df["home_goals"] == df["away_goals"], 1, 2))
    logloss_base = _safe_log_loss(outcomes, probs_base)

    lam_home_adj = lam_home_mod
    lam_away_adj = lam_away_mod
    probs_mod = _poisson_1x2_prob(lam_home_adj, lam_away_adj)
    logloss_mod = _safe_log_loss(outcomes, probs_mod)
    brier_base = _multiclass_brier(outcomes, probs_base)
    brier_mod = _multiclass_brier(outcomes, probs_mod)

    artifact = diag_dir / "level_b_modifiers.csv"
    pd.DataFrame(
        {
            "motivation": X["motivation"],
            "fatigue": X["fatigue"],
            "injuries": X["injuries"],
            "lambda_home_mod": lam_home_adj,
            "lambda_away_mod": lam_away_adj,
        }
    ).to_csv(artifact, index=False)

    return LevelBMetrics(
        monotonic_checks=monotonic_checks,
        ablation={
            "logloss_base": float(logloss_base),
            "logloss_mod": float(logloss_mod),
            "brier_base": float(brier_base),
            "brier_mod": float(brier_mod),
        },
        artifact=artifact,
    )


@dataclass
class LevelCMetrics:
    markets: dict[str, float]
    top_scores: list[tuple[str, float]]
    calibration: dict[str, Any]
    artifacts: dict[str, str]


def _simulate_level_c(df: pd.DataFrame, diag_dir: Path) -> LevelCMetrics:
    from ml.montecarlo_simulator import simulate

    lam_home = df["lambda_home_true"].iloc[:50].mean()
    lam_away = df["lambda_away_true"].iloc[:50].mean()
    sim_result = simulate(5000, lambda_home=lam_home, lambda_away=lam_away, seed=20240920, top_n=10)

    totals = df["home_goals"] + df["away_goals"]
    over25 = (totals > 2.5).astype(int)
    probs_over = np.clip(df["lambda_home_true"] + df["lambda_away_true"], 0, 8) / 8
    frac_pos, mean_pred = calibration_curve(over25, probs_over, n_bins=8, strategy="quantile")

    artifacts: dict[str, str] = {}
    if HAS_MPL and plt is not None:
        rel_path = diag_dir / "reliability_over25.png"
        plt.figure(figsize=(6, 4))
        plt.plot(mean_pred, frac_pos, marker="o", label="Model")
        plt.plot([0, 1], [0, 1], linestyle="--", label="Perfect")
        plt.title("Reliability — Over 2.5 Goals")
        plt.xlabel("Predicted probability")
        plt.ylabel("Observed frequency")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(rel_path)
        plt.close()
        artifacts["reliability"] = str(rel_path)

        totals_path = diag_dir / "totals_distribution.png"
        plt.figure(figsize=(6, 4))
        plt.hist(totals, bins=range(0, 9), edgecolor="black")
        if PercentFormatter is not None:
            plt.gca().yaxis.set_major_formatter(PercentFormatter(xmax=len(totals)))
        plt.title("Distribution of Total Goals")
        plt.xlabel("Total goals")
        plt.ylabel("Frequency")
        plt.tight_layout()
        plt.savefig(totals_path)
        plt.close()
        artifacts["totals"] = str(totals_path)

        heatmap_path = diag_dir / "scorelines_heatmap.png"
        matrix = np.zeros((6, 6))
        for score, prob in sim_result.top_scorelines:
            home, away = map(int, score.split("-"))
            if home < 6 and away < 6:
                matrix[home, away] = prob
        plt.figure(figsize=(5, 4))
        plt.imshow(matrix, cmap="magma")
        plt.colorbar(label="Probability")
        plt.title("Top scorelines heatmap")
        plt.xlabel("Away goals")
        plt.ylabel("Home goals")
        plt.tight_layout()
        plt.savefig(heatmap_path)
        plt.close()
        artifacts["scorelines"] = str(heatmap_path)

        gain_path = diag_dir / "gain_chart.png"
        preds = probs_over
        actual = over25
        order = np.argsort(preds)[::-1]
        gains = np.cumsum(actual[order]) / max(1, actual.sum())
        plt.figure(figsize=(6, 4))
        plt.plot(np.linspace(0, 1, len(gains)), gains, label="Model")
        plt.plot([0, 1], [0, 1], linestyle="--", label="Random")
        plt.title("Gain chart — Over 2.5")
        plt.xlabel("Fraction of samples")
        plt.ylabel("Recall")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(gain_path)
        plt.close()
        artifacts["gain"] = str(gain_path)
    else:
        artifacts = dict.fromkeys(("reliability", "totals", "scorelines", "gain"), "")

    fair_prices = {k: round(1.0 / v, 2) if v > 0 else float("inf") for k, v in {
        "1": sim_result.home_win,
        "X": sim_result.draw,
        "2": sim_result.away_win,
        "BTTS": sim_result.btts,
    }.items()}

    return LevelCMetrics(
        markets={
            "home_win": sim_result.home_win,
            "draw": sim_result.draw,
            "away_win": sim_result.away_win,
            "over_2_5": sim_result.over_2_5,
            "over_3_5": sim_result.over_3_5,
            "btts": sim_result.btts,
            "fair_prices": fair_prices,
        },
        top_scores=sim_result.top_scorelines,
        calibration={
            "over25_curve": {
                "pred": mean_pred.tolist(),
                "observed": frac_pos.tolist(),
            }
        },
        artifacts=artifacts,
    )


def _backtest_metrics(df: pd.DataFrame, diag_dir: Path) -> dict[str, Any]:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["season_week"] = df["date"].dt.isocalendar().week
    df["league"] = df["league_id"]
    df["total_goals"] = df["home_goals"] + df["away_goals"]
    df["btts"] = (df["home_goals"] > 0) & (df["away_goals"] > 0)
    df["over25"] = df["total_goals"] > 2
    df["outcome"] = np.where(df["home_goals"] > df["away_goals"], 0, np.where(df["home_goals"] == df["away_goals"], 1, 2))

    preds = _poisson_1x2_prob(df["lambda_home_true"].to_numpy(), df["lambda_away_true"].to_numpy())
    logloss_val = _safe_log_loss(df["outcome"].to_numpy(), preds)
    brier_val = _multiclass_brier(df["outcome"], preds)
    roc_btts = roc_auc_score(df["btts"].astype(int), preds[:, 0] + preds[:, 2])
    roc_over = roc_auc_score(df["over25"].astype(int), preds[:, 0] + preds[:, 2])

    summary_rows = []
    for (league, week), group in df.groupby(["league", "season_week"]):
        probs = _poisson_1x2_prob(group["lambda_home_true"].to_numpy(), group["lambda_away_true"].to_numpy())
        row = {
            "league": league,
            "week": int(week),
            "matches": len(group),
            "logloss": _safe_log_loss(group["outcome"].to_numpy(), probs),
            "brier": _multiclass_brier(group["outcome"], probs),
            "roc_btts": roc_auc_score(group["btts"].astype(int), probs[:, 0] + probs[:, 2]) if group["btts"].nunique() > 1 else float("nan"),
            "roc_over": roc_auc_score(group["over25"].astype(int), probs[:, 0] + probs[:, 2]) if group["over25"].nunique() > 1 else float("nan"),
        }
        summary_rows.append(row)

    csv_path = diag_dir / "backtest_summary.csv"
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)

    return {
        "aggregate": {
            "logloss": float(logloss_val),
            "brier": float(brier_val),
            "roc_auc_btts": float(roc_btts),
            "roc_auc_over": float(roc_over),
        },
        "csv": str(csv_path),
    }


def _bot_emulation(diag_dir: Path, settings: Any) -> dict[str, Any]:
    from datetime import UTC, datetime

    from app.bot.formatting import (
        format_about,
        format_explain,
        format_help,
        format_match_details,
        format_settings,
        format_start,
        format_today_matches,
    )
    from app.bot.keyboards import match_details_keyboard, today_keyboard
    from app.bot.services import Prediction
    from app.bot.storage import ensure_schema, list_reports, record_report

    ensure_schema()
    now = datetime.now(UTC)
    sample_prediction = Prediction(
        match_id=4242,
        home="Sample FC",
        away="Mock Town",
        league="EPL",
        kickoff=now,
        markets={"1x2": {"home": 0.51, "draw": 0.27, "away": 0.22}},
        totals={"2.5": {"over": 0.61, "under": 0.39}},
        btts={"yes": 0.58, "no": 0.42},
        top_scores=[{"score": "2:1", "probability": 0.13}, {"score": "1:1", "probability": 0.11}],
        lambda_home=1.45,
        lambda_away=1.12,
        expected_goals=2.57,
        fair_odds={"home": 1.96, "draw": 3.7, "away": 4.55},
        confidence=0.68,
        modifiers=[{"name": "Мотивация", "delta": 0.05, "impact": 0.04}],
        delta_probabilities={"home": 0.04, "draw": -0.01, "away": -0.03},
        summary="Форма хозяев выше среднего, защита гостей проседает.",
    )

    timings = {}

    def _timeit(label: str, func: Callable[[], str]) -> str:
        start = time.perf_counter()
        result = func()
        timings[label] = time.perf_counter() - start
        return result

    html_start = _timeit("/start", lambda: format_start("ru", "Europe/Moscow", ["/start", "/today"]))
    html_help = _timeit("/help", format_help)
    today_item = {
        "id": sample_prediction.match_id,
        "home": sample_prediction.home,
        "away": sample_prediction.away,
        "league": sample_prediction.league,
        "kickoff": sample_prediction.kickoff,
        "markets": sample_prediction.markets,
        "confidence": sample_prediction.confidence,
        "totals": sample_prediction.totals,
        "expected_goals": sample_prediction.expected_goals,
    }
    html_today = _timeit(
        "/today",
        lambda: format_today_matches(
            title="Матчи дня",
            timezone="Europe/Moscow",
            items=[today_item],
            page=1,
            total_pages=1,
        ),
    )
    html_match = _timeit(
        "/match",
        lambda: format_match_details(
            {
                "fixture": {
                    "id": sample_prediction.match_id,
                    "home": sample_prediction.home,
                    "away": sample_prediction.away,
                    "league": sample_prediction.league,
                    "kickoff": sample_prediction.kickoff,
                },
                "markets": sample_prediction.markets,
                "totals": sample_prediction.totals,
                "both_teams_to_score": sample_prediction.btts,
                "top_scores": sample_prediction.top_scores,
                "fair_odds": sample_prediction.fair_odds,
                "confidence": sample_prediction.confidence,
            }
        ),
    )
    html_explain = _timeit(
        "/explain",
        lambda: format_explain(
            {
                "id": sample_prediction.match_id,
                "fixture": {"home": sample_prediction.home, "away": sample_prediction.away},
                "lambda_home": sample_prediction.lambda_home,
                "lambda_away": sample_prediction.lambda_away,
                "modifiers": sample_prediction.modifiers,
                "delta_probabilities": sample_prediction.delta_probabilities,
                "confidence": sample_prediction.confidence,
                "summary": sample_prediction.summary,
            }
        ),
    )
    html_settings = _timeit("/settings", lambda: format_settings({"tz": "Europe/Moscow", "lang": "ru"}))
    html_about = _timeit(
        "/about",
        lambda: format_about(
            {
                "version": settings.APP_VERSION,
                "environment": settings.APP_ENV,
                "cache_ttl": settings.CACHE_TTL_SECONDS,
            }
        ),
    )

    keyboard_today = today_keyboard([today_item], query_hash="abc123", page=1, total_pages=1)
    keyboard_match = match_details_keyboard(
        match_id=sample_prediction.match_id,
        query_hash="abc123",
        page=1,
    )

    record_report("diag-report", match_id=sample_prediction.match_id, path="/tmp/report.csv")
    reports = list_reports()

    html_payloads = {
        "start": html_start,
        "help": html_help,
        "today": html_today,
        "match": html_match,
        "explain": html_explain,
        "settings": html_settings,
        "about": html_about,
    }
    html_lengths = {key: len(value) for key, value in html_payloads.items()}

    artifact_path = diag_dir / "bot_payloads.json"
    artifact_path.write_text(json.dumps(html_payloads, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "latency": {key: round(value * 1000, 2) for key, value in timings.items()},
        "html_lengths": html_lengths,
        "reports": reports,
        "keyboards": {
            "today_buttons": len(keyboard_today.inline_keyboard),
            "match_buttons": len(keyboard_match.inline_keyboard),
        },
        "payloads_artifact": str(artifact_path),
        "cache_ttl": getattr(settings, "CACHE_TTL_SECONDS", None),
    }


def _ops_checks(settings: Any, diag_dir: Path) -> dict[str, Any]:
    from app.health import HealthServer
    from app.runtime_lock import RuntimeLock
    from app.runtime_state import STATE

    health = HealthServer(settings.HEALTH_HOST, settings.HEALTH_PORT)
    lock = RuntimeLock(Path(settings.RUNTIME_LOCK_PATH))
    ops_info = {}

    async def _exercise_health() -> None:
        await health.start()
        await asyncio.sleep(0.05)
        reader, writer = await asyncio.open_connection(settings.HEALTH_HOST, settings.HEALTH_PORT)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        data = await reader.read(512)
        writer.close()
        await writer.wait_closed()
        ops_info["health_response"] = data.decode("utf-8", errors="ignore").splitlines()[0]
        STATE.db_ready = True
        STATE.polling_ready = True
        STATE.scheduler_ready = True
        reader2, writer2 = await asyncio.open_connection(settings.HEALTH_HOST, settings.HEALTH_PORT)
        writer2.write(b"GET /ready HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer2.drain()
        data_ready = await reader2.read(512)
        writer2.close()
        await writer2.wait_closed()
        ops_info["ready_response"] = data_ready.decode("utf-8", errors="ignore").splitlines()[0]
        await health.stop()

    async def _exercise_lock() -> None:
        await lock.acquire()
        held = Path(settings.RUNTIME_LOCK_PATH).exists()
        await lock.release()
        ops_info["runtime_lock"] = held

    async def _runner() -> None:
        await _exercise_health()
        await _exercise_lock()

    asyncio.run(_runner())

    backups = list(Path(settings.BACKUP_DIR).glob("*.sqlite3"))
    ops_info["backups"] = [str(p) for p in backups]
    return ops_info


def _write_diagnostics_md(
    diag_dir: Path,
    statuses: dict[str, dict[str, Any]],
    context: dict[str, Any],
    metrics: dict[str, Any],
) -> Path:
    lines = ["# Diagnostics Summary", ""]
    lines.append("| Section | Status | Notes |")
    lines.append("| --- | --- | --- |")
    for section, payload in statuses.items():
        status = payload.get("status", "⚠️")
        note = payload.get("note", "")
        lines.append(f"| {section} | {status} | {note} |")
    freshness = statuses.get("Data Freshness")
    if freshness and freshness.get("leagues"):
        lines.extend(["", "## League Freshness", ""])
        lines.append("| League | Status | Hours |")
        lines.append("| --- | --- | --- |")
        for league_id, payload in sorted(freshness["leagues"].items()):
            hours = payload.get("hours")
            status = payload.get("status", "?")
            if isinstance(hours, float) and math.isfinite(hours):
                hours_repr = f"{hours:.1f}"
            else:
                hours_repr = "n/a"
            lines.append(f"| {league_id} | {status} | {hours_repr} |")
    lines.extend(["", "## Context", ""])
    lines.append("```json")
    lines.append(json.dumps(context, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.extend(["", "## Metrics Snapshot", ""])
    lines.append("```json")
    lines.append(json.dumps(metrics, ensure_ascii=False, indent=2))
    lines.append("```")
    path = diag_dir / "DIAGNOSTICS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_diagnostics_json(
    diag_dir: Path,
    context: dict[str, Any],
    metrics: dict[str, Any],
    statuses: dict[str, dict[str, Any]],
) -> Path:
    payload = {
        "context": context,
        "metrics": metrics,
        "statuses": statuses,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = diag_dir / "diagnostics_report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    with _temp_env({"PYTHONUNBUFFERED": "1", "SPORTMONKS_STUB": "1", "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", "stub-token"), "ODDS_API_KEY": os.getenv("ODDS_API_KEY", "stub-odds")}):
        settings = _load_settings()
    diag_dir = _resolve_reports_dir(settings, args.reports_dir)
    started_at = datetime.now(UTC)

    statuses: dict[str, dict[str, Any]] = {}
    metrics: dict[str, Any] = {}

    entry = _collect_entry_flags()
    env_contract = _collect_env_contract(repo_root)
    statuses["ENV"] = {
        "status": "✅" if not env_contract["missing_in_example"] else "⚠️",
        "note": f"missing_in_example={env_contract['missing_in_example']} extra={env_contract['extra_in_example']}",
    }
    path_notes = _ensure_paths(settings)
    statuses["Paths"] = {"status": "✅", "note": "; ".join(path_notes)}

    base_env = os.environ.copy()
    base_env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "SPORTMONKS_STUB": "1",
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", "stub-token"),
            "ODDS_API_KEY": os.getenv("ODDS_API_KEY", "stub-odds"),
        }
    )

    dataset = _simulate_dataset()
    dataset_hash = hashlib.sha256(pd.util.hash_pandas_object(dataset, index=True).values).hexdigest()
    dq_result = _run_data_quality(dataset, diag_dir)
    statuses["Data Quality"] = {"status": dq_result["status"], "note": dq_result["note"]}
    metrics["data_quality"] = dq_result
    metrics["dataset_hash"] = dataset_hash

    run_only_data_quality = args.data_quality and not args.all
    reports_root = Path(settings.REPORTS_DIR)

    if run_only_data_quality:
        context = {
            "entry": entry,
            "reports_dir": str(diag_dir),
            "settings_snapshot": {
                "DB_PATH": settings.DB_PATH,
                "REPORTS_DIR": settings.REPORTS_DIR,
                "MODEL_REGISTRY_PATH": settings.MODEL_REGISTRY_PATH,
            },
        }
        diag_md = _write_diagnostics_md(diag_dir, statuses, context, metrics)
        diag_json = _write_diagnostics_json(diag_dir, context, metrics, statuses)
        print("Diagnostics complete (data-quality only)")
        print(f"Markdown report: {diag_md}")
        print(f"JSON report: {diag_json}")
        return

    if args.pytest:
        pytest_result = _run_pytest(diag_dir, base_env)
        statuses["Tests"] = {
            "status": "✅" if pytest_result["returncode"] == 0 else "❌",
            "note": f"rc={pytest_result['returncode']} log={pytest_result['log']}",
        }
        metrics["pytest"] = pytest_result

    if not args.skip_smoke:
        smoke_env = base_env.copy()
        smoke_env.update(
            {
                "ENABLE_HEALTH": "1",
                "ENABLE_POLLING": "0",
                "ENABLE_SCHEDULER": "0",
            }
        )
        smoke = _run_smoke(diag_dir, smoke_env)
        statuses["Smoke"] = {
            "status": "✅" if smoke["returncode"] == 0 else "❌",
            "note": f"rc={smoke['returncode']} log={smoke['log']}",
        }
        metrics["smoke"] = smoke

    golden = _run_golden(reports_root)
    statuses["Golden Baseline"] = {"status": golden["status"], "note": golden["note"]}
    metrics["golden"] = golden

    drift = _run_drift(diag_dir, dataset)
    statuses["Drift"] = {"status": drift["status"], "note": drift["note"]}
    metrics["drift"] = drift

    value_diag = _run_value_section(diag_dir, settings)
    statuses["Value & Odds"] = {
        "status": value_diag.get("status", "⚠️"),
        "note": value_diag.get("note", ""),
    }
    metrics["value_odds"] = value_diag
    aggregation_diag = value_diag.get("aggregation", {}) or {}
    aggregation_pairs = int(aggregation_diag.get("pairs", 0))
    statuses["Odds Aggregation"] = {
        "status": "✅" if aggregation_pairs else "⚠️",
        "note": (
            f"pairs={aggregation_pairs} avg={aggregation_diag.get('avg_provider_count', 0.0):.1f}"
            if aggregation_pairs
            else "нет данных"
        ),
    }
    metrics["odds_aggregation"] = aggregation_diag
    reliability_diag = value_diag.get("reliability", {}) or {}
    reliability_entries = int(reliability_diag.get("entries", 0))
    reliability_failures = reliability_diag.get("below_threshold", []) or []
    reliability_warnings = reliability_diag.get("low_samples", []) or []
    if reliability_entries == 0:
        reliability_status = "⚠️"
        reliability_note = "нет данных"
    else:
        reliability_status = "✅"
        reliability_note = (
            f"avg={reliability_diag.get('avg_score', 0.0):.2f}"
            f" min={reliability_diag.get('min_score', 0.0):.2f}"
            f" cov={reliability_diag.get('avg_coverage', 0.0):.2f}"
        )
        if reliability_diag.get("avg_latency_component") is not None:
            reliability_note += (
                f" lat={reliability_diag.get('avg_latency_component', 0.0):.2f}"
            )
        if reliability_failures:
            reliability_status = "❌"
            reliability_note += f" fails={len(reliability_failures)}"
        elif reliability_warnings:
            reliability_status = "⚠️"
            reliability_note += f" warn={len(reliability_warnings)}"
    statuses["Provider Reliability"] = {
        "status": reliability_status,
        "note": reliability_note,
    }
    metrics["provider_reliability"] = reliability_diag
    try:
        probe = list(reliability_v2.get_provider_scores(league="GLOBAL", market="1X2"))
    except Exception as exc:  # pragma: no cover - diagnostic logging only
        statuses["Reliability v2 API"] = {
            "status": "⚠️",
            "note": f"error={exc.__class__.__name__}",
        }
        metrics["reliability_v2_api"] = {"reachable": False, "error": str(exc)}
    else:
        statuses["Reliability v2 API"] = {
            "status": "✅" if probe else "⚠️",
            "note": f"entries={len(probe)}",
        }
        metrics["reliability_v2_api"] = {"reachable": True, "entries": len(probe)}
    best_price_diag = value_diag.get("best_price", {}) or {}
    best_routes = int(best_price_diag.get("routes", 0))
    best_available = int(best_price_diag.get("available", 0))
    if best_available == 0:
        best_status = "⚠️"
        best_note = "нет матчей"
    elif best_routes == 0:
        best_status = "⚠️"
        best_note = f"routes=0/{best_available}"
    else:
        best_status = "✅"
        best_note = (
            f"routes={best_routes}/{best_available}"
            f" avgΔ={best_price_diag.get('avg_improvement_pct', 0.0):.2f}%"
            f" score={best_price_diag.get('avg_score', 0.0):.2f}"
        )
    statuses["Best-Price Routing"] = {"status": best_status, "note": best_note}
    metrics["best_price_routing"] = best_price_diag
    clv_diag = value_diag.get("clv", {}) or {}
    clv_entries = int(clv_diag.get("entries", 0))
    statuses["CLV"] = {
        "status": "✅" if clv_entries else "⚠️",
        "note": (
            f"entries={clv_entries} avg={clv_diag.get('avg_clv', 0.0):.2f}%"
            if clv_entries
            else "нет записей"
        ),
    }
    metrics["clv"] = clv_diag
    settlement_diag = _run_settlement_section(settings)
    statuses["Settlement & ROI"] = {
        "status": settlement_diag["status"],
        "note": settlement_diag["note"],
    }
    metrics["settlement"] = settlement_diag.get("summary", {})

    value_calibration = _run_value_calibration_section(settings)
    statuses["Value Calibration"] = {
        "status": value_calibration["status"],
        "note": value_calibration["note"],
    }
    metrics["value_calibration"] = value_calibration["report"]

    level_a = _train_level_a(dataset, diag_dir)
    statuses["Model Level A"] = {
        "status": "✅",
        "note": f"alpha={level_a.best_alpha} folds={len(level_a.folds)}",
    }

    level_b = _train_modifiers(dataset, level_a, diag_dir)
    statuses["Model Level B"] = {
        "status": "✅",
        "note": f"Δlogloss={level_b.ablation['logloss_mod'] - level_b.ablation['logloss_base']:.4f}",
    }

    level_c = _simulate_level_c(dataset, diag_dir)
    statuses["Model Level C"] = {"status": "✅", "note": f"home_win={level_c.markets['home_win']:.3f}"}

    calibration = _run_calibration_section(dataset, diag_dir)
    statuses["Calibration"] = {"status": calibration["status"], "note": calibration["note"]}
    metrics["calibration"] = calibration

    invariance = _run_invariance_checks(dataset)
    statuses["Bi-Poisson"] = {"status": invariance["status"], "note": invariance["note"]}
    metrics["bipoisson"] = invariance

    backtest = _backtest_metrics(dataset, diag_dir)
    statuses["Backtest"] = {
        "status": "✅",
        "note": f"logloss={backtest['aggregate']['logloss']:.3f} brier={backtest['aggregate']['brier']:.3f}",
    }

    bot_diag = _bot_emulation(diag_dir, settings)
    statuses["Bot UX"] = {
        "status": "✅",
        "note": f"latency_ms≈{statistics.mean(bot_diag['latency'].values()):.1f}",
    }

    ops_diag = _ops_checks(settings, diag_dir)
    statuses["Ops"] = {
        "status": "✅",
        "note": f"health={ops_diag.get('health_response')} ready={ops_diag.get('ready_response')}",
    }

    freshness_diag = evaluate_sportmonks_freshness(settings)
    statuses["Data Freshness"] = {
        "status": freshness_diag["status"],
        "note": freshness_diag.get("note", ""),
        "leagues": freshness_diag.get("leagues", {}),
        "max_hours": freshness_diag.get("max_hours"),
    }
    metrics["sportmonks_freshness"] = freshness_diag

    static_diag = _run_static_analysis(diag_dir)
    statuses["Static Analysis"] = {"status": static_diag["status"], "note": static_diag["note"]}
    metrics["static_analysis"] = static_diag

    bench_result = _run_benchmarks(diag_dir)
    statuses["Benchmarks"] = {"status": bench_result["status"], "note": bench_result["note"]}
    metrics["bench"] = bench_result

    level_a_dict = dataclasses.asdict(level_a)
    level_a_dict["artifact"] = str(level_a.artifact)
    level_b_dict = dataclasses.asdict(level_b)
    level_b_dict["artifact"] = str(level_b.artifact)

    metrics.update(
        {
            "dataset_hash": dataset_hash,
            "env_contract": env_contract,
            "level_a": level_a_dict,
            "level_b": level_b_dict,
            "level_c": {
                "markets": level_c.markets,
                "top_scores": level_c.top_scores,
                "calibration": level_c.calibration,
                "artifacts": level_c.artifacts,
            },
            "backtest": backtest,
            "bot": bot_diag,
            "ops": ops_diag,
        }
    )

    record_diagnostics_summary(
        statuses,
        data_quality_total=dq_result.get("issue_total", 0),
        drift_max=drift.get("psi_max", {}),
        drift_status=drift.get("status_raw", {}),
    )

    context = {
        "entry": entry,
        "reports_dir": str(diag_dir),
        "settings_snapshot": {
            "DB_PATH": settings.DB_PATH,
            "REPORTS_DIR": settings.REPORTS_DIR,
            "MODEL_REGISTRY_PATH": settings.MODEL_REGISTRY_PATH,
        },
    }
    trigger = os.getenv("DIAG_TRIGGER", "manual")
    context["trigger"] = trigger

    diag_md = _write_diagnostics_md(diag_dir, statuses, context, metrics)
    diag_json = _write_diagnostics_json(diag_dir, context, metrics, statuses)
    finished_at = datetime.now(UTC)
    try:
        html_index = reports_html.build_dashboard(
            diag_dir=diag_dir,
            statuses=statuses,
            metrics=metrics,
            context=context,
            trigger=trigger,
            started_at=started_at,
            finished_at=finished_at,
            report_path=diag_md,
        )
        history_entry = reports_html.append_history(
            diag_dir=diag_dir,
            statuses=statuses,
            trigger=trigger,
            keep=getattr(settings, "DIAG_HISTORY_KEEP", 60),
            started_at=started_at,
            finished_at=finished_at,
            html_path=html_index,
        )
        metrics["history_entry"] = dataclasses.asdict(history_entry)
        metrics["html_index"] = str(html_index)
    except Exception as exc:  # pragma: no cover - dashboard failures should not stop diagnostics
        print(f"Failed to build diagnostics dashboard: {exc}")

    print("Diagnostics complete")
    print(f"Markdown report: {diag_md}")
    print(f"JSON report: {diag_json}")


if __name__ == "__main__":
    main()
