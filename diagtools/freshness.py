"""
/**
 * @file: freshness.py
 * @description: Sportmonks data freshness evaluation utilities and CLI.
 * @dependencies: argparse, datetime, json, math, pathlib, sqlite3
 * @created: 2025-02-14
 */
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.data_providers.sportmonks.metrics import sm_freshness_hours_max
from app.data_source import _parse_timestamp


def evaluate_sportmonks_freshness(settings: Any) -> dict[str, Any]:
    warn_hours = float(getattr(settings, "SM_FRESHNESS_WARN_HOURS", 12))
    fail_hours = float(getattr(settings, "SM_FRESHNESS_FAIL_HOURS", 48))
    db_path = Path(settings.DB_PATH)
    if not db_path.exists():
        sm_freshness_hours_max.set(float("inf"))
        return {
            "status": "FAIL",
            "note": "DB missing",
            "max_hours": None,
            "per_table": {},
            "leagues": {},
        }

    tables = ["sm_fixtures", "sm_standings", "sm_injuries", "sm_teams"]
    ages: dict[str, float] = {}
    status = "OK"
    notes: list[str] = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for table in tables:
            try:
                row = conn.execute(
                    f"SELECT pulled_at_utc FROM {table} ORDER BY pulled_at_utc DESC LIMIT 1"
                ).fetchone()
            except sqlite3.Error as exc:  # pragma: no cover - defensive
                ages[table] = float("inf")
                status = "FAIL"
                notes.append(f"{table}=error:{exc}")
                continue
            if not row or not row[0]:
                ages[table] = float("inf")
                status = "FAIL"
                notes.append(f"{table}=empty")
                continue
            pulled = _parse_timestamp(row[0])
            if isinstance(pulled, datetime):
                age_hours = (datetime.now(tz=UTC) - pulled).total_seconds() / 3600
            else:
                age_hours = float("inf")
            ages[table] = age_hours
            if age_hours > fail_hours:
                status = "FAIL"
            elif age_hours > warn_hours and status == "OK":
                status = "WARN"
            notes.append(f"{table}={age_hours:.1f}h")

        league_rows = conn.execute(
            "SELECT league_id, MAX(pulled_at_utc) AS pulled FROM sm_fixtures GROUP BY league_id"
        ).fetchall()
    finally:
        conn.close()

    league_summary: dict[str, dict[str, Any]] = {}
    for row in league_rows:
        league_id = str(row["league_id"]) if row["league_id"] is not None else "unknown"
        pulled_raw = row["pulled"]
        pulled_dt = _parse_timestamp(pulled_raw)
        if isinstance(pulled_dt, datetime):
            hours = (datetime.now(tz=UTC) - pulled_dt).total_seconds() / 3600
        else:
            hours = float("inf")
        if hours > fail_hours:
            league_status = "FAIL"
        elif hours > warn_hours:
            league_status = "WARN"
        else:
            league_status = "OK"
        league_summary[league_id] = {"hours": hours, "status": league_status}

    max_age = max(ages.values()) if ages else float("inf")
    sm_freshness_hours_max.set(max_age if math.isfinite(max_age) else 0.0)

    return {
        "status": status,
        "note": "; ".join(notes),
        "max_hours": max_age,
        "per_table": ages,
        "leagues": league_summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Sportmonks data freshness")
    parser.add_argument("--json", action="store_true", help="Print result as JSON")
    parser.add_argument("--check", action="store_true", help="Return non-zero exit for WARN/FAIL")
    args = parser.parse_args(argv)

    from config import settings  # pylint: disable=import-outside-toplevel

    result = evaluate_sportmonks_freshness(settings)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {result['status']}")
        print(result.get("note", ""))
        if result.get("leagues"):
            print("Leagues:")
            for league_id, payload in sorted(result["leagues"].items()):
                hours = payload.get("hours")
                status = payload.get("status")
                if isinstance(hours, float) and math.isfinite(hours):
                    print(f"  {league_id}: {status} ({hours:.1f}h)")
                else:
                    print(f"  {league_id}: {status} (n/a)")

    if result["status"] == "FAIL":
        return 2
    if result["status"] == "WARN" and args.check:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
