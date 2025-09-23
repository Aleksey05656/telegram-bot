"""
@file: test_staleness_badges.py
@description: Validate freshness badges rendering in bot commands.
@dependencies: pytest
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.bot.formatting import format_today_matches
from app.bot.routers import commands
from app.bot.services import Prediction


@pytest.fixture(autouse=True)
def enable_staleness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands.settings, "SHOW_DATA_STALENESS", True)
    monkeypatch.setattr(commands.settings, "SM_FRESHNESS_WARN_HOURS", 12)
    monkeypatch.setattr(commands.settings, "SM_FRESHNESS_FAIL_HOURS", 24)


def _prediction(freshness: float) -> Prediction:
    return Prediction(
        match_id=1,
        home="A",
        away="B",
        league="EPL",
        kickoff=datetime.now(tz=UTC),
        markets={"1x2": {"home": 0.5, "draw": 0.3, "away": 0.2}},
        totals={},
        btts={},
        top_scores=[],
        lambda_home=1.2,
        lambda_away=1.0,
        expected_goals=2.2,
        fair_odds={},
        confidence=0.6,
        modifiers=[],
        delta_probabilities={},
        summary="",
        freshness_hours=freshness,
        standings=[],
        injuries=[],
    )


def test_freshness_note_for_recent_data() -> None:
    preds = [_prediction(0.2)]
    note = commands._freshness_note(preds)
    assert note and "updated" in note
    text = format_today_matches(
        title="Test",
        timezone="UTC",
        items=[commands._prediction_to_item(preds[0])],
        page=1,
        total_pages=1,
        freshness_note=note,
    )
    assert "updated" in text


def test_freshness_note_for_stale_data() -> None:
    preds = [_prediction(30.0)]
    note = commands._freshness_note(preds)
    assert note and "stale" in note
