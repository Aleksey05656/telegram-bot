"""
/**
 * @file: tests/odds/test_movement_closing.py
 * @description: Tests for closing line selection and trend detection in LinesAggregator.
 * @dependencies: datetime, pathlib, app.lines.aggregator
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.lines.aggregator import LinesAggregator
from app.lines.providers.base import OddsSnapshot
from app.lines.storage import OddsSQLiteStore


def _fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "odds_multi"


def _snapshot(provider: str, price: float, kickoff: datetime, minutes_before: int) -> OddsSnapshot:
    pulled = kickoff - timedelta(minutes=minutes_before)
    return OddsSnapshot(
        provider=provider,
        pulled_at=pulled,
        match_key="m-2",
        league="EPL",
        kickoff_utc=kickoff,
        market="1X2",
        selection="HOME",
        price_decimal=price,
        extra=None,
    )


def test_closing_line_detected(tmp_path) -> None:
    db_path = tmp_path / "odds.sqlite3"
    store = OddsSQLiteStore(db_path=str(db_path))
    kickoff = datetime(2025, 10, 10, 20, 0, tzinfo=UTC)
    aggregator = LinesAggregator(
        method="median",
        store=store,
        retention_days=7,
        movement_window_minutes=120,
    )
    path = _fixtures_dir() / "movement_closing.csv"
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        early_quotes = [
            _snapshot(row["provider"], float(row["price_decimal"]), kickoff, int(row["minutes_before"]))
            for row in reader
            if row["stage"] == "early"
        ]
    aggregator.aggregate(early_quotes)
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        closing_quotes = [
            _snapshot(row["provider"], float(row["price_decimal"]), kickoff, int(row["minutes_before"]))
            for row in reader
            if row["stage"] == "closing"
        ]
    result = aggregator.aggregate(closing_quotes)
    consensus = result[0]
    payload = consensus.extra["consensus"]
    assert payload["trend"] == "↘︎"
    assert payload["closing_price"] == 1.85
    assert payload["closing_pulled_at"].endswith("Z")
    # Re-running with same closing data should keep closing price stable
    result_repeat = aggregator.aggregate(closing_quotes)
    repeat_payload = result_repeat[0].extra["consensus"]
    assert repeat_payload["closing_price"] == 1.85
