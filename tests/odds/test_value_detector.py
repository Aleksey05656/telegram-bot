"""
@file: tests/odds/test_value_detector.py
@description: Tests for value detector filtering, edge computation and sorting.
@dependencies: datetime, app.value_detector
@created: 2025-09-24
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.lines.providers.base import OddsSnapshot
from app.value_detector import ModelOutcome, ValueDetector


def _snapshot(match_key: str, market: str, selection: str, price: float) -> OddsSnapshot:
    return OddsSnapshot(
        provider="csv",
        pulled_at=datetime(2024, 9, 1, 10, tzinfo=UTC),
        match_key=match_key,
        league="EPL",
        kickoff_utc=datetime(2024, 9, 1, 18, tzinfo=UTC),
        market=market,
        selection=selection,
        price_decimal=price,
    )


def test_value_detector_filters_and_sorts() -> None:
    detector = ValueDetector(
        min_edge_pct=5.0,
        min_confidence=0.5,
        max_picks=2,
        markets=("1X2",),
        overround_method="proportional",
    )
    match_key = "arsenal|manchester-city|2024-09-01T18:00Z"
    model = [
        ModelOutcome(match_key=match_key, market="1X2", selection="HOME", probability=0.45, confidence=0.7),
        ModelOutcome(match_key=match_key, market="1X2", selection="DRAW", probability=0.30, confidence=0.7),
        ModelOutcome(match_key=match_key, market="1X2", selection="AWAY", probability=0.25, confidence=0.7),
    ]
    odds = [
        _snapshot(match_key, "1X2", "HOME", 1.90),
        _snapshot(match_key, "1X2", "DRAW", 3.80),
        _snapshot(match_key, "1X2", "AWAY", 4.20),
    ]
    picks = detector.detect(model=model, market=odds)
    assert len(picks) == 1
    pick = picks[0]
    assert pick.selection == "HOME"
    assert pick.edge_pct > 5.0
    assert pick.market_probability > 0
