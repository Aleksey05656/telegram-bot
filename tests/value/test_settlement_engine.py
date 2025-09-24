"""
/**
 * @file: tests/value/test_settlement_engine.py
 * @description: Unit tests for settlement engine covering 1X2, OU and BTTS outcomes with ROI.
 * @dependencies: datetime, sqlite3, app.settlement.engine
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from app.settlement.engine import FixtureResult, SettlementEngine


class DummyResultsProvider:
    def __init__(self, mapping: dict[str, FixtureResult]) -> None:
        self._mapping = mapping

    def fetch(self, match_keys: list[str]) -> dict[str, FixtureResult]:
        return {key: self._mapping[key] for key in match_keys if key in self._mapping}


def _create_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE picks_ledger (
            id INTEGER PRIMARY KEY,
            match_key TEXT NOT NULL,
            market TEXT NOT NULL,
            selection TEXT NOT NULL,
            price_taken REAL NOT NULL,
            provider_price_decimal REAL NOT NULL,
            consensus_price_decimal REAL NOT NULL,
            kickoff_utc TEXT NOT NULL,
            clv_pct REAL NULL,
            closing_price REAL NULL,
            outcome TEXT NULL,
            roi REAL NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_settlement_engine_updates_outcomes_and_roi(tmp_path) -> None:
    db_path = tmp_path / "settlement.sqlite3"
    conn = _create_db(str(db_path))
    now = datetime(2025, 10, 7, 12, 0, tzinfo=UTC)
    kickoff_past = now - timedelta(hours=5)

    rows = [
        (
            1,
            "match-1",
            "1X2",
            "HOME",
            2.2,
            2.2,
            2.0,
            _iso(kickoff_past),
            None,
            2.0,
            None,
            None,
            _iso(now - timedelta(hours=1)),
        ),
        (
            2,
            "match-1",
            "1X2",
            "AWAY",
            3.5,
            3.5,
            3.1,
            _iso(kickoff_past),
            -2.5,
            None,
            None,
            None,
            _iso(now - timedelta(hours=1)),
        ),
        (
            3,
            "match-2",
            "OU_2_0",
            "OVER",
            1.9,
            1.9,
            1.8,
            _iso(kickoff_past),
            None,
            None,
            None,
            None,
            _iso(now - timedelta(hours=2)),
        ),
        (
            4,
            "match-3",
            "BTTS",
            "YES",
            1.85,
            1.85,
            1.75,
            _iso(kickoff_past),
            4.0,
            None,
            None,
            None,
            _iso(now - timedelta(hours=3)),
        ),
    ]
    conn.executemany(
        """
        INSERT INTO picks_ledger(
            id, match_key, market, selection, price_taken,
            provider_price_decimal, consensus_price_decimal,
            kickoff_utc, clv_pct, closing_price, outcome, roi, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    results = {
        "match-1": FixtureResult(match_key="match-1", home_score=2, away_score=1),
        "match-2": FixtureResult(match_key="match-2", home_score=1, away_score=1),
        "match-3": FixtureResult(match_key="match-3", home_score=0, away_score=0),
    }

    engine = SettlementEngine(results_provider=DummyResultsProvider(results), db_path=str(db_path))
    settled = engine.settle()
    assert settled == 4

    with sqlite3.connect(db_path) as check_conn:
        check_conn.row_factory = sqlite3.Row
        stored = check_conn.execute("SELECT * FROM picks_ledger ORDER BY id").fetchall()

    outcomes = [row["outcome"] for row in stored]
    assert outcomes == ["win", "lose", "push", "lose"]

    roi_values = [row["roi"] for row in stored]
    assert roi_values == [120.0, -100.0, 0.0, -100.0]

    clv_updated = stored[0]["clv_pct"]
    assert clv_updated is not None and round(clv_updated, 2) == 10.0
    assert stored[1]["clv_pct"] == -2.5  # не перезаписывается при наличии значения
