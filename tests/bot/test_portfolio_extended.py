"""
/**
 * @file: tests/bot/test_portfolio_extended.py
 * @description: Tests extended portfolio rendering and best-price messaging.
 * @dependencies: app.bot.formatting, datetime
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.bot.formatting import format_portfolio, format_value_picks


def test_format_portfolio_includes_roi_and_details() -> None:
    summary = {
        "total": 12,
        "avg_edge": 3.25,
        "avg_clv": 1.5,
        "avg_roi": 4.0,
        "positive_share": 0.55,
        "page": 2,
        "total_pages": 3,
        "picks": [
            {
                "match_key": "MATCH-1",
                "market": "1X2",
                "selection": "HOME",
                "provider_price_decimal": 2.2,
                "consensus_price_decimal": 2.0,
                "closing_price": 1.9,
                "outcome": "win",
                "roi": 20.0,
                "clv_pct": 5.0,
                "created_at": "2025-10-07T09:00:00+00:00",
            }
        ],
    }
    text = format_portfolio(summary)
    assert "Всего сигналов: 12" in text
    assert "ROI 60д: 4.00%" in text
    assert "Страница 2/3" in text
    assert "MATCH-1" in text
    assert "2.20 vs cons 2.00 / close 1.90" in text
    assert "WIN ROI +20.0% CLV +5.00%" in text


def test_format_value_picks_best_price_block() -> None:
    kickoff = datetime(2025, 10, 8, 18, 0, tzinfo=UTC)
    cards = [
        {
            "match": {"home": "Team A", "away": "Team B", "kickoff": kickoff, "league": "EPL"},
            "pick": type(
                "P",
                (),
                {
                    "market": "1X2",
                    "selection": "HOME",
                    "model_probability": 0.55,
                    "market_probability": 0.5,
                    "edge_weighted_pct": 3.2,
                    "edge_pct": 5.4,
                    "confidence": 0.8,
                    "edge_threshold_pct": 3.0,
                    "confidence_threshold": 0.6,
                    "calibrated": True,
                    "provider": "consensus",
                    "fair_price": 1.9,
                    "market_price": 2.1,
                },
            )(),
            "overround_method": "proportional",
            "consensus": {
                "match_key": "m-10",
                "market": "1X2",
                "selection": "HOME",
                "price": 2.05,
                "provider_count": 2,
                "trend": "↗︎",
                "closing_price": 1.98,
            },
            "best_price": {
                "provider": "csv",
                "price_decimal": 2.25,
                "pulled_at_utc": "2025-10-07T11:30:00Z",
                "score": 0.78,
            },
        }
    ]
    rendered = format_value_picks(title="Value", cards=cards)
    assert "Best price: csv 2.25 (score=0.78)" in rendered
