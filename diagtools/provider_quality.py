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
    payload: list[dict[str, Any]] = [record.__dict__ for record in records]
    (reports_dir / "provider_quality.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = ["# Provider Quality", ""]
    for record in records:
        lines.append(
            "* {provider}/{market}/{league}: score={score:.2f} coverage={coverage:.2f} fresh={fresh_share:.2f} lag={lag_ms:.0f}ms".format(
                **record.__dict__,
            )
        )
    (reports_dir / "provider_quality.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    records = _load_provider_stats(str(args.db_path))
    _write_reports(records, Path(args.reports_dir))
    if not records:
        print("provider_quality: no records")
        raise SystemExit(1)
    failing = [
        record
        for record in records
        if record.score < float(args.min_score) or record.coverage < float(args.min_coverage)
    ]
    print(
        f"provider_quality: {len(records)} entries, min_score={args.min_score}, min_coverage={args.min_coverage}"
    )
    if failing:
        print(
            "failing providers: "
            + ", ".join(f"{item.provider}/{item.market}" for item in failing[:5])
        )
        raise SystemExit(2)
    raise SystemExit(0)


if __name__ == "__main__":
    main()

