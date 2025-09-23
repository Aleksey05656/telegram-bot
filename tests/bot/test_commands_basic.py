"""
/**
 * @file: tests/bot/test_commands_basic.py
 * @description: Smoke tests for formatting helpers used by core commands.
 * @dependencies: app.bot.formatting
 * @created: 2025-09-23
 */
"""

from app.bot.formatting import format_help, format_start, format_today_matches


def test_format_start_contains_timezone_and_language() -> None:
    text = format_start("ru", "Europe/Moscow", ["/today", "/match"])
    assert "Europe/Moscow" in text
    assert "RU" in text
    assert "/today" in text


def test_format_help_lists_key_commands() -> None:
    text = format_help()
    assert "/today" in text
    assert "/match" in text
    assert "Пример" in text


def test_format_today_matches_renders_probabilities() -> None:
    items = [
        {
            "home": "Team A",
            "away": "Team B",
            "markets": {"home": 0.52, "draw": 0.24, "away": 0.24},
            "confidence": 0.71,
            "totals": {},
        }
    ]
    text = format_today_matches(
        title="Матчи",
        timezone="UTC",
        items=items,
        page=1,
        total_pages=1,
    )
    assert "Team A vs Team B" in text
    assert "52.0%" in text
    assert "Страница 1/1" in text
