"""
@file: provider.py
@description: High level Sportmonks provider with normalization helpers for ETL workflows.
@dependencies: asyncio, datetime, typing
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable, Sequence

from app.mapping.keys import normalize_name

from .client import SportmonksClient
from .schemas import FixtureDTO, InjuryDTO, StandingDTO, TeamDTO


class SportmonksProvider:
    """Fetch and normalize Sportmonks entities into internal DTOs."""

    def __init__(self, client: SportmonksClient | None = None) -> None:
        self._client = client or SportmonksClient()

    @property
    def client(self) -> SportmonksClient:
        return self._client

    async def fetch_fixtures(
        self,
        date_from: datetime,
        date_to: datetime,
        *,
        league_ids: Sequence[str | int] | None = None,
    ) -> list[FixtureDTO]:
        params = self._league_params(league_ids)
        params.update(
            {
                "include": "league;season;participants",
                "from": _fmt_date(date_from),
                "to": _fmt_date(date_to),
            }
        )
        response = await self._client.get("/fixtures", params=params)
        records = _iter_records(response.data)
        fixtures: list[FixtureDTO] = []
        for record in records:
            dto = _parse_fixture(record)
            if dto:
                fixtures.append(dto)
        return fixtures

    async def fetch_teams(self, league_id: str | int) -> list[TeamDTO]:
        response = await self._client.get(f"/leagues/{league_id}/teams", params={"include": "country"})
        teams: list[TeamDTO] = []
        for record in _iter_records(response.data):
            dto = _parse_team(record)
            if dto:
                teams.append(dto)
        return teams

    async def fetch_standings(self, league_id: str | int, season_id: str | int) -> list[StandingDTO]:
        response = await self._client.get(
            f"/standings/season/{season_id}",
            params={"league_ids": str(league_id)},
        )
        standings: list[StandingDTO] = []
        for record in _iter_records(response.data):
            dto = _parse_standing(record)
            if dto:
                standings.append(dto)
        return standings

    async def fetch_injuries(
        self,
        date_from: datetime,
        date_to: datetime,
        *,
        league_ids: Sequence[str | int] | None = None,
    ) -> list[InjuryDTO]:
        params = self._league_params(league_ids)
        params.update({"from": _fmt_date(date_from), "to": _fmt_date(date_to)})
        response = await self._client.get("/injuries", params=params)
        injuries: list[InjuryDTO] = []
        for record in _iter_records(response.data):
            dto = _parse_injury(record)
            if dto:
                injuries.append(dto)
        return injuries

    def _league_params(self, league_ids: Sequence[str | int] | None) -> dict[str, str]:
        resolved = league_ids
        if not resolved:
            allowlist = self._client.config.leagues_allowlist
            if allowlist:
                resolved = allowlist
        if not resolved:
            return {}
        return {"league_ids": ",".join(str(item) for item in resolved)}


def _iter_records(payload: Any) -> Iterable[dict[str, Any]]:
    if not payload:
        return []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _parse_fixture(record: dict[str, Any]) -> FixtureDTO | None:
    fixture_id = _safe_int(record.get("id"))
    if fixture_id is None:
        return None
    league_id = _safe_int(record.get("league_id") or (record.get("league") or {}).get("id"))
    season_id = _safe_int(record.get("season_id") or (record.get("season") or {}).get("id"))
    home_id = _participant_id(record, "home")
    away_id = _participant_id(record, "away")
    kickoff = _parse_datetime(record.get("starting_at") or record.get("kickoff") or record.get("time"))
    status = record.get("status") or (record.get("time") or {}).get("status") if isinstance(record.get("time"), dict) else None
    payload = {
        "id": fixture_id,
        "league_id": league_id,
        "season_id": season_id,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "kickoff": _serialize_datetime(kickoff),
        "status": status or None,
    }
    return FixtureDTO(
        fixture_id=fixture_id,
        league_id=league_id,
        season_id=season_id,
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_utc=kickoff,
        status=status,
        payload=payload,
    )


def _parse_team(record: dict[str, Any]) -> TeamDTO | None:
    team_id = _safe_int(record.get("id"))
    name = (record.get("name") or record.get("display_name") or "").strip()
    if team_id is None or not name:
        return None
    country = None
    country_field = record.get("country")
    if isinstance(country_field, dict):
        country = country_field.get("name") or country_field.get("code")
    payload = {
        "id": team_id,
        "name": name,
        "country": country,
        "short_code": record.get("short_code"),
    }
    return TeamDTO(
        team_id=team_id,
        name=name,
        name_normalized=normalize_name(name),
        country=country,
        payload=payload,
    )


def _parse_standing(record: dict[str, Any]) -> StandingDTO | None:
    team = record.get("team") or record.get("team_id")
    team_id = _safe_int(team.get("id") if isinstance(team, dict) else team)
    if team_id is None:
        return None
    league = _safe_int(record.get("league_id") or (record.get("league") or {}).get("id"))
    season = _safe_int(record.get("season_id") or (record.get("season") or {}).get("id"))
    position = _safe_int(record.get("position"))
    points = _safe_int(record.get("points"))
    payload = dict(record)
    return StandingDTO(
        league_id=league or 0,
        season_id=season or 0,
        team_id=team_id,
        position=position,
        points=points,
        payload=payload,
    )


def _parse_injury(record: dict[str, Any]) -> InjuryDTO | None:
    injury_id = _safe_int(record.get("id"))
    player = (record.get("player") or {}).get("name") if isinstance(record.get("player"), dict) else record.get("player_name")
    if injury_id is None or not player:
        return None
    fixture_id = _safe_int(record.get("fixture_id"))
    team_id = _safe_int((record.get("team") or {}).get("id") if isinstance(record.get("team"), dict) else record.get("team_id"))
    status = record.get("status") or (record.get("type") or {}).get("name") if isinstance(record.get("type"), dict) else None
    payload = {
        "id": injury_id,
        "fixture_id": fixture_id,
        "team_id": team_id,
        "player_name": player,
        "status": status,
        "position": record.get("position"),
    }
    return InjuryDTO(
        injury_id=injury_id,
        fixture_id=fixture_id,
        team_id=team_id,
        player_name=player,
        status=status,
        payload=payload,
    )


def _participant_id(record: dict[str, Any], role: str) -> int | None:
    # Support Sportmonks v3 structure participants -> data -> {id, meta: {location}}
    participants = record.get("participants")
    if isinstance(participants, dict):
        data = participants.get("data")
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                meta = item.get("meta") or {}
                location = (meta or {}).get("location")
                if location == role:
                    pid = _safe_int(item.get("id"))
                    if pid is not None:
                        return pid
    key_variants = [
        f"{role}_team_id",
        f"{role}_team",
        role,
    ]
    for key in key_variants:
        value = record.get(key)
        candidate = None
        if isinstance(value, dict):
            candidate = value.get("id")
        else:
            candidate = value
        pid = _safe_int(candidate)
        if pid is not None:
            return pid
    return None


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=UTC)
    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            return None
        candidate = candidate.replace("Z", "+00:00")
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(candidate, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(candidate)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    if isinstance(raw, dict):
        timestamp = raw.get("timestamp")
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(float(timestamp), tz=UTC)
        iso = raw.get("date_time") or raw.get("date")
        return _parse_datetime(iso)
    return None


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _fmt_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d")


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
