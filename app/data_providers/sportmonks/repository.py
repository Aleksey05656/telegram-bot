"""
@file: repository.py
@description: SQLite persistence helpers for Sportmonks normalized entities.
@dependencies: contextlib, datetime, json, sqlite3
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from config import Settings

from .schemas import FixtureDTO, InjuryDTO, StandingDTO, TeamDTO


class SportmonksRepository:
    """Persist Sportmonks payloads into SQLite tables with idempotent upserts."""

    def __init__(self, db_path: str | None = None) -> None:
        settings = Settings()
        self._db_path = Path(db_path or settings.DB_PATH)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_fixtures(self, fixtures: Sequence[FixtureDTO], *, pulled_at: datetime) -> int:
        return self._upsert_many(
            """
            INSERT INTO sm_fixtures(
                id, league_id, season_id, home_id, away_id, kickoff_utc, status, payload_json, pulled_at_utc
            ) VALUES(:id, :league_id, :season_id, :home_id, :away_id, :kickoff_utc, :status, :payload_json, :pulled_at)
            ON CONFLICT(id) DO UPDATE SET
                league_id=excluded.league_id,
                season_id=excluded.season_id,
                home_id=excluded.home_id,
                away_id=excluded.away_id,
                kickoff_utc=excluded.kickoff_utc,
                status=excluded.status,
                payload_json=excluded.payload_json,
                pulled_at_utc=excluded.pulled_at_utc
            """,
            (
                {
                    "id": dto.fixture_id,
                    "league_id": dto.league_id,
                    "season_id": dto.season_id,
                    "home_id": dto.home_team_id,
                    "away_id": dto.away_team_id,
                    "kickoff_utc": _iso_or_none(dto.kickoff_utc),
                    "status": dto.status,
                    "payload_json": json.dumps(dto.payload, ensure_ascii=False, sort_keys=True),
                    "pulled_at": _iso_timestamp(pulled_at),
                }
                for dto in fixtures
            ),
        )

    def upsert_teams(self, teams: Sequence[TeamDTO], *, pulled_at: datetime) -> int:
        return self._upsert_many(
            """
            INSERT INTO sm_teams(id, name_norm, country, payload_json, pulled_at_utc)
            VALUES(:id, :name_norm, :country, :payload_json, :pulled_at)
            ON CONFLICT(id) DO UPDATE SET
                name_norm=excluded.name_norm,
                country=excluded.country,
                payload_json=excluded.payload_json,
                pulled_at_utc=excluded.pulled_at_utc
            """,
            (
                {
                    "id": dto.team_id,
                    "name_norm": dto.name_normalized,
                    "country": dto.country,
                    "payload_json": json.dumps(dto.payload, ensure_ascii=False, sort_keys=True),
                    "pulled_at": _iso_timestamp(pulled_at),
                }
                for dto in teams
            ),
        )

    def upsert_standings(self, rows: Sequence[StandingDTO], *, pulled_at: datetime) -> int:
        return self._upsert_many(
            """
            INSERT INTO sm_standings(
                league_id, season_id, team_id, position, points, payload_json, pulled_at_utc
            ) VALUES(:league_id, :season_id, :team_id, :position, :points, :payload_json, :pulled_at)
            ON CONFLICT(league_id, season_id, team_id) DO UPDATE SET
                position=excluded.position,
                points=excluded.points,
                payload_json=excluded.payload_json,
                pulled_at_utc=excluded.pulled_at_utc
            """,
            (
                {
                    "league_id": row.league_id,
                    "season_id": row.season_id,
                    "team_id": row.team_id,
                    "position": row.position,
                    "points": row.points,
                    "payload_json": json.dumps(row.payload, ensure_ascii=False, sort_keys=True),
                    "pulled_at": _iso_timestamp(pulled_at),
                }
                for row in rows
            ),
        )

    def upsert_injuries(self, rows: Sequence[InjuryDTO], *, pulled_at: datetime) -> int:
        return self._upsert_many(
            """
            INSERT INTO sm_injuries(
                id, fixture_id, team_id, player_name, status, payload_json, pulled_at_utc
            ) VALUES(:id, :fixture_id, :team_id, :player_name, :status, :payload_json, :pulled_at)
            ON CONFLICT(id) DO UPDATE SET
                fixture_id=excluded.fixture_id,
                team_id=excluded.team_id,
                player_name=excluded.player_name,
                status=excluded.status,
                payload_json=excluded.payload_json,
                pulled_at_utc=excluded.pulled_at_utc
            """,
            (
                {
                    "id": row.injury_id,
                    "fixture_id": row.fixture_id,
                    "team_id": row.team_id,
                    "player_name": row.player_name,
                    "status": row.status,
                    "payload_json": json.dumps(row.payload, ensure_ascii=False, sort_keys=True),
                    "pulled_at": _iso_timestamp(pulled_at),
                }
                for row in rows
            ),
        )

    def upsert_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sm_meta(key, value_text) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value_text=excluded.value_text
                """,
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            cursor = conn.execute("SELECT value_text FROM sm_meta WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def last_sync_timestamp(self) -> datetime | None:
        value = self.get_meta("last_sync_completed_at")
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _upsert_many(self, query: str, rows: Iterable[dict[str, object]]) -> int:
        items = list(rows)
        if not items:
            return 0
        with self._connect() as conn:
            cur = conn.cursor()
            cur.executemany(query, items)
            return cur.rowcount if cur.rowcount != -1 else len(items)


def _iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _iso_timestamp(value)
