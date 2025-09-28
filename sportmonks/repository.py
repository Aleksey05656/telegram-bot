"""
@file: repository.py
@description: Persistence helpers for SportMonks ingestion with Postgres upserts.
@dependencies: asyncio, datetime, json, sqlalchemy, config, database.db_router, sportmonks.schemas
@created: 2025-09-23
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Iterable

import os

from sqlalchemy import text

from config import get_settings
from database import get_db_router
from logger import logger
from .schemas import Fixture, OddsQuote, StandingRow


def _is_offline_env() -> bool:
    for name in ("AMVERA", "USE_OFFLINE_STUBS", "FAILSAFE_MODE"):
        value = os.getenv(name)
        if isinstance(value, str) and value.lower() in {"1", "true", "yes"}:
            return True
    return False


def _resolve_router(settings: Any):
    if _is_offline_env():
        logger.debug("Offline mode detected, SportMonksRepository will skip DB wiring")
        return None
    try:
        return get_db_router(settings)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Failed to initialise DB router for SportMonksRepository: %s", exc)
        return None


class SportMonksRepository:
    """Persist SportMonks payloads into analytical storage."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._router = _resolve_router(self._settings)
        self._startup_lock = asyncio.Lock()
        self._started = False

    async def ensure_ready(self) -> None:
        if self._router is None:
            return
        if self._started:
            return
        async with self._startup_lock:
            if not self._started:
                await self._router.startup()
                self._started = True

    async def upsert_fixture(self, fixture: Fixture, pulled_at: datetime | None = None) -> None:
        if self._router is None:
            logger.debug("Offline mode: skipping fixture upsert for %s", fixture.id)
            return
        await self.ensure_ready()
        payload = json.dumps(fixture.model_dump(mode="json"), ensure_ascii=False)
        pulled = (pulled_at or datetime.utcnow()).isoformat()
        async with self._router.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO sm_fixtures (id, league_id, season_id, home_id, away_id, kickoff_utc, status, payload_json, pulled_at_utc)
                    VALUES (:id, :league_id, :season_id, :home_id, :away_id, :kickoff, :status, :payload, :pulled)
                    ON CONFLICT (id) DO UPDATE SET
                        league_id = EXCLUDED.league_id,
                        season_id = EXCLUDED.season_id,
                        home_id = EXCLUDED.home_id,
                        away_id = EXCLUDED.away_id,
                        kickoff_utc = EXCLUDED.kickoff_utc,
                        status = EXCLUDED.status,
                        payload_json = EXCLUDED.payload_json,
                        pulled_at_utc = EXCLUDED.pulled_at_utc
                    """
                ),
                {
                    "id": fixture.id,
                    "league_id": fixture.league_id,
                    "season_id": fixture.season_id,
                    "home_id": fixture.home_team_id,
                    "away_id": fixture.away_team_id,
                    "kickoff": fixture.starting_at.isoformat() if fixture.starting_at else None,
                    "status": fixture.status,
                    "payload": payload,
                    "pulled": pulled,
                },
            )
            await session.commit()

    async def upsert_team(self, team_payload: dict[str, Any]) -> None:
        team_id = int(team_payload.get("id"))
        if self._router is None:
            logger.debug("Offline mode: skipping team upsert for %s", team_id)
            return
        await self.ensure_ready()
        name_norm = (team_payload.get("name") or team_payload.get("short_code") or "").lower()
        country = team_payload.get("country", {}).get("name") if isinstance(team_payload.get("country"), dict) else team_payload.get("country")
        payload = json.dumps(team_payload, ensure_ascii=False)
        pulled = datetime.utcnow().isoformat()
        async with self._router.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO sm_teams (id, name_norm, country, payload_json, pulled_at_utc)
                    VALUES (:id, :name_norm, :country, :payload, :pulled)
                    ON CONFLICT (id) DO UPDATE SET
                        name_norm = EXCLUDED.name_norm,
                        country = EXCLUDED.country,
                        payload_json = EXCLUDED.payload_json,
                        pulled_at_utc = EXCLUDED.pulled_at_utc
                    """
                ),
                {
                    "id": team_id,
                    "name_norm": name_norm,
                    "country": country,
                    "payload": payload,
                    "pulled": pulled,
                },
            )
            await session.commit()

    async def upsert_standings(self, season_id: int, rows: Iterable[StandingRow]) -> None:
        if self._router is None:
            logger.debug(
                "Offline mode: skipping standings upsert for season %s", season_id
            )
            return
        await self.ensure_ready()
        pulled = datetime.utcnow().isoformat()
        async with self._router.session() as session:
            for row in rows:
                payload = json.dumps(row.model_dump(mode="json"), ensure_ascii=False)
                await session.execute(
                    text(
                        """
                        INSERT INTO sm_standings (league_id, season_id, team_id, position, points, payload_json, pulled_at_utc)
                        VALUES (:league_id, :season_id, :team_id, :position, :points, :payload, :pulled)
                        ON CONFLICT (league_id, season_id, team_id) DO UPDATE SET
                            position = EXCLUDED.position,
                            points = EXCLUDED.points,
                            payload_json = EXCLUDED.payload_json,
                            pulled_at_utc = EXCLUDED.pulled_at_utc
                        """
                    ),
                    {
                        "league_id": row.league_id,
                        "season_id": row.season_id,
                        "team_id": row.team_id,
                        "position": row.position,
                        "points": row.points,
                        "payload": payload,
                        "pulled": pulled,
                    },
                )
            await session.commit()

    async def store_prediction(
        self,
        *,
        fixture: Fixture,
        lambda_home: float,
        lambda_away: float,
        markets: dict[str, Any],
        confidence: float,
        model_version: str,
        features_snapshot: dict[str, Any],
    ) -> None:
        if self._router is None:
            logger.debug(
                "Offline mode: skipping prediction store for fixture %s", fixture.id
            )
            return
        await self.ensure_ready()
        async with self._router.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO predictions (
                        fixture_id,
                        league_id,
                        season_id,
                        home_team_id,
                        away_team_id,
                        match_start,
                        model_name,
                        model_version,
                        lambda_home,
                        lambda_away,
                        prob_home_win,
                        prob_draw,
                        prob_away_win,
                        totals_probs,
                        btts_probs,
                        recommendations,
                        confidence,
                        features_snapshot,
                        meta
                    ) VALUES (
                        :fixture_id,
                        :league_id,
                        :season_id,
                        :home_id,
                        :away_id,
                        :match_start,
                        :model_name,
                        :model_version,
                        :lambda_home,
                        :lambda_away,
                        :prob_home,
                        :prob_draw,
                        :prob_away,
                        :totals,
                        :btts,
                        :recommendations,
                        :confidence,
                        :features,
                        :meta
                    )
                    ON CONFLICT (fixture_id, model_version) DO UPDATE SET
                        lambda_home = EXCLUDED.lambda_home,
                        lambda_away = EXCLUDED.lambda_away,
                        prob_home_win = EXCLUDED.prob_home_win,
                        prob_draw = EXCLUDED.prob_draw,
                        prob_away_win = EXCLUDED.prob_away_win,
                        totals_probs = EXCLUDED.totals_probs,
                        btts_probs = EXCLUDED.btts_probs,
                        recommendations = EXCLUDED.recommendations,
                        confidence = EXCLUDED.confidence,
                        features_snapshot = EXCLUDED.features_snapshot,
                        meta = EXCLUDED.meta,
                        updated_at = NOW()
                    """
                ),
                {
                    "fixture_id": fixture.id,
                    "league_id": fixture.league_id,
                    "season_id": fixture.season_id,
                    "home_id": fixture.home_team_id,
                    "away_id": fixture.away_team_id,
                    "match_start": fixture.starting_at,
                    "model_name": "sportmonks_ingestion",
                    "model_version": model_version,
                    "lambda_home": lambda_home,
                    "lambda_away": lambda_away,
                    "prob_home": markets.get("1x2", {}).get("1"),
                    "prob_draw": markets.get("1x2", {}).get("x"),
                    "prob_away": markets.get("1x2", {}).get("2"),
                    "totals": json.dumps(markets.get("totals"), ensure_ascii=False),
                    "btts": json.dumps(markets.get("btts"), ensure_ascii=False),
                    "recommendations": json.dumps(markets.get("recommendations", {}), ensure_ascii=False),
                    "confidence": confidence,
                    "features": json.dumps(features_snapshot, ensure_ascii=False),
                    "meta": json.dumps({"source": "sportmonks_update"}, ensure_ascii=False),
                },
            )
            await session.commit()

    async def store_odds(self, quotes: Iterable[OddsQuote]) -> None:
        payload = list(quotes)
        if self._router is None:
            logger.debug(
                "Offline mode: skipping odds store for %s quotes",
                len(payload),
            )
            return
        await self.ensure_ready()
        async with self._router.session() as session:
            for quote in payload:
                await session.execute(
                    text(
                        """
                        INSERT INTO odds_snapshots (provider, pulled_at_utc, match_key, league, kickoff_utc, market, selection, price_decimal, extra_json)
                        VALUES (:provider, :pulled, :match_key, :league, :kickoff, :market, :selection, :price, :extra)
                        ON CONFLICT (provider, match_key, market, selection, pulled_at_utc) DO NOTHING
                        """
                    ),
                    {
                        "provider": str(quote.bookmaker_id),
                        "pulled": quote.pulled_at.isoformat() if quote.pulled_at else datetime.utcnow().isoformat(),
                        "match_key": f"{quote.fixture_id}",
                        "league": None,
                        "kickoff": None,
                        "market": str(quote.market_id),
                        "selection": quote.label,
                        "price": quote.price,
                        "extra": json.dumps(quote.extra, ensure_ascii=False),
                    },
                )
            await session.commit()


sportmonks_repository = SportMonksRepository()
