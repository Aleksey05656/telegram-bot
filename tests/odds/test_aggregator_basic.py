"""
/**
 * @file: tests/odds/test_aggregator_basic.py
 * @description: Unit tests for LinesAggregator consensus strategies (best, median, weighted).
 * @dependencies: datetime, app.lines.aggregator
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.lines.aggregator import LinesAggregator
from app.lines.providers.base import OddsSnapshot


def _fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "odds_multi"


def _snapshot(provider: str, price: float, minutes_before: int) -> OddsSnapshot:
    kickoff = datetime(2025, 10, 10, 18, 0, tzinfo=UTC)
    pulled = kickoff - timedelta(minutes=minutes_before)
    return OddsSnapshot(
        provider=provider,
        pulled_at=pulled,
        match_key="m-1",
        league="EPL",
        kickoff_utc=kickoff,
        market="1X2",
        selection="HOME",
        price_decimal=price,
        extra=None,
    )


def _load_consensus_snapshots() -> list[OddsSnapshot]:
    path = _fixtures_dir() / "consensus_basic.csv"
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [
            _snapshot(
                str(row["provider"]),
                float(row["price_decimal"]),
                int(row["minutes_before"]),
            )
            for row in reader
        ]


@pytest.mark.parametrize(
    ("method", "expected_price"),
    [
        ("best", 2.4),
        ("median", 2.0),
    ],
)
def test_aggregator_consensus_basic(method: str, expected_price: float) -> None:
    aggregator = LinesAggregator(method=method, store=None)
    snapshots = _load_consensus_snapshots()
    result = aggregator.aggregate(snapshots)
    assert len(result) == 1
    consensus = result[0]
    assert pytest.approx(consensus.price_decimal, rel=1e-6) == expected_price
    payload = consensus.extra.get("consensus")
    assert payload["provider_count"] == 3


def test_aggregator_weighted_with_custom_weights() -> None:
    aggregator = LinesAggregator(
        method="weighted",
        provider_weights={"a": 2.0, "b": 1.0, "c": 1.0},
        store=None,
    )
    snapshots = _load_consensus_snapshots()
    result = aggregator.aggregate(snapshots)
    consensus = result[0]
    # Weighted probability = (0.5*2 + 0.5555*1 + 0.4166*1) / 4
    expected_probability = (0.5 * 2 + (1 / 1.8) + (1 / 2.4)) / 4
    assert pytest.approx(consensus.price_decimal, rel=1e-6) == pytest.approx(
        1 / expected_probability, rel=1e-6
    )
    providers = consensus.extra["consensus"]["providers"]
    assert {item["name"] for item in providers} == {"a", "b", "c"}
