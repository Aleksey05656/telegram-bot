"""
@file: services/recommendation_engine.py
@description: Deterministic Monte-Carlo based recommendation engine with DB-backed
    inputs and probability invariants.
@dependencies: numpy, sqlalchemy, database.db_router.DBRouter, logger
@created: 2025-09-20
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import text

from database import DBRouter
from logger import logger

_PROB_TOLERANCE = 1e-6
_DEFAULT_SCORELINE_TOPK = 6
_MIN_PROBABILITY = 1e-9


class PredictionEngineError(RuntimeError):
    """Base class for recommendation engine errors."""


class InvalidPredictionRequest(PredictionEngineError):
    """Raised when request payload misses mandatory identifiers."""


class FixtureNotFoundError(PredictionEngineError):
    """Raised when fixture metadata cannot be located in the database."""


class MetricsNotFoundError(PredictionEngineError):
    """Raised when team metrics required for simulation are unavailable."""


@dataclass(slots=True)
class FixtureRecord:
    """Simple representation of fixture metadata fetched from the database."""

    fixture_id: int
    home_team: str
    away_team: str
    league: str | None
    kickoff: datetime | None
    home_team_id: int | None
    away_team_id: int | None


@dataclass(slots=True)
class TeamMetrics:
    """Aggregated metrics for a team used to derive Poisson intensities."""

    team_id: int | None
    name: str
    attack_strength: float | None
    defence_strength: float | None
    lambda_for: float | None
    lambda_against: float | None
    xg_for: float | None
    xg_against: float | None

    def candidates_for_scoring(self) -> Iterable[float]:
        yield from _finite_positive(
            (
                self.lambda_for,
                self.xg_for,
                self.attack_strength,
            )
        )

    def candidates_for_conceding(self) -> Iterable[float]:
        yield from _finite_positive(
            (
                self.lambda_against,
                self.xg_against,
                self.defence_strength,
            )
        )


def _finite_positive(values: Iterable[float | None]) -> list[float]:
    cleaned: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            as_float = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(as_float) or math.isinf(as_float) or as_float <= 0:
            continue
        cleaned.append(as_float)
    return cleaned


def _normalize_pair(a: float, b: float) -> tuple[float, float]:
    first = max(_MIN_PROBABILITY, max(0.0, a))
    second = max(_MIN_PROBABILITY, max(0.0, b))
    total = first + second
    if total <= 0:
        return 0.5, 0.5
    return first / total, second / total


def _normalize_triplet(values: Mapping[str, float]) -> dict[str, float]:
    cleaned = {key: max(_MIN_PROBABILITY, max(0.0, float(value))) for key, value in values.items()}
    total = sum(cleaned.values())
    if total <= 0:
        uniform = 1.0 / max(1, len(cleaned))
        return {key: uniform for key in cleaned}
    return {key: value / total for key, value in cleaned.items()}


class RecommendationEngine:
    """Main entry point responsible for generating prediction payloads."""

    def __init__(
        self,
        db_router: DBRouter,
        *,
        fixtures_table: str = "fixtures",
        metrics_table: str = "team_metrics",
        scoreline_topk: int = _DEFAULT_SCORELINE_TOPK,
    ) -> None:
        self._db_router = db_router
        self._fixtures_table = fixtures_table
        self._metrics_table = metrics_table
        self._scoreline_topk = scoreline_topk

    async def generate_prediction(
        self,
        fixture_id: str | None = None,
        *,
        home: str | None = None,
        away: str | None = None,
        seed: int,
        n_sims: int,
    ) -> dict[str, Any]:
        if n_sims <= 0:
            raise InvalidPredictionRequest("n_sims must be positive")

        fixture = await self._resolve_fixture(fixture_id, home, away)
        home_metrics = await self._load_team_metrics(
            fixture.home_team_id, fixture.home_team
        )
        away_metrics = await self._load_team_metrics(
            fixture.away_team_id, fixture.away_team
        )

        lambda_home, lambda_away = self._estimate_lambdas(home_metrics, away_metrics)
        logger.debug(
            "simulation_inputs fixture=%s λH=%.3f λA=%.3f seed=%s n_sims=%s",
            fixture.fixture_id,
            lambda_home,
            lambda_away,
            seed,
            n_sims,
        )

        simulation = self._simulate(lambda_home, lambda_away, seed=seed, n_sims=n_sims)
        self._assert_invariants(simulation)

        payload = {
            "fixture_id": fixture.fixture_id,
            "league": fixture.league,
            "utc_kickoff": fixture.kickoff.isoformat() if fixture.kickoff else None,
            "teams": {
                "home": fixture.home_team,
                "away": fixture.away_team,
            },
            "expected_goals": {
                "home": lambda_home,
                "away": lambda_away,
            },
            "seed": seed,
            "n_sims": n_sims,
            "probs": simulation["probs"],
            "totals": simulation["totals"],
            "scoreline_topk": simulation["scoreline_topk"],
        }
        return payload

    async def _resolve_fixture(
        self,
        fixture_id: str | None,
        home: str | None,
        away: str | None,
    ) -> FixtureRecord:
        if fixture_id is None and (home is None or away is None):
            raise InvalidPredictionRequest(
                "Either fixture_id or both home and away teams must be provided"
            )

        if fixture_id is None:
            return FixtureRecord(
                fixture_id=0,
                home_team=home or "home",
                away_team=away or "away",
                league=None,
                kickoff=None,
                home_team_id=None,
                away_team_id=None,
            )

        try:
            fixture_int = int(fixture_id)
        except (TypeError, ValueError) as exc:  # pragma: no cover - validation guard
            raise InvalidPredictionRequest("fixture_id must be numeric") from exc

        query = text(
            f"""
            SELECT id, home_team, away_team, league, utc_kickoff, home_team_id, away_team_id
            FROM {self._fixtures_table}
            WHERE id = :fixture_id
            LIMIT 1
            """
        )
        async with self._db_router.session(read_only=True) as session:
            result = await session.execute(query, {"fixture_id": fixture_int})
            row = result.one_or_none()

        if row is None:
            raise FixtureNotFoundError(f"Fixture {fixture_id} not found")

        kickoff = row.utc_kickoff
        if isinstance(kickoff, str):
            try:
                kickoff = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except ValueError:
                kickoff = None
        if isinstance(kickoff, datetime) and kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=UTC)

        return FixtureRecord(
            fixture_id=int(row.id),
            home_team=str(row.home_team),
            away_team=str(row.away_team),
            league=str(row.league) if row.league is not None else None,
            kickoff=kickoff,
            home_team_id=row.home_team_id,
            away_team_id=row.away_team_id,
        )

    async def _load_team_metrics(
        self,
        team_id: int | None,
        team_name: str,
    ) -> TeamMetrics:
        params: dict[str, Any]
        if team_id is not None:
            query = text(
                f"""
                SELECT team_id, team_name, attack_strength, defence_strength,
                       lambda_for, lambda_against, xg_for, xg_against
                FROM {self._metrics_table}
                WHERE team_id = :team_id
                LIMIT 1
                """
            )
            params = {"team_id": int(team_id)}
        else:
            query = text(
                f"""
                SELECT team_id, team_name, attack_strength, defence_strength,
                       lambda_for, lambda_against, xg_for, xg_against
                FROM {self._metrics_table}
                WHERE LOWER(team_name) = LOWER(:team_name)
                LIMIT 1
                """
            )
            params = {"team_name": team_name}

        async with self._db_router.session(read_only=True) as session:
            result = await session.execute(query, params)
            row = result.one_or_none()

        if row is None:
            identifier = team_id if team_id is not None else team_name
            raise MetricsNotFoundError(f"Metrics missing for team {identifier}")

        return TeamMetrics(
            team_id=row.team_id,
            name=row.team_name,
            attack_strength=row.attack_strength,
            defence_strength=row.defence_strength,
            lambda_for=row.lambda_for,
            lambda_against=row.lambda_against,
            xg_for=row.xg_for,
            xg_against=row.xg_against,
        )

    def _estimate_lambdas(
        self,
        home: TeamMetrics,
        away: TeamMetrics,
    ) -> tuple[float, float]:
        home_candidates = list(home.candidates_for_scoring()) + list(
            away.candidates_for_conceding()
        )
        away_candidates = list(away.candidates_for_scoring()) + list(
            home.candidates_for_conceding()
        )

        lambda_home = self._aggregate_lambda(home_candidates)
        lambda_away = self._aggregate_lambda(away_candidates)
        return lambda_home, lambda_away

    @staticmethod
    def _aggregate_lambda(candidates: Iterable[float]) -> float:
        values = [value for value in candidates if value > 0]
        if not values:
            return 1.2
        # Geometric mean is robust for multiplicative strengths
        log_sum = sum(math.log(value) for value in values)
        mean = math.exp(log_sum / len(values))
        return max(0.05, float(mean))

    def _simulate(
        self,
        lambda_home: float,
        lambda_away: float,
        *,
        seed: int,
        n_sims: int,
    ) -> dict[str, Any]:
        rng = np.random.default_rng(seed)
        home_goals = rng.poisson(lambda_home, n_sims)
        away_goals = rng.poisson(lambda_away, n_sims)
        total = float(n_sims)

        counts = Counter(zip(home_goals.tolist(), away_goals.tolist(), strict=False))

        win_home = sum(count for (h, a), count in counts.items() if h > a)
        win_away = sum(count for (h, a), count in counts.items() if h < a)
        draws = total - win_home - win_away

        probs = _normalize_triplet(
            {
                "H": win_home / total,
                "D": draws / total,
                "A": win_away / total,
            }
        )

        over = sum(count for (h, a), count in counts.items() if h + a > 2)
        under = total - over
        over_prob, under_prob = _normalize_pair(over / total, under / total)

        btts_yes = sum(count for (h, a), count in counts.items() if h > 0 and a > 0)
        btts_no = total - btts_yes
        btts_yes_prob, btts_no_prob = _normalize_pair(btts_yes / total, btts_no / total)

        score_probs: list[dict[str, float]] = []
        for (h, a), count in counts.items():
            prob = count / total
            if prob <= 0 or not math.isfinite(prob):
                continue
            score_probs.append({"score": f"{h}:{a}", "probability": prob})

        scoreline_topk = sorted(
            score_probs,
            key=lambda item: (-item["probability"], item["score"]),
        )[: self._scoreline_topk]

        return {
            "probs": probs,
            "totals": {
                "over_2_5": over_prob,
                "under_2_5": under_prob,
                "btts_yes": btts_yes_prob,
                "btts_no": btts_no_prob,
            },
            "scoreline_topk": scoreline_topk,
        }

    @staticmethod
    def _assert_invariants(simulation: Mapping[str, Any]) -> None:
        probs = simulation["probs"]
        totals = simulation["totals"]

        prob_sum = sum(probs.values())
        if not math.isfinite(prob_sum) or abs(prob_sum - 1.0) > _PROB_TOLERANCE:
            raise PredictionEngineError("1X2 probabilities failed to normalise")

        over_sum = totals["over_2_5"] + totals["under_2_5"]
        if not math.isfinite(over_sum) or abs(over_sum - 1.0) > _PROB_TOLERANCE:
            raise PredictionEngineError("Totals probabilities failed to normalise")

        btts_sum = totals["btts_yes"] + totals["btts_no"]
        if not math.isfinite(btts_sum) or abs(btts_sum - 1.0) > _PROB_TOLERANCE:
            raise PredictionEngineError("BTTS probabilities failed to normalise")

        scoreline_topk = simulation.get("scoreline_topk", [])
        if scoreline_topk:
            probs_list = [item["probability"] for item in scoreline_topk]
            if probs_list != sorted(probs_list, reverse=True):
                raise PredictionEngineError("Scoreline topk is not sorted by probability")
            if any(prob <= 0 or not math.isfinite(prob) for prob in probs_list):
                raise PredictionEngineError("Scoreline probabilities contain invalid values")
