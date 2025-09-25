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
    samples: int
    fresh_success: int
    fresh_fail: int
    latency_sum_ms: float
    status: str = "OK"

    @property
    def coverage(self) -> float:
        total = max(self.samples, 1)
        return float(self.fresh_success) / float(total)

    @property
    def latency_ms(self) -> float:
        successes = max(self.fresh_success, 1)
        return float(self.latency_sum_ms) / float(successes)


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
        default=int(getattr(settings, "RELIAB_MIN_SAMPLES", 200)),
        help="Minimum decayed sample size before enforcing fail gates",
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
            SELECT provider, market, league, score, samples, fresh_success,
                   fresh_fail, latency_sum_ms
              FROM provider_stats
            """,
        ).fetchall()
    return [
        ProviderRecord(
            provider=str(row["provider"]),
            market=str(row["market"]),
            league=str(row["league"]),
            score=float(row["score"]),
            samples=int(row["samples"]),
            fresh_success=int(row["fresh_success"]),
            fresh_fail=int(row["fresh_fail"]),
            latency_sum_ms=float(row["latency_sum_ms"]),
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
            "samples": r.samples,
            "fresh_success": r.fresh_success,
            "fresh_fail": r.fresh_fail,
            "coverage": r.coverage,
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
    lines.append("| Provider | League | Market | Score | Coverage | Latency ms | Samples | Status |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
    for record in records:
        lines.append(
            f"| {record.provider} | {record.league} | {record.market} | "
            f"{record.score:.3f} | {record.coverage:.2f} | {record.latency_ms:.0f} | "
            f"{record.samples} | {record.status} |"
        )
    (reports_dir / "provider_quality.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    records = _load_provider_stats(str(args.db_path))
    if not records:
        print("provider_quality: no records")
        raise SystemExit(1)
    min_score = float(args.min_score)
    min_coverage = float(args.min_coverage)
    min_samples = int(args.min_samples)
    failures: list[ProviderRecord] = []
    warnings: list[ProviderRecord] = []
    for record in records:
        status = "OK"
        if record.samples < min_samples:
            status = "WARN"
        if record.coverage < min_coverage:
            status = "WARN"
        if record.score < min_score:
            status = "FAIL"
        record.status = status
        if status == "FAIL":
            failures.append(record)
        elif status == "WARN":
            warnings.append(record)
    _write_reports(records, Path(args.reports_dir))
    summary = (
        f"provider_quality: {len(records)} entries, min_score={min_score}, min_coverage={min_coverage},"
        f" min_samples={min_samples}"
    )
    print(summary)
    if failures:
        print(
            "FAIL: "
            + ", ".join(
                f"{item.provider}/{item.league}/{item.market}" for item in failures[:5]
            )
        )
        raise SystemExit(2)
    if warnings:
        print(
            "WARN: "
            + ", ".join(
                f"{item.provider}/{item.league}/{item.market}" for item in warnings[:5]
            )
        )
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()

