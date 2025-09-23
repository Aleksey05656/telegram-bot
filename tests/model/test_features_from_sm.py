"""
@file: test_features_from_sm.py
@description: Test Sportmonks data source exposes context used by model layer.
@dependencies: pytest, sqlite3, datetime
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.data_providers.sportmonks.repository import SportmonksRepository
from app.data_providers.sportmonks.schemas import FixtureDTO, InjuryDTO, StandingDTO
from app.data_source import SportmonksDataSource


def _prepare_db(db_path: Path) -> SportmonksRepository:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE sm_fixtures(
                id INTEGER PRIMARY KEY,
                league_id INTEGER,
                season_id INTEGER,
                home_id INTEGER,
                away_id INTEGER,
                kickoff_utc TEXT,
                status TEXT,
                payload_json TEXT,
                pulled_at_utc TEXT
            );
            CREATE TABLE sm_teams(
                id INTEGER PRIMARY KEY,
                name_norm TEXT,
                country TEXT,
                payload_json TEXT,
                pulled_at_utc TEXT
            );
            CREATE TABLE sm_standings(
                league_id INTEGER,
                season_id INTEGER,
                team_id INTEGER,
                position INTEGER,
                points INTEGER,
                payload_json TEXT,
                pulled_at_utc TEXT,
                PRIMARY KEY (league_id, season_id, team_id)
            );
            CREATE TABLE sm_injuries(
                id INTEGER PRIMARY KEY,
                fixture_id INTEGER,
                team_id INTEGER,
                player_name TEXT,
                status TEXT,
                payload_json TEXT,
                pulled_at_utc TEXT
            );
            CREATE TABLE sm_meta(
                key TEXT PRIMARY KEY,
                value_text TEXT
            );
            """
        )
    finally:
        conn.close()
    return SportmonksRepository(str(db_path))


def test_fixture_context_contains_standings_and_injuries(tmp_path: Path) -> None:
    db_path = tmp_path / "sportmonks.sqlite"
    repo = _prepare_db(db_path)
    pulled = datetime(2024, 5, 1, tzinfo=UTC)
    repo.upsert_fixtures(
        [
            FixtureDTO(
                fixture_id=42,
                league_id=8,
                season_id=2024,
                home_team_id=10,
                away_team_id=20,
                kickoff_utc=pulled,
                status="NS",
                payload={"id": 42},
            )
        ],
        pulled_at=pulled,
    )
    repo.upsert_standings(
        [
            StandingDTO(
                league_id=8,
                season_id=2024,
                team_id=10,
                position=1,
                points=80,
                payload={"team_id": 10},
            )
        ],
        pulled_at=pulled,
    )
    repo.upsert_injuries(
        [
            InjuryDTO(
                injury_id=500,
                fixture_id=42,
                team_id=10,
                player_name="John Doe",
                status="out",
                payload={"player_name": "John Doe"},
            )
        ],
        pulled_at=pulled,
    )
    data_source = SportmonksDataSource(db_path)
    context = data_source.fixture_context(42)
    assert context is not None
    assert context.standings and context.standings[0]["points"] == 80
    assert context.injuries and context.injuries[0]["player_name"] == "John Doe"
    assert context.freshness_hours >= 0
