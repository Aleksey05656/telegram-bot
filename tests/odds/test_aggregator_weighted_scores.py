"""
/**
 * @file: tests/odds/test_aggregator_weighted_scores.py
 * @description: Tests LinesAggregator weighted mode driven by reliability v2 scores and best-price filtering.
 * @dependencies: datetime, pytest, app.lines.aggregator, app.lines.providers.base, app.lines.reliability_v2, app.lines.storage
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.lines.aggregator import LinesAggregator
from app.lines.providers.base import OddsSnapshot
from app.lines.reliability_v2 import ProviderReliabilityStoreV2, ProviderReliabilityV2
from app.lines.storage import OddsSQLiteStore
from config import settings


def _snapshot(
    provider: str,
    pulled_at: datetime,
    *,
    price: float,
) -> OddsSnapshot:
    return OddsSnapshot(
        provider=provider,
        pulled_at=pulled_at,
        match_key="match-weighted",
        league="EPL",
        kickoff_utc=pulled_at + timedelta(hours=1),
        market="1X2",
        selection="HOME",
        price_decimal=price,
        extra={},
    )


def test_weighted_uses_reliability_scores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "RELIAB_V2_ENABLE", True, raising=False)
    monkeypatch.setattr(settings, "BEST_PRICE_MIN_SCORE", 0.6, raising=False)
    monkeypatch.setattr(settings, "BEST_PRICE_LOOKBACK_MIN", 30, raising=False)
    reliab_store = ProviderReliabilityStoreV2(db_path=str(tmp_path / "reliab.sqlite"))
    tracker = ProviderReliabilityV2(
        store=reliab_store,
        decay=1.0,
        min_samples=0,
        prior_fresh_alpha=1.0,
        prior_fresh_beta=1.0,
        prior_latency_shape=1.0,
        prior_latency_scale=100.0,
        stability_z_tol=1.0,
        closing_tol_pct=1.0,
    )
    agg_store = OddsSQLiteStore(db_path=str(tmp_path / "odds.sqlite"))
    aggregator = LinesAggregator(
        method="weighted",
        provider_weights={},
        store=agg_store,
        reliability=tracker,
        known_providers=["alpha", "beta"],
        best_price_min_score=0.6,
    )

    now = datetime.now(UTC)
    # Drive tracker: alpha provides fresh quotes, beta misses -> alpha score climbs, beta drops.
    for minutes in range(4):
        moment = now + timedelta(minutes=minutes)
        quote_alpha = _snapshot("alpha", moment, price=2.0)
        tracker.observe_event(
            match_key="match-weighted",
            market="1X2",
            league="EPL",
            quotes=[quote_alpha],
            expected_providers=["alpha", "beta"],
            reference_price=2.0,
            observed_at=moment,
        )

    alpha_stats = tracker.get("alpha", "1X2", "EPL")
    beta_stats = tracker.get("beta", "1X2", "EPL")
    assert alpha_stats is not None and beta_stats is not None
    assert alpha_stats.score > 0.6
    assert beta_stats.score < 0.2
    weights_before = {"alpha": alpha_stats.score, "beta": beta_stats.score}

    quotes = [
        _snapshot("alpha", now + timedelta(minutes=5), price=2.0),
        _snapshot("beta", now + timedelta(minutes=5), price=3.0),
    ]
    result = aggregator.aggregate(quotes)
    assert len(result) == 1
    consensus = aggregator.last_metadata[("match-weighted", "1X2", "HOME")]
    expected_probability = (
        weights_before["alpha"] * (1 / 2.0) + weights_before["beta"] * (1 / 3.0)
    ) / (weights_before["alpha"] + weights_before["beta"])
    assert pytest.approx(consensus.probability, rel=1e-6) == pytest.approx(expected_probability, rel=1e-6)

    best = aggregator.pick_best_route(
        match_key="match-weighted",
        market="1X2",
        selection="HOME",
        league="EPL",
        now=now + timedelta(minutes=6),
    )
    assert best is not None
    assert best["provider"].lower() == "alpha"
