"""
@file: schemas.py
@description: Pydantic data models for SportMonks entities used in ingestion and analytics layers.
@dependencies: datetime, typing, pydantic
@created: 2025-09-23
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class Participant(BaseModel):
    id: int
    name: str | None = None
    short_code: str | None = Field(None, alias="short_code")
    meta: dict[str, Any] = Field(default_factory=dict)
    type: Literal["team", "referee", "player"] | None = None


class Score(BaseModel):
    id: int | None = None
    participant_id: int | None = Field(None, alias="participant_id")
    description: str | None = Field(None, alias="description")
    score: float | None = Field(None, alias="value")
    type: str | None = Field(None, alias="type")


class Event(BaseModel):
    id: int
    minute: int | None = None
    team_id: int | None = None
    player_id: int | None = None
    type: str | None = None
    result: str | None = None
    related_player_id: int | None = None
    injured: bool = False


class XGValue(BaseModel):
    team_id: int | None = None
    player_id: int | None = None
    value: float | None = Field(None, alias="expected_goals")
    minute: int | None = None
    degraded_mode: bool = False


class LineupPlayerDetail(BaseModel):
    player_id: int
    team_id: int
    position: str | None = None
    formation_position: str | None = None
    is_starting: bool = Field(default=False, alias="is_starting")
    shirt_number: int | None = None
    expected_minutes: int | None = None
    status: str | None = None
    sidelined: list[str] = Field(default_factory=list)
    xg: float | None = None


class TeamStats(BaseModel):
    team_id: int
    fixture_id: int
    xg: float | None = None
    xga: float | None = None
    shots: int | None = None
    shots_on_target: int | None = None
    possession: float | None = None
    corners: int | None = None
    fouls: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None

    @computed_field  # type: ignore[misc]
    @property
    def attack_strength(self) -> float | None:
        if self.xg is None:
            return None
        if self.shots_on_target in (None, 0):
            return self.xg
        return float(self.xg) / max(1, self.shots_on_target)


class Fixture(BaseModel):
    id: int
    league_id: int | None = None
    season_id: int | None = None
    starting_at: datetime | None = Field(None, alias="starting_at")
    status: str | None = None
    state: str | None = None
    venue_id: int | None = None
    participants: list[Participant] = Field(default_factory=list)
    scores: list[Score] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    lineups: list[LineupPlayerDetail] = Field(default_factory=list)
    formations: dict[str, Any] = Field(default_factory=dict)
    xg_fixture: list[XGValue] = Field(default_factory=list)
    odds_pre_match: list["OddsQuote"] = Field(default_factory=list)
    odds_inplay: list["OddsQuote"] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def home_team_id(self) -> int | None:
        for participant in self.participants:
            if participant.meta.get("location") == "home":
                return participant.id
        return None

    @computed_field  # type: ignore[misc]
    @property
    def away_team_id(self) -> int | None:
        for participant in self.participants:
            if participant.meta.get("location") == "away":
                return participant.id
        return None


class StandingRow(BaseModel):
    league_id: int
    season_id: int
    team_id: int
    position: int | None = None
    points: int | None = None
    matches_played: int | None = Field(None, alias="played")
    wins: int | None = None
    draws: int | None = None
    losses: int | None = None
    goals_scored: int | None = Field(None, alias="scored")
    goals_against: int | None = Field(None, alias="against")
    form: list[str] = Field(default_factory=list)


class Market(BaseModel):
    id: int
    key: str
    name: str


class Bookmaker(BaseModel):
    id: int
    name: str
    url: str | None = None


class OddsQuote(BaseModel):
    fixture_id: int
    market_id: int
    bookmaker_id: int
    label: str
    price: float
    probability: float | None = None
    type: Literal["pre-match", "inplay"] = "pre-match"
    pulled_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
