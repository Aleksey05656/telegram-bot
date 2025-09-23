"""
/**
 * @file: tests/bot/test_today_pagination.py
 * @description: Validate inline keyboards for pagination flows.
 * @dependencies: app.bot.keyboards
 * @created: 2025-09-23
 */
"""

from app.bot.keyboards import match_details_keyboard, today_keyboard


def test_today_keyboard_contains_match_and_navigation() -> None:
    markup = today_keyboard(
        [{"id": 101, "home": "A", "away": "B"}],
        query_hash="abc123",
        page=1,
        total_pages=2,
    )
    callback_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert any(data.startswith("match:101") for data in callback_data)
    assert any(data == "page:abc123:1" for data in callback_data) is False
    assert any(data == "page:abc123:2" for data in callback_data)


def test_match_details_keyboard_has_back_button() -> None:
    markup = match_details_keyboard(42, query_hash="hash321", page=3)
    callback_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "explain:42" in callback_data
    assert "export:42" in callback_data
    assert f"back:hash321:3" in callback_data
