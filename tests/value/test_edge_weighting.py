"""
/**
 * @file: tests/value/test_edge_weighting.py
 * @description: Validate Monte Carlo confidence weighting inside ValueDetector.
 * @dependencies: app.value_detector, app.lines.providers.base
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.lines.providers.base import OddsSnapshot
from app.value_detector import ModelOutcome, ValueDetector


def _snapshot(match_key: str, market: str, selection: str, price: float) -> OddsSnapshot:
    now = datetime.now(UTC)
    return OddsSnapshot(
        provider="stub",
        pulled_at=now,
        match_key=match_key,
        league="L1",
        kickoff_utc=now + timedelta(hours=6),
        market=market,
        selection=selection,
        price_decimal=price,
    )


def test_weighted_edge_prefers_higher_confidence() -> None:
    detector = ValueDetector(
        min_edge_pct=0.0,
        min_confidence=0.0,
        max_picks=10,
        markets=("1X2",),
        overround_method="proportional",
        confidence_method="mc_var",
        calibration=None,
    )
    model = [
        ModelOutcome(
            match_key="m1",
            market="1X2",
            selection="HOME",
            probability=0.55,
            confidence=0.9,
            probability_variance=0.1,
        ),
        ModelOutcome(
            match_key="m2",
            market="1X2",
            selection="HOME",
            probability=0.5,
            confidence=0.9,
            probability_variance=1.5,
        ),
    ]
    market = [
        _snapshot("m1", "1X2", "HOME", price=2.1),
        _snapshot("m2", "1X2", "HOME", price=2.4),
    ]
    picks = detector.detect(model=model, market=market)
    assert len(picks) == 2
    first, second = picks
    assert first.match_key == "m1"
    assert first.edge_weighted_pct > second.edge_weighted_pct
    assert first.edge_weighted_pct == pytest.approx(first.edge_pct * first.confidence)
    assert first.confidence == pytest.approx(1 / (1 + 0.1))
    assert second.confidence == pytest.approx(1 / (1 + 1.5))
