"""
@file: data_source.py
@description: High-level accessors bridging Sportmonks persistence with feature pipelines.
@dependencies: datetime, json, sqlite3
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from config import Settings


class FixtureContext(NamedTuple):
    fixture: dict[str, Any]
    standings: list[dict[str, Any]]
    injuries: list[dict[str, Any]]
    freshness_hours: float


@dataclass(slots=True)
class SportmonksDataSource:
    """Read Sportmonks ETL outputs from SQLite storage."""

    db_path: Path

    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = Settings()
        resolved = Path(db_path or settings.DB_PATH)
        self.db_path = resolved

    def fixture_context(self, fixture_id: int) -> FixtureContext | None:
        with self._connect() as conn:
            fixture_row = conn.execute(
                "SELECT * FROM sm_fixtures WHERE id = ?", (fixture_id,)
            ).fetchone()
            if not fixture_row:
                return None
            fixture = self._normalize_row(fixture_row)
            league_id = fixture.get("league_id")
            season_id = fixture.get("season_id")
            standings = []
            if league_id is not None and season_id is not None:
                standings_rows = conn.execute(
                    "SELECT * FROM sm_standings WHERE league_id = ? AND season_id = ?",
                    (league_id, season_id),
                ).fetchall()
                standings = [self._normalize_row(row) for row in standings_rows]
            injuries_rows = conn.execute(
                "SELECT * FROM sm_injuries WHERE team_id IN (?, ?) ORDER BY pulled_at_utc DESC",
                (fixture.get("home_id"), fixture.get("away_id")),
            ).fetchall()
            injuries = [self._normalize_row(row) for row in injuries_rows]
            freshness = self._max_freshness_hours([fixture, *standings, *injuries])
            return FixtureContext(fixture, standings, injuries, freshness)

    def latest_pulled_at(self) -> datetime | None:
        with self._connect() as conn:
            timestamps: list[datetime] = []
            for table in ("sm_fixtures", "sm_standings", "sm_injuries", "sm_teams"):
                row = conn.execute(
                    f"SELECT pulled_at_utc FROM {table} ORDER BY pulled_at_utc DESC LIMIT 1"
                ).fetchone()
                if not row:
                    continue
                parsed = _parse_timestamp(row[0])
                if parsed:
                    timestamps.append(parsed)
            if not timestamps:
                return None
            return max(timestamps)

    def freshness_hours(self) -> float | None:
        latest = self.latest_pulled_at()
        if not latest:
            return None
        return (datetime.now(tz=UTC) - latest).total_seconds() / 3600

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _normalize_row(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload_json = payload.get("payload_json")
        if isinstance(payload_json, str):
            try:
                payload["payload_json"] = json.loads(payload_json)
            except json.JSONDecodeError:
                payload["payload_json"] = payload_json
        pulled = payload.get("pulled_at_utc")
        payload["pulled_at_dt"] = _parse_timestamp(pulled)
        return payload

    def _max_freshness_hours(self, rows: Iterable[dict[str, Any]]) -> float:
        ages: list[float] = []
        now = datetime.now(tz=UTC)
        for item in rows:
            pulled = item.get("pulled_at_dt")
            if isinstance(pulled, datetime):
                ages.append((now - pulled).total_seconds() / 3600)
        return max(ages) if ages else 0.0


def _parse_timestamp(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, str):
        candidate = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None
