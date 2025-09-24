"""
/**
 * @file: tests/value/test_clv_math.py
 * @description: Tests for CLV calculation and picks ledger persistence.
 * @dependencies: datetime, app.value_clv
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.lines.aggregator import ConsensusMeta, ProviderQuote
from app.value_clv import PicksLedgerStore, calculate_clv


@dataclass(slots=True)
class _ValuePick:
    match_key: str
    market: str
    selection: str
    league: str | None
    fair_price: float
    market_price: float
    edge_pct: float
    model_probability: float
    market_probability: float
    confidence: float
    edge_weighted_pct: float
    edge_threshold_pct: float
    confidence_threshold: float
    calibrated: bool
    provider: str
    pulled_at: datetime
    kickoff_utc: datetime


def _value_pick() -> _ValuePick:
    kickoff = datetime(2025, 10, 12, 17, 0, tzinfo=UTC)
    pulled = kickoff - timedelta(hours=5)
    return _ValuePick(
        match_key="m-3",
        market="1X2",
        selection="HOME",
        league="EPL",
        fair_price=1.95,
        market_price=2.1,
        edge_pct=5.0,
        model_probability=0.51,
        market_probability=0.48,
        confidence=0.8,
        edge_weighted_pct=4.0,
        edge_threshold_pct=3.0,
        confidence_threshold=0.6,
        calibrated=True,
        provider="consensus",
        pulled_at=pulled,
        kickoff_utc=kickoff,
    )


def _consensus_meta(closing_price: float) -> ConsensusMeta:
    kickoff = datetime(2025, 10, 12, 17, 0, tzinfo=UTC)
    closing_time = kickoff - timedelta(minutes=15)
    providers = (
        ProviderQuote(provider="a", price_decimal=2.1, pulled_at=closing_time),
    )
    return ConsensusMeta(
        match_key="m-3",
        market="1X2",
        selection="HOME",
        price_decimal=2.1,
        probability=0.48,
        method="median",
        provider_count=1,
        providers=providers,
        trend="↘︎",
        pulled_at=closing_time,
        league="EPL",
        kickoff_utc=kickoff,
        closing_price=closing_price,
        closing_pulled_at=closing_time,
    )


def _init_schema(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS picks_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                match_key TEXT NOT NULL,
                market TEXT NOT NULL,
                selection TEXT NOT NULL,
                stake REAL NOT NULL,
                price_taken REAL NOT NULL,
                model_probability REAL NOT NULL,
                market_probability REAL NOT NULL,
                edge_pct REAL NOT NULL,
                confidence REAL NOT NULL,
                pulled_at_utc TEXT NOT NULL,
                kickoff_utc TEXT NOT NULL,
                consensus_price REAL NOT NULL,
                consensus_method TEXT NOT NULL,
                consensus_provider_count INTEGER NOT NULL,
                clv_pct REAL NULL,
                closing_price REAL NULL,
                closing_pulled_at TEXT NULL,
                closing_method TEXT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, match_key, market, selection, pulled_at_utc)
            );
            CREATE TABLE IF NOT EXISTS closing_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_key TEXT NOT NULL,
                market TEXT NOT NULL,
                selection TEXT NOT NULL,
                consensus_price REAL NOT NULL,
                consensus_probability REAL NOT NULL,
                provider_count INTEGER NOT NULL,
                method TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(match_key, market, selection)
            );
            """
        )


def test_calculate_clv_formula() -> None:
    assert calculate_clv(2.0, 1.8) == pytest.approx((2.0 / 1.8 - 1.0) * 100.0)


def test_ledger_records_clv(tmp_path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    store = PicksLedgerStore(db_path=str(db_path))
    _init_schema(str(db_path))
    pick = _value_pick()
    consensus = _consensus_meta(closing_price=1.85)
    store.record_pick(1, pick, consensus)
    store.record_closing_line(consensus)
    store.apply_closing_to_picks(consensus)
    rows = store.list_user_picks(1)
    assert len(rows) == 1
    entry = rows[0]
    expected_clv = calculate_clv(float(entry["price_taken"]), 1.85)
    assert entry["closing_price"] == 1.85
    assert entry["closing_method"] == "median"
    assert pytest.approx(float(entry["clv_pct"]), rel=1e-6) == expected_clv
