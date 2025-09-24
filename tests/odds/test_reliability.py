"""
/**
 * @file: tests/odds/test_reliability.py
 * @description: Unit tests for provider reliability tracker scoring and eligibility filters.
 * @dependencies: datetime, math, app.lines.reliability, app.lines.providers.base
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from app.lines.providers.base import OddsSnapshot
from app.lines.reliability import (
    GLOBAL_LEAGUE,
    ProviderReliabilityStore,
    ProviderReliabilityTracker,
)


def _snapshot(
    provider: str,
    *,
    match_key: str,
    pulled_at: datetime,
    kickoff: datetime,
    price: float,
    league: str | None = "EPL",
) -> OddsSnapshot:
    return OddsSnapshot(
        provider=provider,
        pulled_at=pulled_at,
        match_key=match_key,
        league=league,
        kickoff_utc=kickoff,
        market="1X2",
        selection="HOME",
        price_decimal=price,
        extra=None,
    )


def test_reliability_scoring_and_eligibility(tmp_path) -> None:
    db_path = tmp_path / "reliability.sqlite3"
    store = ProviderReliabilityStore(db_path=str(db_path))
    tracker = ProviderReliabilityTracker(store=store, decay=0.5, max_freshness_sec=600)
    base = datetime(2025, 10, 7, 12, 0, tzinfo=UTC)
    kickoff = base + timedelta(hours=4)

    # Первый эвент: отсутствует HTTP-провайдер → покрытие низкое
    tracker.observe_event(
        match_key="m-1",
        market="1X2",
        league="EPL",
        quotes=[_snapshot("csv", match_key="m-1", pulled_at=base, kickoff=kickoff, price=2.1)],
        expected_providers=["csv", "http"],
        reference_price=2.05,
        observed_at=base,
    )

    assert tracker.eligible("csv", "1X2", "EPL", min_score=0.5) is False
    assert tracker.eligible("http", "1X2", "EPL", min_score=0.5) is False

    # Наращиваем статистику для обоих провайдеров
    for step in range(1, 13):
        pulled_at = base + timedelta(minutes=step)
        tracker.observe_event(
            match_key="m-1",
            market="1X2",
            league="EPL",
            quotes=[
                _snapshot(
                    "csv",
                    match_key="m-1",
                    pulled_at=pulled_at,
                    kickoff=kickoff,
                    price=2.05 + step * 0.01,
                ),
                _snapshot(
                    "http",
                    match_key="m-1",
                    pulled_at=pulled_at,
                    kickoff=kickoff,
                    price=2.00 + step * 0.015,
                ),
            ],
            expected_providers=["csv", "http"],
            reference_price=2.05 + step * 0.008,
            observed_at=pulled_at,
        )

    stats_csv = tracker.get("csv", "1X2", "EPL")
    stats_http = tracker.get("http", "1X2", "EPL")
    assert stats_csv is not None and stats_http is not None
    assert stats_csv.coverage > 0.6
    assert stats_http.coverage > 0.6
    assert stats_csv.score > 0.5
    assert tracker.eligible("csv", "1X2", "EPL", min_score=0.5)
    assert tracker.eligible("http", "1X2", "EPL", min_score=0.5)

    snapshot = tracker.snapshot()
    providers = {item.provider for item in snapshot}
    assert {"csv", "http"}.issubset(providers)

    stored = store.get_stats("CSV", "1x2", "epl")
    assert stored is not None
    assert math.isclose(stored.score, stats_csv.score, rel_tol=1e-6)


def test_reliability_global_fallback(tmp_path) -> None:
    db_path = tmp_path / "reliability_global.sqlite3"
    store = ProviderReliabilityStore(db_path=str(db_path))
    tracker = ProviderReliabilityTracker(store=store, decay=0.4, max_freshness_sec=300)
    base = datetime(2025, 10, 7, 12, 0, tzinfo=UTC)
    kickoff = base + timedelta(hours=2)

    tracker.observe_event(
        match_key="m-2",
        market="1X2",
        league=None,
        quotes=[
            _snapshot(
                "csv",
                match_key="m-2",
                pulled_at=base,
                kickoff=kickoff,
                price=1.95,
                league=None,
            )
        ],
        expected_providers=["csv"],
        reference_price=1.96,
        observed_at=base,
    )

    direct = store.get_stats("csv", "1X2", GLOBAL_LEAGUE)
    assert direct is not None
    fallback = store.get_stats("csv", "1X2", "Premier League")
    assert fallback is not None
    assert fallback.league == GLOBAL_LEAGUE
