"""
@file: test_upsert_idempotent.py
@description: Validate Sportmonks repository upserts remain idempotent and preserve indexes.
@dependencies: pytest, sqlite3, datetime
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.data_providers.sportmonks.repository import SportmonksRepository
from app.data_providers.sportmonks.schemas import FixtureDTO, InjuryDTO


def _init_schema(db_path: Path) -> None:
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
                payload_json TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL
            );
            CREATE TABLE sm_injuries(
                id INTEGER PRIMARY KEY,
                fixture_id INTEGER,
                team_id INTEGER,
                player_name TEXT,
                status TEXT,
                payload_json TEXT NOT NULL,
                pulled_at_utc TEXT NOT NULL
            );
            CREATE INDEX idx_sm_injuries_fixture ON sm_injuries(fixture_id);
            """
        )
    finally:
        conn.close()


def _repo(db_path: Path) -> SportmonksRepository:
    return SportmonksRepository(str(db_path))


def _fixture(pulled: datetime) -> FixtureDTO:
    return FixtureDTO(
        fixture_id=42,
        league_id=8,
        season_id=2024,
        home_team_id=1,
        away_team_id=2,
        kickoff_utc=pulled,
        status="NS",
        payload={"id": 42},
    )


def _injury(pulled: datetime) -> InjuryDTO:
    return InjuryDTO(
        injury_id=900,
        fixture_id=42,
        team_id=1,
        league_id=8,
        player_name="John Doe",
        status="fit",
        payload={"id": 900},
    )


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "sm.sqlite"
    _init_schema(db_path)
    repo = _repo(db_path)
    pulled = datetime(2025, 1, 1, tzinfo=UTC)

    assert repo.upsert_fixtures([_fixture(pulled)], pulled_at=pulled) == 1
    assert repo.upsert_injuries([_injury(pulled)], pulled_at=pulled) == 1

    # Updating with same payload should still report one affected row without duplicates
    assert repo.upsert_fixtures([_fixture(pulled)], pulled_at=pulled) == 1
    assert repo.upsert_injuries([_injury(pulled)], pulled_at=pulled) == 1

    with sqlite3.connect(db_path) as conn:
        fixture_count = conn.execute("SELECT COUNT(*) FROM sm_fixtures").fetchone()[0]
        injury_count = conn.execute("SELECT COUNT(*) FROM sm_injuries").fetchone()[0]
        index_rows = conn.execute("PRAGMA index_list('sm_injuries')").fetchall()

    assert fixture_count == 1
    assert injury_count == 1
    assert any(row[1] == "idx_sm_injuries_fixture" for row in index_rows)
