"""
/**
 * @file: tests/bot/test_value_explain_render.py
 * @description: Check rendering of calibration labels and explanations for value cards.
 * @dependencies: app.bot.formatting, app.value_detector
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.bot.formatting import format_value_comparison, format_value_picks
from app.value_detector import ValuePick


def _pick() -> ValuePick:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    return ValuePick(
        match_key="m1",
        market="1X2",
        selection="HOME",
        league="EPL",
        fair_price=2.1,
        market_price=2.4,
        edge_pct=12.5,
        model_probability=0.48,
        market_probability=0.41,
        confidence=0.75,
        edge_weighted_pct=9.375,
        edge_threshold_pct=4.0,
        confidence_threshold=0.7,
        calibrated=True,
        provider="stub",
        pulled_at=now,
        kickoff_utc=now + timedelta(hours=6),
    )


def test_value_card_includes_calibration_and_explain() -> None:
    pick = _pick()
    text = format_value_picks(
        title="Value",
        cards=[{"match": {"home": "Team A", "away": "Team B", "league": "EPL", "kickoff": pick.kickoff_utc}, "pick": pick, "overround_method": "proportional"}],
    )
    assert "Калибровка активна" in text
    assert "edge_w=9.38" in text
    assert "ℹ️ Объяснение" in text


def test_compare_render_shows_explanation_block() -> None:
    pick = _pick()
    summary = {
        "match": {
            "home": "Team A",
            "away": "Team B",
            "league": "EPL",
            "kickoff": pick.kickoff_utc,
        },
        "picks": [pick],
        "markets": {},
        "overround_method": "proportional",
    }
    text = format_value_comparison(summary)
    assert "ℹ️" in text
    assert "edge_w" in text
    assert "τ≥" in text
