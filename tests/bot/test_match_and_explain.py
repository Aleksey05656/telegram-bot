"""
/**
 * @file: tests/bot/test_match_and_explain.py
 * @description: Ensure match and explain formatters expose required fields.
 * @dependencies: app.bot.services, app.bot.formatting
 * @created: 2025-09-23
 */
"""

from datetime import UTC, datetime

from app.bot.formatting import format_explain, format_match_details
from app.bot.services import Prediction


def _sample_prediction() -> Prediction:
    return Prediction(
        match_id=555,
        home="Home",
        away="Away",
        league="League",
        kickoff=datetime(2025, 1, 15, 18, 0, tzinfo=UTC),
        markets={"1x2": {"home": 0.6, "draw": 0.2, "away": 0.2}},
        totals={"2.5": {"over": 0.55, "under": 0.45}},
        btts={"yes": 0.51, "no": 0.49},
        top_scores=[{"score": "2:1", "probability": 0.12}],
        lambda_home=1.4,
        lambda_away=1.1,
        expected_goals=2.5,
        fair_odds={"home": 1.67, "draw": 4.8, "away": 5.0},
        confidence=0.73,
        modifiers=[{"name": "Форма", "delta": 0.02, "impact": 0.015}],
        delta_probabilities={"home": 0.05, "draw": -0.03, "away": -0.02},
        summary="Форма хозяев определяет прогноз",
    )


def test_match_details_contains_markets() -> None:
    prediction = _sample_prediction()
    text = format_match_details(
        {
            "fixture": {
                "id": prediction.match_id,
                "home": prediction.home,
                "away": prediction.away,
                "league": prediction.league,
                "kickoff": prediction.kickoff,
            },
            "markets": prediction.markets,
            "totals": prediction.totals,
            "both_teams_to_score": prediction.btts,
            "top_scores": prediction.top_scores,
            "fair_odds": prediction.fair_odds,
            "confidence": prediction.confidence,
        }
    )
    assert "P(1)" in text
    assert "Over 2.5" in text
    assert "Топ скорлайны" in text


def test_format_explain_mentions_modifiers() -> None:
    prediction = _sample_prediction()
    text = format_explain(
        {
            "id": prediction.match_id,
            "fixture": {"home": prediction.home, "away": prediction.away},
            "lambda_home": prediction.lambda_home,
            "lambda_away": prediction.lambda_away,
            "modifiers": prediction.modifiers,
            "delta_probabilities": prediction.delta_probabilities,
            "confidence": prediction.confidence,
            "summary": prediction.summary,
        }
    )
    assert "λ базовые" in text
    assert "Модификаторы" in text
    assert "Уверенность" in text
