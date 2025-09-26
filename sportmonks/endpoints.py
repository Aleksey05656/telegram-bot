"""
@file: endpoints.py
@description: High-level SportMonks endpoint wrappers with caching, pagination and parsing into Pydantic schemas.
@dependencies: asyncio, datetime, typing, config, sportmonks.client, sportmonks.cache, sportmonks.schemas
@created: 2025-09-23
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from config import get_settings

from .cache import sportmonks_cache
from .client import SportMonksClient
from .schemas import (
    Bookmaker,
    Fixture,
    LineupPlayerDetail,
    Market,
    OddsQuote,
    Participant,
    Score,
    StandingRow,
    XGValue,
)


class SportMonksEndpoints:
    """Typed façade over raw HTTP client."""

    def __init__(
        self,
        *,
        client: SportMonksClient | None = None,
    ) -> None:
        self.settings = get_settings()
        self.client = client or SportMonksClient()
        self.cache = sportmonks_cache

    async def fixtures_between(
        self,
        start: str,
        end: str,
        *,
        chunk_days: int = 90,
    ) -> list[Fixture]:
        async def loader() -> list[dict[str, Any]]:
            fixtures: list[dict[str, Any]] = []
            async for payload in self.client.chunked_between(
                "/fixtures/between/{start}/{end}",
                start=start,
                end=end,
                chunk_days=chunk_days,
                params={"include": "participants;scores;states"},
            ):
                fixtures.append(payload)
            return fixtures

        raw = await self.cache.get_or_set(
            "fixtures-between",
            (start, end, chunk_days),
            "fixtures_upcoming",
            loader,
        )
        return [self._parse_fixture_summary(item) for item in raw]

    async def fixtures_live(self) -> list[Fixture]:
        async def loader() -> list[dict[str, Any]]:
            payload = await self.client.get_json(
                "/livescores/latest", params={"include": "participants;scores;states"}
            )
            data = payload.get("data", [])
            return data if isinstance(data, list) else []

        raw = await self.cache.get_or_set(
            "fixtures-live",
            ("latest",),
            "fixtures_live",
            loader,
        )
        return [self._parse_fixture_summary(item) for item in raw]

    async def fixture_card(self, fixture_id: int) -> Fixture:
        async def loader() -> dict[str, Any]:
            payload = await self.client.get_json(
                f"/fixtures/{fixture_id}",
                params={
                    "include": (
                        "participants;scores;events;statistics;lineups.details;"
                        "formations;states;lineups.xGLineup;xGFixture"
                    )
                },
            )
            return payload.get("data", {})

        raw = await self.cache.get_or_set(
            "fixture-card",
            (fixture_id,),
            "fixtures_base",
            loader,
        )
        return self._parse_fixture_detail(raw)

    async def expected_lineups(
        self, fixture_ids: Iterable[int]
    ) -> dict[int, tuple[list[LineupPlayerDetail], bool]]:
        fixture_list = sorted(set(int(fx) for fx in fixture_ids))
        if not fixture_list:
            return {}
        filters = ",".join(str(fx) for fx in fixture_list)
        payload = await self.client.get_json(
            "/expected/lineups",
            params={"filters": f"fixtureIds:{filters}"},
        )
        data = payload.get("data", [])
        results: dict[int, tuple[list[LineupPlayerDetail], bool]] = {}
        for item in data if isinstance(data, list) else []:
            fixture_id = int(item.get("fixture_id", 0))
            degraded = False
            players: list[LineupPlayerDetail] = []
            for player in item.get("lineup", []) or item.get("players", []):
                stats = player.get("statistics", {}) or {}
                xg = player.get("xg")
                if xg is None:
                    shots = stats.get("shots", {}) or {}
                    xg = shots.get("total") or shots.get("onTarget")
                    degraded = True
                sidelined = []
                sideline_info = player.get("sidelined") or {}
                if isinstance(sideline_info, dict):
                    reason = sideline_info.get("reason")
                    status = sideline_info.get("status")
                    if reason:
                        sidelined.append(str(reason))
                    if status:
                        sidelined.append(str(status))
                players.append(
                    LineupPlayerDetail(
                        player_id=int(player.get("player_id") or player.get("id")),
                        team_id=int(player.get("team_id") or item.get("team_id") or 0),
                        position=player.get("position"),
                        formation_position=player.get("formation_position"),
                        is_starting=bool(player.get("is_starting", True)),
                        shirt_number=player.get("shirt_number"),
                        expected_minutes=player.get("expected_minutes"),
                        status=player.get("status"),
                        sidelined=sidelined,
                        xg=xg,
                    )
                )
            results[fixture_id] = (players, degraded)
        return results

    async def team_profile(self, team_id: int) -> dict[str, Any]:
        async def loader() -> dict[str, Any]:
            payload = await self.client.get_json(
                f"/teams/{team_id}", params={"include": "squad;coach"}
            )
            return payload.get("data", {})

        return await self.cache.get_or_set(
            "team-profile",
            (team_id,),
            "reference_slow",
            loader,
        )

    async def standings_season(self, season_id: int) -> list[StandingRow]:
        async def loader() -> list[dict[str, Any]]:
            payload = await self.client.get_json(f"/standings/seasons/{season_id}")
            data = payload.get("data", [])
            return data if isinstance(data, list) else []

        raw = await self.cache.get_or_set(
            "standings-season",
            (season_id,),
            "table_base",
            loader,
        )
        return [self._parse_standing_row(season_id, row) for row in raw]

    async def standings_live(self, league_id: int) -> list[StandingRow]:
        payload = await self.client.get_json(f"/standings/live/leagues/{league_id}")
        data = payload.get("data", [])
        if not isinstance(data, list):
            return []
        return [self._parse_standing_row(None, row) for row in data]

    async def odds_pre_match_latest(self) -> list[OddsQuote]:
        async def loader() -> list[dict[str, Any]]:
            payload = await self.client.get_json("/odds/pre-match/latest")
            return payload.get("data", []) if isinstance(payload.get("data"), list) else []

        raw = await self.cache.get_or_set(
            "odds-pre-latest",
            ("latest",),
            "odds_pre_match",
            loader,
        )
        return [self._parse_odds(item, "pre-match") for item in raw]

    async def odds_inplay_latest(self) -> list[OddsQuote]:
        payload = await self.client.get_json("/odds/inplay/latest")
        data = payload.get("data", [])
        rows = data if isinstance(data, list) else []
        quotes = [self._parse_odds(item, "inplay") for item in rows]
        await self.cache.set_ttl(
            "odds-inplay", ("latest",), "odds_inplay", [q.model_dump() for q in quotes]
        )
        return quotes

    async def odds_for_fixture(self, fixture_id: int, *, inplay: bool = False) -> list[OddsQuote]:
        path = "/odds/inplay/fixtures/{fixture_id}" if inplay else "/odds/pre-match/fixtures/{fixture_id}"
        async def loader() -> list[dict[str, Any]]:
            payload = await self.client.get_json(path.format(fixture_id=fixture_id))
            data = payload.get("data", [])
            return data if isinstance(data, list) else []

        ttl_key = "odds_inplay" if inplay else "odds_pre_match"
        raw = await self.cache.get_or_set(
            "odds-fixture",
            (fixture_id, "inplay" if inplay else "pre"),
            ttl_key,
            loader,
        )
        odds_type = "inplay" if inplay else "pre-match"
        return [self._parse_odds(item, odds_type) for item in raw]

    async def odds_reference(self) -> tuple[list[Market], list[Bookmaker]]:
        async def markets_loader() -> list[dict[str, Any]]:
            payload = await self.client.get_json("/odds/markets")
            return payload.get("data", []) if isinstance(payload.get("data"), list) else []

        async def bookmakers_loader() -> list[dict[str, Any]]:
            payload = await self.client.get_json("/odds/bookmakers")
            return payload.get("data", []) if isinstance(payload.get("data"), list) else []

        markets_raw, bookmakers_raw = await asyncio.gather(
            self.cache.get_or_set("odds-markets", ("all",), "reference_slow", markets_loader),
            self.cache.get_or_set("odds-bookmakers", ("all",), "reference_slow", bookmakers_loader),
        )
        return (
            [Market(id=int(item["id"]), key=item.get("key", ""), name=item.get("name", "")) for item in markets_raw],
            [Bookmaker(id=int(item["id"]), name=item.get("name", ""), url=item.get("url")) for item in bookmakers_raw],
        )

    def _parse_fixture_summary(self, payload: dict[str, Any]) -> Fixture:
        participants = [self._parse_participant(part) for part in payload.get("participants", [])]
        scores = [self._parse_score(score) for score in payload.get("scores", [])]
        fixture = Fixture(
            id=int(payload.get("id")),
            league_id=payload.get("league_id"),
            season_id=payload.get("season_id"),
            starting_at=self._parse_dt(payload.get("starting_at")),
            status=payload.get("status"),
            state=(payload.get("states") or [{}])[0].get("state") if payload.get("states") else None,
            venue_id=payload.get("venue_id"),
            participants=participants,
            scores=scores,
        )
        return fixture

    def _parse_fixture_detail(self, payload: dict[str, Any]) -> Fixture:
        fixture = self._parse_fixture_summary(payload)
        fixture.events = [self._parse_event(event) for event in payload.get("events", [])]
        stats_map: dict[str, Any] = {}
        for item in payload.get("statistics", []) or []:
            team_id = item.get("team_id")
            stats_map[str(team_id)] = item.get("stats") or item.get("statistics") or {}
        fixture.statistics = stats_map
        lineups: list[LineupPlayerDetail] = []
        degraded = False
        for lineup in payload.get("lineups", []) or []:
            team_id = lineup.get("team_id")
            for player in lineup.get("details", []) or []:
                player_stats = player.get("statistics", {}) or {}
                xg = player_stats.get("xg")
                if xg is None:
                    shots = player_stats.get("shots", {}) or {}
                    xg = shots.get("total") or shots.get("onTarget")
                    degraded = True
                sidelined: list[str] = []
                status_info = player.get("status")
                if isinstance(status_info, dict):
                    reason = status_info.get("reason")
                    availability = status_info.get("availability")
                    if reason:
                        sidelined.append(str(reason))
                    if availability:
                        sidelined.append(str(availability))
                lineups.append(
                    LineupPlayerDetail(
                        player_id=int(player.get("player_id") or player.get("id")),
                        team_id=int(team_id or player.get("team_id") or 0),
                        position=player.get("position"),
                        formation_position=player.get("formation_position"),
                        is_starting=bool(player.get("is_starting", True)),
                        shirt_number=player.get("shirt_number"),
                        expected_minutes=player.get("expected_minutes"),
                        status=player.get("status") if isinstance(player.get("status"), str) else None,
                        sidelined=sidelined,
                        xg=xg,
                    )
                )
        fixture.lineups = lineups
        fixture.formations = {str(item.get("team_id")): item.get("formation") for item in payload.get("formations", []) or []}
        fixture.xg_fixture = [
            XGValue(
                team_id=item.get("team_id"),
                player_id=item.get("player_id"),
                value=item.get("value") or item.get("expected_goals"),
                minute=item.get("minute"),
                degraded_mode=degraded,
            )
            for item in payload.get("xGFixture", []) or []
        ]
        return fixture

    def _parse_participant(self, payload: dict[str, Any]) -> Participant:
        meta = payload.get("meta") or {}
        if payload.get("type") == "team" and "details" in payload:
            meta = {**meta, **(payload.get("details") or {})}
        return Participant(
            id=int(payload.get("id")),
            name=payload.get("name") or payload.get("short_code"),
            short_code=payload.get("short_code"),
            meta=meta,
            type=payload.get("type"),
        )

    def _parse_score(self, payload: dict[str, Any]) -> Score:
        return Score(
            id=payload.get("id"),
            participant_id=payload.get("participant_id") or payload.get("team_id"),
            description=payload.get("description"),
            score=payload.get("score") or payload.get("value"),
            type=payload.get("type"),
        )

    def _parse_event(self, payload: dict[str, Any]):
        from .schemas import Event

        return Event(
            id=int(payload.get("id")),
            minute=payload.get("minute"),
            team_id=payload.get("team_id"),
            player_id=payload.get("player_id"),
            type=payload.get("type"),
            result=payload.get("result"),
            related_player_id=payload.get("related_player_id"),
            injured=bool(payload.get("injury_time")) or bool(payload.get("injured")),
        )

    def _parse_standing_row(self, season_id: int | None, payload: dict[str, Any]) -> StandingRow:
        league_id = payload.get("league_id") or payload.get("league", {}).get("id")
        season = season_id or payload.get("season_id") or payload.get("season", {}).get("id")
        return StandingRow(
            league_id=int(league_id),
            season_id=int(season),
            team_id=int(payload.get("team_id") or payload.get("team", {}).get("id")),
            position=payload.get("position"),
            points=payload.get("points"),
            matches_played=payload.get("played") or payload.get("games_played"),
            wins=payload.get("win") or payload.get("wins"),
            draws=payload.get("draw") or payload.get("draws"),
            losses=payload.get("loss") or payload.get("losses"),
            goals_scored=payload.get("scored") or payload.get("goals_scored"),
            goals_against=payload.get("against") or payload.get("goals_against"),
            form=self._extract_form(payload),
        )

    def _parse_odds(self, payload: dict[str, Any], odds_type: str) -> OddsQuote:
        fixture_id = int(payload.get("fixture_id") or payload.get("fixture", {}).get("id", 0))
        market = payload.get("market") or {}
        bookmaker = payload.get("bookmaker") or {}
        pulled_at = self._parse_dt(payload.get("updated_at") or payload.get("last_update"))
        probability = payload.get("probability")
        if probability is None and payload.get("decimal"):
            try:
                probability = 1 / float(payload["decimal"])
            except Exception:  # pragma: no cover
                probability = None
        return OddsQuote(
            fixture_id=fixture_id,
            market_id=int(payload.get("market_id") or market.get("id", 0)),
            bookmaker_id=int(payload.get("bookmaker_id") or bookmaker.get("id", 0)),
            label=payload.get("label") or payload.get("name") or "",
            price=float(payload.get("decimal") or payload.get("price", 0.0)),
            probability=probability,
            type="inplay" if odds_type == "inplay" else "pre-match",
            pulled_at=pulled_at,
            extra={
                "handicap": payload.get("handicap"),
                "market_key": market.get("key"),
                "bookmaker": bookmaker.get("name"),
            },
        )

    def _extract_form(self, payload: dict[str, Any]) -> list[str]:
        form = payload.get("form")
        if isinstance(form, str):
            return [part for part in form.split(" ") if part]
        if isinstance(form, list):
            return [str(part) for part in form]
        return []

    def _parse_dt(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None


__all__ = ["SportMonksEndpoints"]
