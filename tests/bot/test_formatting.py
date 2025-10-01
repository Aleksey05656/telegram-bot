"""
@file: tests/bot/test_formatting.py
@description: Tests for formatting helpers used by tgbotapp handlers.
@dependencies: tgbotapp.widgets
@created: 2025-09-19
"""
from __future__ import annotations

from datetime import datetime, timezone

from tgbotapp.widgets import format_fixture_list, format_prediction


def test_format_fixture_list_html_escape() -> None:
    fixtures = [
        {
            "id": 99,
            "home": "Alpha <FC>",
            "away": "Beta & Co",
            "league": "Premier",
            "kickoff": datetime(2025, 1, 1, 18, 0, tzinfo=timezone.utc),
        }
    ]
    text = format_fixture_list(fixtures)
    assert "Alpha &lt;FC&gt;" in text
    assert "Beta &amp; Co" in text
    assert "📅" in text


def test_format_prediction_sections() -> None:
    payload = {
        "fixture": {
            "id": 99,
            "home": "Alpha <FC>",
            "away": "Beta & Co",
            "league": "Premier",
            "kickoff": datetime(2025, 1, 1, 18, 0, tzinfo=timezone.utc),
        },
        "markets": {"1x2": {"home": 0.48, "draw": 0.27, "away": 0.25}},
        "totals": {"2.5": {"over": 0.55, "under": 0.45}},
        "both_teams_to_score": {"yes": 0.53, "no": 0.47},
        "top_scores": [("2:1", 0.12), ("1:1", 0.11), ("0:2", 0.09)],
    }
    text = format_prediction(payload)
    assert "Alpha &lt;FC&gt;" in text and "Beta &amp; Co" in text
    assert "1X2" in text and "Тоталы" in text and "Обе забьют" in text
    assert "55.0%" in text and "45.0%" in text
    assert text.count("%") >= 6
    assert any(line.startswith("1. 2:1") for line in text.splitlines())
