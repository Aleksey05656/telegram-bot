"""
@file: app/lines/mapper.py
@description: Helpers for normalizing external odds rows into internal match identifiers.
@dependencies: datetime, sqlite3, app.mapping.keys
@created: 2025-09-24
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

from app.mapping.keys import build_match_key, normalize_name


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if value is None:
        raise ValueError("kickoff_utc is required for odds mapping")
    if isinstance(value, (int, float)):
        raise TypeError("kickoff_utc must be ISO string or datetime, not numeric")
    text = str(value).strip()
    if not text:
        raise ValueError("kickoff_utc is required for odds mapping")
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid kickoff timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(slots=True)
class LinesMapper:
    """Normalize provider odds rows into deterministic match keys."""

    team_aliases: Mapping[str, str] | None = None
    league_aliases: Mapping[str, str] | None = None
    _team_aliases: dict[str, str] = field(init=False, default_factory=dict, repr=False)
    _league_aliases: dict[str, str] = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._team_aliases = {
            normalize_name(key): value for key, value in (self.team_aliases or {}).items()
        }
        self._league_aliases = {
            normalize_name(key): value for key, value in (self.league_aliases or {}).items()
        }

    def _resolve_team(self, name: str) -> str:
        canonical = self._team_aliases.get(normalize_name(name))
        return canonical or name

    def _resolve_league(self, name: str | None) -> str | None:
        if name is None:
            return None
        canonical = self._league_aliases.get(normalize_name(name))
        return canonical or name

    def normalize_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy of odds row augmented with `match_key` and normalized fields."""

        home = str(row.get("home") or row.get("home_team") or "").strip()
        away = str(row.get("away") or row.get("away_team") or "").strip()
        league = row.get("league")
        kickoff = _parse_datetime(row.get("kickoff_utc"))
        if not home or not away:
            raise ValueError("home and away must be present for odds mapping")
        match_key = build_match_key(self._resolve_team(home), self._resolve_team(away), kickoff)
        normalized = dict(row)
        normalized["match_key"] = match_key
        normalized["league"] = self._resolve_league(league)
        normalized["kickoff_utc"] = kickoff.isoformat().replace("+00:00", "Z")
        normalized.setdefault("home", home)
        normalized.setdefault("away", away)
        return normalized


__all__ = ["LinesMapper"]
