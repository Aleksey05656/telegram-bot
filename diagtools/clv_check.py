"""
/**
 * @file: diagtools/clv_check.py
 * @description: CLI tool validating picks ledger CLV health and generating diagnostics reports.
 * @dependencies: argparse, json, sqlite3, config, app.value_clv
 * @created: 2025-10-05
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
class ClvSummary:
    entries: int
    avg_clv: float
    positive_share: float


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check picks ledger CLV health")
    parser.add_argument(
        "--db-path",
        default=getattr(settings, "DB_PATH", "/data/bot.sqlite3"),
        help="Path to SQLite database with picks_ledger table",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(getattr(settings, "CLV_FAIL_THRESHOLD_PCT", -5.0)),
        help="Minimum acceptable average CLV in percent",
    )
    parser.add_argument(
        "--reports-dir",
        default=Path(getattr(settings, "REPORTS_DIR", "/data/reports")) / "diagnostics",
        help="Directory to store MD/JSON reports",
    )
    return parser.parse_args(argv)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_summary(db_path: str) -> ClvSummary:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT clv_pct FROM picks_ledger
            WHERE clv_pct IS NOT NULL
            """
        ).fetchall()
    values = [float(row["clv_pct"]) for row in rows]
    if not values:
        return ClvSummary(entries=0, avg_clv=0.0, positive_share=0.0)
    avg = sum(values) / len(values)
    positive = sum(1 for value in values if value >= 0.0) / len(values)
    return ClvSummary(entries=len(values), avg_clv=avg, positive_share=positive)


def _write_reports(summary: ClvSummary, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "entries": summary.entries,
        "avg_clv": summary.avg_clv,
        "positive_share": summary.positive_share,
    }
    json_path = reports_dir / "value_clv.json"
    md_path = reports_dir / "value_clv.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Value CLV Summary",
        "",
        f"* Entries: {summary.entries}",
        f"* Average CLV: {summary.avg_clv:.2f}%",
        f"* Positive share: {summary.positive_share * 100:.1f}%",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    reports_dir = Path(args.reports_dir)
    summary = _load_summary(str(args.db_path))
    _write_reports(summary, reports_dir)
    print(
        f"CLV summary: entries={summary.entries} avg={summary.avg_clv:.2f}% "
        f"positive={summary.positive_share * 100:.1f}%"
    )
    if summary.entries == 0:
        raise SystemExit(1)
    if summary.avg_clv < float(args.threshold):
        raise SystemExit(2)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
