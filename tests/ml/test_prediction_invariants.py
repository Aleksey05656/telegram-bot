"""
@file: tests/ml/test_prediction_invariants.py
@description: Invariant tests for the recommendation engine prediction payload.
@dependencies: pytest, hypothesis, numpy, sqlalchemy
@created: 2025-09-20
"""
from __future__ import annotations

import math
from collections.abc import Awaitable, Callable

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings  # type: ignore  # noqa: E402
from hypothesis import strategies as st  # type: ignore  # noqa: E402
from hypothesis.extra.asyncio import async_test  # type: ignore  # noqa: E402
from sqlalchemy import text

from database import DBRouter
from services.recommendation_engine import RecommendationEngine

pytestmark = pytest.mark.needs_np


async def _create_schema(router: DBRouter) -> None:
    async with router.session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE fixtures (
                    id INTEGER PRIMARY KEY,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    league TEXT,
                    utc_kickoff TEXT,
                    home_team_id INTEGER,
                    away_team_id INTEGER
                )
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE TABLE team_metrics (
                    team_id INTEGER PRIMARY KEY,
                    team_name TEXT NOT NULL,
                    attack_strength REAL,
                    defence_strength REAL,
                    lambda_for REAL,
                    lambda_against REAL,
                    xg_for REAL,
                    xg_against REAL
                )
                """
            )
        )
        await session.commit()


@pytest.fixture
async def engine_with_data() -> tuple[RecommendationEngine, Callable[[float, float], Awaitable[None]]]:
    router = DBRouter(dsn="sqlite+aiosqlite:///:memory:")
    await _create_schema(router)
    async with router.session() as session:
        await session.execute(
            text(
                """
                INSERT INTO fixtures (id, home_team, away_team, league, utc_kickoff, home_team_id, away_team_id)
                VALUES (:id, :home, :away, :league, :kickoff, :home_id, :away_id)
                """
            ),
            {
                "id": 1,
                "home": "Alpha FC",
                "away": "Beta United",
                "league": "Test League",
                "kickoff": "2025-09-20T18:30:00+00:00",
                "home_id": 10,
                "away_id": 20,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO team_metrics (
                    team_id, team_name, attack_strength, defence_strength,
                    lambda_for, lambda_against, xg_for, xg_against
                )
                VALUES
                    (:home_id, :home_name, 1.4, 0.9, 1.6, 1.1, 1.5, 1.0),
                    (:away_id, :away_name, 1.2, 1.0, 1.3, 1.2, 1.2, 1.1)
                """
            ),
            {
                "home_id": 10,
                "home_name": "Alpha FC",
                "away_id": 20,
                "away_name": "Beta United",
            },
        )
        await session.commit()

    engine = RecommendationEngine(router)

    async def _update(home_rate: float, away_rate: float) -> None:
        async with router.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE team_metrics
                    SET lambda_for = :rate,
                        xg_for = :rate,
                        attack_strength = :rate
                    WHERE team_id = :team_id
                    """
                ),
                {"rate": home_rate, "team_id": 10},
            )
            await session.execute(
                text(
                    """
                    UPDATE team_metrics
                    SET lambda_against = :rate,
                        xg_against = :rate,
                        defence_strength = :rate
                    WHERE team_id = :team_id
                    """
                ),
                {"rate": away_rate, "team_id": 10},
            )
            await session.execute(
                text(
                    """
                    UPDATE team_metrics
                    SET lambda_for = :rate,
                        xg_for = :rate,
                        attack_strength = :rate
                    WHERE team_id = :team_id
                    """
                ),
                {"rate": away_rate, "team_id": 20},
            )
            await session.execute(
                text(
                    """
                    UPDATE team_metrics
                    SET lambda_against = :rate,
                        xg_against = :rate,
                        defence_strength = :rate
                    WHERE team_id = :team_id
                    """
                ),
                {"rate": home_rate, "team_id": 20},
            )
            await session.commit()

    yield engine, _update
    await router.shutdown()


@pytest.mark.asyncio
async def test_probabilities_and_totals_are_normalized(engine_with_data) -> None:
    engine, _ = engine_with_data
    result = await engine.generate_prediction("1", seed=42, n_sims=5000)

    probs = result["probs"]
    assert pytest.approx(sum(probs.values()), rel=1e-6, abs=1e-6) == 1.0
    assert all(prob >= 0 for prob in probs.values())

    totals = result["totals"]
    assert pytest.approx(totals["over_2_5"] + totals["under_2_5"], rel=1e-6, abs=1e-6) == 1.0
    assert pytest.approx(totals["btts_yes"] + totals["btts_no"], rel=1e-6, abs=1e-6) == 1.0
    assert all(value >= 0 for value in totals.values())

    topk = result["scoreline_topk"]
    assert topk == sorted(topk, key=lambda item: item["probability"], reverse=True)
    assert all(item["probability"] > 0 for item in topk)


@pytest.mark.asyncio
async def test_seed_stability(engine_with_data) -> None:
    engine, _ = engine_with_data
    first = await engine.generate_prediction("1", seed=7, n_sims=4000)
    second = await engine.generate_prediction("1", seed=7, n_sims=4000)
    assert first["probs"] == second["probs"]
    assert first["totals"] == second["totals"]
    assert first["scoreline_topk"] == second["scoreline_topk"]

    different_seed = await engine.generate_prediction("1", seed=8, n_sims=4000)
    assert different_seed["probs"] != first["probs"] or different_seed["totals"] != first["totals"]


@given(
    home_rate=st.floats(min_value=0.05, max_value=6.0, allow_nan=False, allow_infinity=False),
    away_rate=st.floats(min_value=0.05, max_value=6.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=20, deadline=None)
@async_test()
async def test_no_nan_for_extreme_lambdas(
    engine_with_data: tuple[RecommendationEngine, Callable[[float, float], Awaitable[None]]],
    home_rate: float,
    away_rate: float,
) -> None:
    engine, update_rates = engine_with_data
    await update_rates(home_rate, away_rate)
    result = await engine.generate_prediction("1", seed=11, n_sims=3000)

    assert all(not math.isnan(prob) and prob >= 0 for prob in result["probs"].values())
    totals = result["totals"]
    assert all(not math.isnan(value) and value >= 0 for value in totals.values())
