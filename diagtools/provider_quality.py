"""
/**
 * @file: diagtools/provider_quality.py
 * @description: CLI to validate provider reliability scores and export diagnostics.
 * @dependencies: argparse, json, sqlite3, config
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings


@dataclass(slots=True)
class ProviderRecord:
    provider: str
    market: str
    league: str
    score: float
    coverage: float
    fresh_share: float
    lag_ms: float
    status: str = "OK"

    @property
    def latency_ms(self) -> float:
        return float(self.lag_ms)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check provider reliability scores")
    parser.add_argument(
        "--db-path",
        default=getattr(settings, "DB_PATH", "/data/bot.sqlite3"),
        help="SQLite database with provider_stats table",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=float(getattr(settings, "RELIABILITY_MIN_SCORE", 0.5)),
        help="Minimum acceptable reliability score",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=float(getattr(settings, "RELIABILITY_MIN_COVERAGE", 0.6)),
        help="Minimum acceptable coverage share",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=int(getattr(settings, "RELIAB_MIN_SAMPLES", 0)),
        help="Legacy compatibility flag; retained for CLI stability",
    )
    parser.add_argument(
        "--min-fresh-share",
        type=float,
        default=float(getattr(settings, "RELIABILITY_MIN_FRESH_SHARE", 0.5)),
        help="Minimum acceptable fresh share",
    )
    parser.add_argument(
        "--max-lag-ms",
        type=float,
        default=float(getattr(settings, "RELIABILITY_MAX_LAG_MS", 600.0)),
        help="Maximum acceptable latency in milliseconds",
    )
    parser.add_argument(
        "--reports-dir",
        default=Path(getattr(settings, "REPORTS_DIR", "/data/reports")) / "diagnostics",
        help="Directory for generated reports",
    )
    return parser.parse_args(argv)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_provider_stats(db_path: str) -> list[ProviderRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT provider, market, league, score, coverage, fresh_share, lag_ms
              FROM provider_stats
            """,
        ).fetchall()
    return [
        ProviderRecord(
            provider=str(row["provider"]),
            market=str(row["market"]),
            league=str(row["league"]),
            score=float(row["score"]),
            coverage=float(row["coverage"]),
            fresh_share=float(row["fresh_share"]),
            lag_ms=float(row["lag_ms"]),
        )
        for row in rows
    ]


def _write_reports(records: list[ProviderRecord], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload: list[dict[str, Any]] = [
        {
            "provider": r.provider,
            "market": r.market,
            "league": r.league,
            "score": r.score,
            "coverage": r.coverage,
            "fresh_share": r.fresh_share,
            "latency_ms": r.latency_ms,
            "status": r.status,
        }
        for r in records
    ]
    (reports_dir / "provider_quality.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = ["# Provider Quality", ""]
    lines.append("| Provider | League | Market | Score | Coverage | Fresh share | Lag ms | Status |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
    for record in records:
        lines.append(
            f"| {record.provider} | {record.league} | {record.market} | "
            f"{record.score:.3f} | {record.coverage:.2f} | {record.fresh_share:.2f} | "
            f"{record.latency_ms:.0f} | {record.status} |"
        )
    (reports_dir / "provider_quality.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    records = _load_provider_stats(str(args.db_path))
    if not records:
        print("provider_quality: no records")
        raise SystemExit(0)
    min_score = float(args.min_score)
    min_coverage = float(args.min_coverage)
    min_samples = int(getattr(args, "min_samples", 0))
    min_fresh_share = float(getattr(args, "min_fresh_share", 0.0))
    max_lag_ms = float(getattr(args, "max_lag_ms", float("inf")))
    failures: list[ProviderRecord] = []
    for record in records:
        status = "OK"
        if record.score < min_score or record.coverage < min_coverage:
            status = "FAIL"
        if record.fresh_share < min_fresh_share or record.lag_ms > max_lag_ms:
            status = "FAIL"
        record.status = status
        if status == "FAIL":
            failures.append(record)
    _write_reports(records, Path(args.reports_dir))
    summary = (
        "provider_quality: {count} entries, min_score={min_score:.2f}, "
        "min_coverage={min_cov:.2f}, min_fresh_share={min_fresh:.2f}, max_lag_ms={max_lag:.0f}, "
        "min_samples={min_samples}"
    ).format(
        count=len(records),
        min_score=min_score,
        min_cov=min_coverage,
        min_fresh=min_fresh_share,
        max_lag=max_lag_ms,
        min_samples=min_samples,
    )
    print(summary)
    if failures:
        names = ", ".join(
            f"{item.provider}/{item.league}/{item.market}" for item in failures[:5]
        )
        print(f"failing providers: {names}")
        raise SystemExit(2)
    raise SystemExit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"provider_quality: unexpected error: {exc}")
        raise SystemExit(1)

