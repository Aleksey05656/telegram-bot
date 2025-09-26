"""
/**
 * @file: tests/odds/test_reliability_v2_bayes.py
 * @description: Unit tests for Bayesian provider reliability tracker (freshness, latency, decay, closing bias).
 * @dependencies: datetime, pytest, app.lines.reliability_v2, app.lines.providers.base, app.lines.storage
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.lines.providers.base import OddsSnapshot
from app.lines.reliability_v2 import ProviderReliabilityStoreV2, ProviderReliabilityV2
from app.lines.storage import LineHistoryPoint


def _quote(
    provider: str,
    pulled_at: datetime,
    *,
    price: float = 2.0,
) -> OddsSnapshot:
    return OddsSnapshot(
        provider=provider,
        pulled_at=pulled_at,
        match_key="match-1",
        league="EPL",
        kickoff_utc=pulled_at + timedelta(hours=2),
        market="1X2",
        selection="HOME",
        price_decimal=price,
        extra={},
    )


def test_bayesian_components_and_decay(tmp_path: Path) -> None:
    db_path = tmp_path / "rel.sqlite"
    store = ProviderReliabilityStoreV2(db_path=str(db_path))
    tracker = ProviderReliabilityV2(
        store=store,
        decay=0.5,
        prior_fresh_alpha=1.0,
        prior_fresh_beta=1.0,
        prior_latency_shape=1.0,
        prior_latency_scale=100.0,
        stability_z_tol=1.0,
        closing_tol_pct=1.0,
        min_samples=0,
    )
    now = datetime.now(UTC)
    fresh_quote = _quote("alpha", now)
    tracker.observe_event(
        match_key="match-1",
        market="1X2",
        league="EPL",
        quotes=[fresh_quote],
        expected_providers=["alpha"],
        reference_price=2.0,
        observed_at=now,
    )
    stats = tracker.get("alpha", "1X2", "EPL")
    assert stats is not None
    assert pytest.approx(stats.fresh_component, rel=1e-6) == pytest.approx(2 / 3, rel=1e-6)
    assert pytest.approx(stats.latency_component, rel=1e-6) == 0.5
    assert stats.samples == 1

    # Second observation: stale quote with long latency triggers decay and lowers freshness expectation.
    later = now + timedelta(minutes=30)
    stale_quote = _quote("alpha", later - timedelta(minutes=20))
    tracker.observe_event(
        match_key="match-1",
        market="1X2",
        league="EPL",
        quotes=[stale_quote],
        expected_providers=["alpha"],
        reference_price=2.0,
        observed_at=later,
    )
    stats = tracker.get("alpha", "1X2", "EPL")
    assert stats is not None
    # Decay drops previous success before adding a stale failure => posterior mean shrinks.
    assert stats.samples == 1  # previous sample decayed away before increment
    assert stats.fresh_component < 0.4
    # Latency component is heavily penalised by the long gap.
    assert stats.latency_component < 0.01

    closing_time = later + timedelta(minutes=5)
    history = [
        LineHistoryPoint(provider="alpha", pulled_at=closing_time - timedelta(minutes=4), price_decimal=1.99),
        LineHistoryPoint(provider="beta", pulled_at=closing_time - timedelta(minutes=3), price_decimal=2.15),
    ]
    tracker.observe_closing(
        match_key="match-1",
        market="1X2",
        league="EPL",
        selection="HOME",
        closing_price=2.0,
        closing_pulled_at=closing_time,
        history=history,
    )
    stats = tracker.get("alpha", "1X2", "EPL")
    assert stats is not None
    assert stats.closing_total == 1
    assert stats.closing_within_tol == 1

    # Re-processing the same closing should not double count thanks to deduplication.
    tracker.observe_closing(
        match_key="match-1",
        market="1X2",
        league="EPL",
        selection="HOME",
        closing_price=2.0,
        closing_pulled_at=closing_time,
        history=history,
    )
    stats = tracker.get("alpha", "1X2", "EPL")
    assert stats is not None
    assert stats.closing_total == 1
    assert stats.closing_within_tol == 1
