"""
/**
 * @file: diagtools/settlement_check.py
 * @description: CLI to validate settlement coverage and ROI health.
 * @dependencies: argparse, json, sqlite3, datetime, config
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from config import settings


@dataclass(slots=True)
class SettlementSummary:
    total: int
    settled: int
    coverage: float
    avg_roi: float
    window_roi: float


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check settlement coverage and ROI")
    parser.add_argument(
        "--db-path",
        default=getattr(settings, "DB_PATH", "/data/bot.sqlite3"),
        help="SQLite database containing picks_ledger",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.6,
        help="Minimum acceptable settlement coverage",
    )
    parser.add_argument(
        "--roi-threshold",
        type=float,
        default=-5.0,
        help="Minimum acceptable ROI in percent",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=int(getattr(settings, "PORTFOLIO_ROLLING_DAYS", 60)),
        help="Rolling window in days for ROI check",
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


def _load_summary(db_path: str, window_days: int) -> SettlementSummary:
    with _connect(db_path) as conn:
        totals = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END) AS settled,
                   AVG(roi) AS avg_roi
              FROM picks_ledger
            """,
        ).fetchone()
        cutoff = datetime.now(UTC) - timedelta(days=max(window_days, 1))
        window_row = conn.execute(
            """
            SELECT AVG(roi) AS avg_roi
              FROM picks_ledger
             WHERE outcome IS NOT NULL
               AND created_at >= ?
            """,
            (_to_iso(cutoff),),
        ).fetchone()
    total = int(totals["total"] or 0)
    settled = int(totals["settled"] or 0)
    coverage = settled / total if total else 0.0
    avg_roi = float(totals["avg_roi"]) if totals["avg_roi"] is not None else 0.0
    window_roi = float(window_row["avg_roi"]) if window_row and window_row["avg_roi"] is not None else 0.0
    return SettlementSummary(
        total=total,
        settled=settled,
        coverage=coverage,
        avg_roi=avg_roi,
        window_roi=window_roi,
    )


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _write_reports(summary: SettlementSummary, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "total": summary.total,
        "settled": summary.settled,
        "coverage": summary.coverage,
        "avg_roi": summary.avg_roi,
        "window_roi": summary.window_roi,
    }
    (reports_dir / "settlement_check.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# Settlement Summary",
        "",
        f"* Picks: {summary.total}",
        f"* Settled: {summary.settled}",
        f"* Coverage: {summary.coverage * 100:.1f}%",
        f"* ROI overall: {summary.avg_roi:.2f}%",
        f"* ROI window: {summary.window_roi:.2f}%",
    ]
    (reports_dir / "settlement_check.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    summary = _load_summary(str(args.db_path), int(args.window_days))
    _write_reports(summary, Path(args.reports_dir))
    if summary.total == 0:
        print("settlement_check: no picks")
        raise SystemExit(1)
    print(
        "settlement_check: total={total} settled={settled} coverage={coverage:.2f} avg_roi={avg_roi:.2f}% window_roi={window_roi:.2f}%".format(
            **summary.__dict__,
        )
    )
    if summary.coverage < float(args.min_coverage) or summary.window_roi < float(args.roi_threshold):
        raise SystemExit(2)
    raise SystemExit(0)


if __name__ == "__main__":
    main()

