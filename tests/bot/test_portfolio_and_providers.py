"""
/**
 * @file: tests/bot/test_portfolio_and_providers.py
 * @description: Tests bot formatting for value providers keyboard and portfolio summaries.
 * @dependencies: datetime, aiogram stubs, app.bot.formatting
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram.types import InlineKeyboardMarkup

from app.bot.formatting import (
    format_portfolio,
    format_providers_breakdown,
    format_value_picks,
)
from app.bot.keyboards import value_providers_keyboard
from app.lines.providers.base import OddsSnapshot


def test_format_value_picks_includes_consensus_line() -> None:
    kickoff = datetime(2025, 10, 9, 18, 0, tzinfo=UTC)
    cards = [
        {
            "match": {"home": "A", "away": "B", "kickoff": kickoff, "league": "EPL"},
            "pick": type("P", (), {"market": "1X2", "selection": "HOME", "model_probability": 0.55, "market_probability": 0.5, "edge_weighted_pct": 3.0, "edge_pct": 5.0, "confidence": 0.8, "edge_threshold_pct": 3.0, "confidence_threshold": 0.6, "calibrated": True, "provider": "consensus", "fair_price": 1.9, "market_price": 2.1})(),
            "overround_method": "proportional",
            "consensus": {
                "match_key": "m-4",
                "market": "1X2",
                "selection": "HOME",
                "price": 2.05,
                "provider_count": 2,
                "trend": "↘︎",
                "closing_price": 1.95,
            },
        }
    ]
    rendered = format_value_picks(title="Value", cards=cards)
    assert "Consensus 2.05" in rendered
    assert "closing 1.95" in rendered


def test_value_providers_keyboard_contains_callback() -> None:
    kickoff = datetime(2025, 10, 9, 18, 0, tzinfo=UTC)
    cards = [
        {
            "match": {"match_key": "m-4", "home": "A", "away": "B", "kickoff": kickoff},
            "pick": type("P", (), {"market": "1X2", "selection": "HOME"})(),
            "consensus": {"match_key": "m-4", "market": "1X2", "selection": "HOME"},
        }
    ]
    markup = value_providers_keyboard(cards)
    assert isinstance(markup, InlineKeyboardMarkup)
    buttons = markup.inline_keyboard[0]
    assert any(button.callback_data.startswith("providers:") for button in buttons)


def test_format_providers_breakdown() -> None:
    kickoff = datetime(2025, 10, 9, 18, 0, tzinfo=UTC)
    quotes = [
        OddsSnapshot(
            provider="p1",
            pulled_at=kickoff,
            match_key="m-5",
            league="EPL",
            kickoff_utc=kickoff,
            market="1X2",
            selection="HOME",
            price_decimal=2.1,
            extra=None,
        )
    ]
    consensus = {"provider_count": 1, "price": 2.1, "trend": "↗︎"}
    text = format_providers_breakdown(
        match_key="m-5",
        market="1X2",
        selection="HOME",
        quotes=quotes,
        consensus=consensus,
    )
    assert "Consensus 2.10" in text
    assert "p1" in text


def test_format_portfolio_summary() -> None:
    summary = {"total": 3, "avg_clv": 4.5, "positive_share": 0.66, "picks": []}
    text = format_portfolio(summary)
    assert "Всего сигналов: 3" in text
    assert "Средний CLV: 4.50%" in text
