"""
@file: core/services/predictor.py
@description: Predictor service orchestrating recommendation engine payload normalisation.
@dependencies: services.recommendation_engine.RecommendationEngine
@created: 2025-09-20
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from services.recommendation_engine import (
    InvalidPredictionRequest,
    PredictionEngineError,
    RecommendationEngine,
)


class PredictorServiceError(RuntimeError):
    """Raised when predictor service fails to generate a payload."""


class PredictorService:
    """Wrapper around :class:`RecommendationEngine` exposing a stable interface."""

    def __init__(self, engine: RecommendationEngine) -> None:
        self._engine = engine

    async def generate_prediction(
        self,
        fixture_id: str | None = None,
        *,
        home: str | None = None,
        away: str | None = None,
        seed: int,
        n_sims: int,
    ) -> dict[str, Any]:
        try:
            prediction = await self._engine.generate_prediction(
                fixture_id,
                home=home,
                away=away,
                seed=seed,
                n_sims=n_sims,
            )
        except (InvalidPredictionRequest, PredictionEngineError) as exc:
            raise PredictorServiceError(str(exc)) from exc

        totals = prediction["totals"]
        return {
            "fixture_id": prediction.get("fixture_id"),
            "league": prediction.get("league"),
            "utc_kickoff": prediction.get("utc_kickoff"),
            "teams": deepcopy(prediction.get("teams", {})),
            "expected_goals": deepcopy(prediction.get("expected_goals", {})),
            "seed": prediction.get("seed"),
            "n_sims": prediction.get("n_sims"),
            "probs": dict(prediction.get("probs", {})),
            "totals": {
                "over_2_5": totals.get("over_2_5"),
                "under_2_5": totals.get("under_2_5"),
                "btts_yes": totals.get("btts_yes"),
                "btts_no": totals.get("btts_no"),
            },
            "scoreline_topk": list(prediction.get("scoreline_topk", [])),
        }
