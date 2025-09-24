"""
/**
 * @file: tests/odds/test_best_route.py
 * @description: Unit tests for best-price routing with reliability and anomaly filtering.
 * @dependencies: datetime, app.lines.aggregator, app.lines.anomaly, app.lines.providers.base,
 *                app.lines.reliability, app.lines.storage
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.lines.aggregator import LinesAggregator
from app.lines.anomaly import OddsAnomalyDetector
from app.lines.providers.base import OddsSnapshot
from app.lines.reliability import ProviderReliabilityStore, ProviderReliabilityTracker
from app.lines.storage import OddsSQLiteStore


def _snapshot(
    provider: str,
    *,
    match_key: str,
    pulled_at: datetime,
    kickoff: datetime,
    price: float,
    league: str = "EPL",
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


def _build_aggregator(tmp_path) -> LinesAggregator:
    odds_store = OddsSQLiteStore(db_path=str(tmp_path / "odds.sqlite3"))
    rel_store = ProviderReliabilityStore(db_path=str(tmp_path / "rel.sqlite3"))
    reliability = ProviderReliabilityTracker(store=rel_store, decay=0.5, max_freshness_sec=900)
    anomaly = OddsAnomalyDetector(z_max=2.5, quantile=0.1)
    return LinesAggregator(
        method="median",
        store=odds_store,
        retention_days=7,
        reliability=reliability,
        anomaly_detector=anomaly,
        known_providers=["csv", "http"],
        best_price_lookback_min=60,
        best_price_min_score=0.4,
    )


def _seed_history(aggregator: LinesAggregator, *, match_key: str, base: datetime, kickoff: datetime) -> None:
    for step in range(12):
        pulled = base + timedelta(minutes=step)
        aggregator.aggregate(
            [
                _snapshot(
                    "csv",
                    match_key=match_key,
                    pulled_at=pulled,
                    kickoff=kickoff,
                    price=2.05 + step * 0.01,
                ),
                _snapshot(
                    "http",
                    match_key=match_key,
                    pulled_at=pulled,
                    kickoff=kickoff,
                    price=2.00 + step * 0.015,
                ),
            ]
        )


def test_best_route_prefers_highest_price(tmp_path) -> None:
    aggregator = _build_aggregator(tmp_path)
    match_key = "match-best"
    base = datetime(2025, 10, 7, 10, 0, tzinfo=UTC)
    kickoff = base + timedelta(hours=5)
    _seed_history(aggregator, match_key=match_key, base=base, kickoff=kickoff)

    pulled = base + timedelta(minutes=30)
    aggregator.aggregate(
        [
            _snapshot(
                "csv",
                match_key=match_key,
                pulled_at=pulled,
                kickoff=kickoff,
                price=2.40,
            ),
            _snapshot(
                "http",
                match_key=match_key,
                pulled_at=pulled,
                kickoff=kickoff,
                price=2.25,
            ),
        ]
    )

    route = aggregator.pick_best_route(
        match_key=match_key,
        market="1X2",
        selection="HOME",
        league="EPL",
        now=pulled + timedelta(seconds=30),
    )
    assert route is not None
    assert route["provider"] == "csv"
    assert route["price_decimal"] > 2.3
    assert route["score"] >= 0.4


def test_best_route_skips_anomalies(tmp_path) -> None:
    aggregator = _build_aggregator(tmp_path)
    match_key = "match-anomaly"
    base = datetime(2025, 10, 7, 9, 0, tzinfo=UTC)
    kickoff = base + timedelta(hours=6)
    _seed_history(aggregator, match_key=match_key, base=base, kickoff=kickoff)

    pulled = base + timedelta(minutes=40)
    aggregator.aggregate(
        [
            _snapshot(
                "csv",
                match_key=match_key,
                pulled_at=pulled,
                kickoff=kickoff,
                price=6.50,
            ),
            _snapshot(
                "http",
                match_key=match_key,
                pulled_at=pulled,
                kickoff=kickoff,
                price=2.30,
            ),
        ]
    )

    route = aggregator.pick_best_route(
        match_key=match_key,
        market="1X2",
        selection="HOME",
        league="EPL",
        now=pulled + timedelta(seconds=10),
    )
    assert route is not None
    assert route["provider"] == "http"
    assert route["price_decimal"] == 2.30


def test_best_route_requires_reliability(tmp_path) -> None:
    odds_store = OddsSQLiteStore(db_path=str(tmp_path / "odds_raw.sqlite3"))
    rel_store = ProviderReliabilityStore(db_path=str(tmp_path / "rel_raw.sqlite3"))
    reliability = ProviderReliabilityTracker(store=rel_store, decay=0.8, max_freshness_sec=600)
    anomaly = OddsAnomalyDetector(z_max=3.0)
    aggregator = LinesAggregator(
        method="median",
        store=odds_store,
        retention_days=3,
        reliability=reliability,
        anomaly_detector=anomaly,
        known_providers=["csv", "http"],
        best_price_lookback_min=30,
        best_price_min_score=0.6,
    )

    base = datetime(2025, 10, 7, 8, 0, tzinfo=UTC)
    kickoff = base + timedelta(hours=4)
    aggregator.aggregate(
        [
            _snapshot(
                "csv",
                match_key="match-raw",
                pulled_at=base,
                kickoff=kickoff,
                price=2.2,
            ),
            _snapshot(
                "http",
                match_key="match-raw",
                pulled_at=base,
                kickoff=kickoff,
                price=2.1,
            ),
        ]
    )

    route = aggregator.pick_best_route(
        match_key="match-raw",
        market="1X2",
        selection="HOME",
        league="EPL",
        now=base + timedelta(minutes=1),
    )
    assert route is None
