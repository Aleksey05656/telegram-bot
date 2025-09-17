"""
@file: tests/services/test_predictor_determinism.py
@description: Determinism tests for PredictorService wrapper.
@dependencies: core.services.predictor
@created: 2025-09-23
"""

from __future__ import annotations

import math
import random

import pytest

from core.services.predictor import PredictorService


class FakeRecommendationEngine:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate_prediction(
        self,
        fixture_id: str | None = None,
        *,
        home: str | None = None,
        away: str | None = None,
        seed: int,
        n_sims: int,
    ) -> dict[str, object]:
        rng = random.Random(seed)
        self.calls.append(
            {
                "fixture_id": fixture_id,
                "home": home,
                "away": away,
                "seed": seed,
                "n_sims": n_sims,
            }
        )
        base = rng.random()
        return {
            "fixture_id": fixture_id or "auto",
            "league": "L",
            "utc_kickoff": "2025-09-23T00:00:00+00:00",
            "teams": {"home": home or "H", "away": away or "A"},
            "expected_goals": {"home": base + 0.5, "away": base + 0.7},
            "seed": seed,
            "n_sims": n_sims,
            "probs": {"home": rng.random(), "draw": rng.random(), "away": rng.random()},
            "totals": {
                "over_2_5": rng.random(),
                "under_2_5": rng.random(),
                "btts_yes": rng.random(),
                "btts_no": rng.random(),
            },
            "scoreline_topk": [
                {"score": "1:0", "probability": rng.random()},
                {"score": "2:1", "probability": rng.random()},
            ],
        }


@pytest.mark.asyncio
async def test_predictor_service_same_seed_same_payload() -> None:
    engine = FakeRecommendationEngine()
    service = PredictorService(engine)
    payload_a = await service.generate_prediction("42", seed=2024, n_sims=1000)
    payload_b = await service.generate_prediction("42", seed=2024, n_sims=1000)
    assert payload_a == payload_b
    assert engine.calls == [
        {"fixture_id": "42", "home": None, "away": None, "seed": 2024, "n_sims": 1000},
        {"fixture_id": "42", "home": None, "away": None, "seed": 2024, "n_sims": 1000},
    ]
    for key, value in payload_a["totals"].items():
        assert value >= 0, f"total {key} should be non-negative"
    for value in payload_a["probs"].values():
        assert not math.isnan(value)
        assert value >= 0


@pytest.mark.asyncio
async def test_predictor_service_different_seed_changes_payload() -> None:
    engine = FakeRecommendationEngine()
    service = PredictorService(engine)
    payload_a = await service.generate_prediction("7", home="A", away="B", seed=100, n_sims=500)
    payload_b = await service.generate_prediction("7", home="A", away="B", seed=101, n_sims=500)
    assert payload_a != payload_b
    assert payload_a["fixture_id"] == payload_b["fixture_id"] == "7"
    assert payload_a["teams"] == payload_b["teams"] == {"home": "A", "away": "B"}

