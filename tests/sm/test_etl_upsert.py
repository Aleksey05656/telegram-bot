"""
@file: test_etl_upsert.py
@description: Verify idempotent upserts for Sportmonks repository.
@dependencies: pytest, sqlite3, datetime, json
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.data_providers.sportmonks.repository import SportmonksRepository
from app.data_providers.sportmonks.schemas import FixtureDTO, InjuryDTO, StandingDTO, TeamDTO


def _setup_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE sm_fixtures (
                id INTEGER PRIMARY KEY,
                league_id INTEGER,
                season_id INTEGER,
                home_id INTEGER,
                away_id INTEGER,
                kickoff_utc TEXT,
                status TEXT,
                payload_json TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL
            );
            CREATE TABLE sm_teams (
                id INTEGER PRIMARY KEY,
                name_norm TEXT,
                country TEXT,
                payload_json TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL
            );
            CREATE TABLE sm_standings (
                league_id INTEGER,
                season_id INTEGER,
                team_id INTEGER,
                position INTEGER,
                points INTEGER,
                payload_json TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL,
                PRIMARY KEY (league_id, season_id, team_id)
            );
            CREATE TABLE sm_injuries (
                id INTEGER PRIMARY KEY,
                fixture_id INTEGER,
                team_id INTEGER,
                player_name TEXT,
                status TEXT,
                payload_json TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL
            );
            CREATE TABLE sm_meta (
                key TEXT PRIMARY KEY,
                value_text TEXT
            );
            """
        )
    finally:
        conn.close()


def test_repository_upserts_without_duplicates(tmp_path: Path) -> None:
    db_path = tmp_path / "sportmonks.sqlite"
    _setup_schema(db_path)
    repo = SportmonksRepository(str(db_path))
    pulled = datetime.now(tz=UTC)

    fixtures = [
        FixtureDTO(
            fixture_id=1,
            league_id=8,
            season_id=2024,
            home_team_id=10,
            away_team_id=20,
            kickoff_utc=pulled,
            status="NS",
            payload={"id": 1},
        )
    ]
    teams = [
        TeamDTO(
            team_id=10,
            name="Sample",
            name_normalized="sample",
            country="England",
            payload={"id": 10},
        )
    ]
    standings = [
        StandingDTO(
            league_id=8,
            season_id=2024,
            team_id=10,
            position=1,
            points=70,
            payload={"team_id": 10},
        )
    ]
    injuries = [
        InjuryDTO(
            injury_id=100,
            fixture_id=1,
            team_id=10,
            player_name="John Doe",
            status="doubtful",
            payload={"player_name": "John Doe"},
        )
    ]

    assert repo.upsert_fixtures(fixtures, pulled_at=pulled) == 1
    assert repo.upsert_teams(teams, pulled_at=pulled) == 1
    assert repo.upsert_standings(standings, pulled_at=pulled) == 1
    assert repo.upsert_injuries(injuries, pulled_at=pulled) == 1

    # second run should not insert duplicates but update timestamps
    assert repo.upsert_fixtures(fixtures, pulled_at=pulled) == 1
    assert repo.upsert_teams(teams, pulled_at=pulled) == 1

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM sm_fixtures").fetchone()[0]
        assert count == 1
    repo.upsert_meta("last_sync_completed_at", pulled.isoformat())
    assert repo.last_sync_timestamp() is not None
