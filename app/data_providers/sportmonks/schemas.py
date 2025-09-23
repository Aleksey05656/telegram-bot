"""
@file: schemas.py
@description: Typed data transfer objects for Sportmonks normalized entities.
@dependencies: dataclasses, datetime, typing
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict


class TeamPayload(TypedDict, total=False):
    id: int
    name: str
    country: str | None
    short_code: str | None


class LeaguePayload(TypedDict, total=False):
    id: int
    name: str
    code: str | None
    season_id: int | None


class FixturePayload(TypedDict, total=False):
    id: int
    league_id: int | None
    season_id: int | None
    home_team_id: int | None
    away_team_id: int | None
    kickoff: str | None
    status: str | None


class InjuryPayload(TypedDict, total=False):
    id: int
    fixture_id: int | None
    team_id: int | None
    player_name: str | None
    status: str | None
    position: str | None


@dataclass(slots=True)
class TeamDTO:
    team_id: int
    name: str
    name_normalized: str
    country: str | None
    payload: TeamPayload


@dataclass(slots=True)
class LeagueDTO:
    league_id: int
    name: str
    code: str | None
    season_id: int | None
    payload: LeaguePayload


@dataclass(slots=True)
class FixtureDTO:
    fixture_id: int
    league_id: int | None
    season_id: int | None
    home_team_id: int | None
    away_team_id: int | None
    kickoff_utc: datetime | None
    status: str | None
    payload: FixturePayload


@dataclass(slots=True)
class StandingDTO:
    league_id: int
    season_id: int
    team_id: int
    position: int | None
    points: int | None
    payload: dict[str, object]


@dataclass(slots=True)
class InjuryDTO:
    injury_id: int
    fixture_id: int | None
    team_id: int | None
    player_name: str
    status: str | None
    payload: InjuryPayload
