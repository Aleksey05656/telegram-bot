"""
/**
 * @file: tests/bot/test_reliability_badges.py
 * @description: Ensures reliability badges render in value and compare responses.
 * @dependencies: app.bot.formatting
 * @created: 2025-10-28
 */
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.bot.formatting import format_value_comparison, format_value_picks


def test_value_picks_render_reliability_block() -> None:
    kickoff = datetime(2025, 10, 28, 18, 0, tzinfo=UTC)
    pick = type(
        "P",
        (),
        {
            "market": "1X2",
            "selection": "HOME",
            "model_probability": 0.55,
            "market_probability": 0.5,
            "edge_weighted_pct": 3.2,
            "edge_pct": 4.8,
            "confidence": 0.85,
            "edge_threshold_pct": 2.5,
            "confidence_threshold": 0.6,
            "calibrated": True,
            "provider": "consensus",
            "fair_price": 1.92,
            "market_price": 2.1,
        },
    )()
    cards = [
        {
            "match": {"home": "Team A", "away": "Team B", "league": "EPL", "kickoff": kickoff},
            "pick": pick,
            "reliability_v2": [
                {"provider": "csv", "score": 0.73},
                {"provider": "http", "score": 0.61, "trend": "↗"},
            ],
        }
    ]
    rendered = format_value_picks(title="Value", cards=cards)
    assert "Reliability:" in rendered
    assert "csv 0.73" in rendered
    assert "http 0.61" in rendered


def test_value_compare_includes_reliability_badge() -> None:
    summary = {
        "match": {
            "home": "Team A",
            "away": "Team B",
            "league": "EPL",
            "kickoff": datetime(2025, 10, 28, 20, 0, tzinfo=UTC),
        },
        "markets": {},
        "picks": [],
        "reliability_v2": [
            {"provider": "csv", "score": 0.70},
            {"provider": "http", "score": 0.65, "trend": "stable"},
        ],
    }
    text = format_value_comparison(summary)
    assert "Reliability:" in text
    assert "stable" in text
