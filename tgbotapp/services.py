"""
@file: tgbotapp/services.py
@description: Default service implementations for Telegram handlers.
@dependencies: asyncio, math, typing, app.integrations
@created: 2025-09-19
"""
from __future__ import annotations

import asyncio
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.integrations.sportmonks_client import SportMonksClient
from logger import logger
from workers.task_manager import task_manager


class MatchNotFoundError(RuntimeError):
    """Raised when fixture is missing in repository."""


class SportMonksFixturesRepository:
    """Fetch fixtures via SportMonks client with async-friendly wrappers."""

    def __init__(self, client: SportMonksClient | None = None):
        self._client = client or SportMonksClient()
        self._cache: dict[int, dict[str, Any]] = {}

    async def list_fixtures_for_date(self, target_date: date) -> list[dict[str, Any]]:
        raw = await asyncio.to_thread(
            self._client.fixtures_by_date,
            target_date.strftime("%Y-%m-%d"),
        )
        fixtures = [self._normalize_fixture(item) for item in raw]
        for fixture in fixtures:
            self._cache[fixture["id"]] = fixture
        return fixtures

    async def get_fixture(self, fixture_id: int) -> dict[str, Any] | None:
        cached = self._cache.get(int(fixture_id))
        if cached:
            return cached
        today = datetime.now(UTC).date()
        search_dates = [today + timedelta(days=offset) for offset in range(-1, 3)]
        for target in search_dates:
            try:
                await self.list_fixtures_for_date(target)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("Fixture fetch failed for %s: %s", target, exc)
                continue
            cached = self._cache.get(int(fixture_id))
            if cached:
                return cached
        return None

    def _normalize_fixture(self, raw: dict[str, Any]) -> dict[str, Any]:
        fixture_id = int(raw.get("id") or raw.get("fixture_id") or 0)
        home = self._extract_team(raw, "home")
        away = self._extract_team(raw, "away")
        league = (
            raw.get("league")
            or raw.get("league_name")
            or raw.get("league_id")
            or (raw.get("league", {}) or {}).get("name")
        )
        kickoff = self._extract_datetime(raw)
        return {
            "id": fixture_id,
            "home": home,
            "away": away,
            "league": league or "",
            "kickoff": kickoff,
        }

    @staticmethod
    def _extract_team(raw: dict[str, Any], key: str) -> str:
        direct = raw.get(key)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        nested = raw.get(f"{key}_team") or raw.get(f"{key}_team_name")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
        nested_obj = raw.get(f"{key}Team") or raw.get(f"{key}TeamData")
        if isinstance(nested_obj, dict):
            name = nested_obj.get("name") or nested_obj.get("data", {}).get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        return "—"

    @staticmethod
    def _extract_datetime(raw: dict[str, Any]) -> datetime:
        candidates = [
            raw.get("kickoff"),
            raw.get("starting_at", {}).get("date_time") if isinstance(raw.get("starting_at"), dict) else None,
            raw.get("starting_at", {}).get("timestamp") if isinstance(raw.get("starting_at"), dict) else None,
            raw.get("date"),
        ]
        for value in candidates:
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=UTC)
            if isinstance(value, int | float):
                return datetime.fromtimestamp(float(value), tz=UTC)
            if isinstance(value, str) and value:
                for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(value.replace("Z", "+00:00"), fmt)
                        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                    except ValueError:
                        continue
        return datetime.now(UTC)


class DeterministicPredictorService:
    """Deterministic predictor that derives markets from Poisson goals."""

    def __init__(self, fixtures_repo: SportMonksFixturesRepository):
        self._fixtures = fixtures_repo

    async def get_prediction(self, fixture_id: int) -> dict[str, Any]:
        fixture = await self._fixtures.get_fixture(int(fixture_id))
        if not fixture:
            raise MatchNotFoundError(f"Fixture {fixture_id} not found")
        lam_home, lam_away = self._estimate_lambdas(int(fixture_id))
        scores = self._score_distribution(lam_home, lam_away)
        prob_home = sum(prob for (home, away), prob in scores.items() if home > away)
        prob_draw = sum(prob for (home, away), prob in scores.items() if home == away)
        prob_away = 1.0 - prob_home - prob_draw
        over_25 = sum(prob for (home, away), prob in scores.items() if home + away > 2)
        btts = sum(prob for (home, away), prob in scores.items() if home > 0 and away > 0)
        top_scores = [
            {"score": f"{home}:{away}", "probability": prob}
            for (home, away), prob in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:6]
        ]
        payload = {
            "fixture": fixture,
            "markets": {
                "1x2": {"home": prob_home, "draw": prob_draw, "away": prob_away},
            },
            "totals": {"2.5": {"over": over_25, "under": 1 - over_25}},
            "both_teams_to_score": {"yes": btts, "no": 1 - btts},
            "top_scores": top_scores,
        }
        return payload

    @staticmethod
    def _estimate_lambdas(fixture_id: int) -> tuple[float, float]:
        base = 1.2 + (fixture_id % 5) * 0.1
        variance = 0.8 + (fixture_id % 3) * 0.05
        return max(0.6, base), max(0.4, variance)

    @staticmethod
    def _score_distribution(lambda_home: float, lambda_away: float) -> dict[tuple[int, int], float]:
        limit = 6
        scores: dict[tuple[int, int], float] = {}
        total = 0.0
        for home in range(limit + 1):
            for away in range(limit + 1):
                prob = _poisson_pmf(home, lambda_home) * _poisson_pmf(away, lambda_away)
                scores[(home, away)] = prob
                total += prob
        if total <= 0:
            return {(0, 0): 1.0}
        return {score: prob / total for score, prob in scores.items()}


class TaskManagerQueue:
    """Adapter around TaskManager for enqueueing prediction jobs."""

    def __init__(self):
        self._manager = task_manager

    def enqueue(self, chat_id: int, home_team: str, away_team: str) -> str | None:
        job_id = services_uuid()
        try:
            job = self._manager.enqueue_prediction(chat_id, home_team, away_team, job_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Не удалось поставить задачу в очередь: %s", exc)
            return None
        if job is None:
            return None
        return job_id


def services_uuid() -> str:
        return datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam**k / math.factorial(k)
