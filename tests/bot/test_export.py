"""
/**
 * @file: tests/bot/test_export.py
 * @description: Test CSV and PNG export generation utilities.
 * @dependencies: app.bot.services
 * @created: 2025-09-23
 */
"""

from datetime import UTC, datetime

from app.bot.services import Prediction, PredictionFacade


def _prediction() -> Prediction:
    return Prediction(
        match_id=777,
        home="Alpha",
        away="Beta",
        league="Test",
        kickoff=datetime(2025, 2, 2, 12, 0, tzinfo=UTC),
        markets={"1x2": {"home": 0.55, "draw": 0.25, "away": 0.20}},
        totals={"2.5": {"over": 0.48, "under": 0.52}},
        btts={"yes": 0.5, "no": 0.5},
        top_scores=[{"score": "1:0", "probability": 0.1}, {"score": "2:1", "probability": 0.08}],
        lambda_home=1.3,
        lambda_away=1.0,
        expected_goals=2.3,
        fair_odds={"home": 1.82, "draw": 4.0, "away": 5.0},
        confidence=0.68,
        modifiers=[{"name": "Домашнее поле", "delta": 0.03, "impact": 0.02}],
        delta_probabilities={"home": 0.04, "draw": -0.02, "away": -0.02},
        summary="Преимущество дома сохраняется",
    )


def test_generate_csv_and_png(tmp_path) -> None:
    facade = PredictionFacade()
    prediction = _prediction()
    csv_path = facade.generate_csv(prediction, reports_dir=tmp_path)
    png_path = facade.generate_png(prediction, reports_dir=tmp_path)
    assert csv_path.exists()
    assert png_path.exists()
    csv_content = csv_path.read_text(encoding="utf-8")
    assert "lambda_home" in csv_content
    assert png_path.suffix == ".png"
