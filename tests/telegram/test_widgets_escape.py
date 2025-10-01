"""
@file: tests/telegram/test_widgets_escape.py
@description: Validation for tgbotapp widget formatting helpers.
@dependencies: tgbotapp.widgets
@created: 2025-09-23
"""

from __future__ import annotations

from tgbotapp.widgets import format_fixture_list, format_prediction


def test_format_fixture_list_escapes_html() -> None:
    fixtures = [
        {
            "id": 42,
            "home": "<Home>",
            "away": "Away & Co",
            "league": "<Elite>",
            "kickoff": "2025-09-30T18:45:00Z",
        },
        {
            "id": 84,
            "home": "Team",
            "away": "Opponent",
            "league": "",
            "kickoff": None,
        },
    ]

    rendered = format_fixture_list(fixtures)

    assert "&lt;Home&gt;" in rendered
    assert "Away &amp; Co" in rendered
    assert "&lt;Elite&gt;" in rendered
    assert "<Home>" not in rendered
    assert "Away & Co" not in rendered


def test_format_prediction_escapes_and_formats_percentages() -> None:
    payload = {
        "fixture": {
            "home": "<Alpha>",
            "away": "Beta & Co",
            "league": "<Top>",
            "kickoff": "2025-10-01T12:00:00+00:00",
        },
        "markets": {
            "1x2": {
                "home": 0.654,
                "draw": 0.123,
                "away": 0.223,
            }
        },
        "totals": {
            "2.5": {"over": 0.7654, "under": 0.2346},
        },
        "both_teams_to_score": {"yes": 0.6789, "no": 0.3211},
        "top_scores": [
            {"score": "<2:1>", "probability": 0.1876},
            ["1:1", 0.1999],
            {"score": "0:0", "probability": 0.089},
        ],
    }

    rendered = format_prediction(payload)

    assert "&lt;Alpha&gt;" in rendered
    assert "Beta &amp; Co" in rendered
    assert "&lt;Top&gt;" in rendered
    assert "65.4%" in rendered
    assert "12.3%" in rendered
    assert "22.3%" in rendered
    assert "76.5%" in rendered
    assert "23.5%" in rendered
    assert "67.9%" in rendered
    assert "32.1%" in rendered
    assert "&lt;2:1&gt;" in rendered
    # Ensure there are no NaN strings rendered
    assert "nan" not in rendered.lower()

