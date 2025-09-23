"""
@file: test_features_ingestion.py
@description: Verify prediction facade enriches Sportmonks context without NaN values.
@dependencies: pytest, sqlite3, datetime, math
"""

from __future__ import annotations

import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.bot.services import PredictionFacade
from app.data_providers.sportmonks.repository import SportmonksRepository
from app.data_providers.sportmonks.schemas import FixtureDTO, InjuryDTO, StandingDTO
from app.data_source import SportmonksDataSource


def _init_db(db_path: Path) -> SportmonksRepository:
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


def _build_prediction_payload() -> dict[str, object]:
    kickoff = datetime(2025, 2, 14, 18, 0, tzinfo=UTC)
    return {
        "id": 42,
        "fixture": {
            "id": 42,
            "home": "Example FC",
            "away": "Mock United",
            "league": "EPL",
            "kickoff": kickoff,
        },
        "markets": {"1x2": {"home": 0.52, "draw": 0.28, "away": 0.20}},
        "totals": {"2.5": {"over": 0.55, "under": 0.45}},
        "both_teams_to_score": {"yes": 0.6, "no": 0.4},
        "top_scores": [{"score": "1:0", "probability": 0.2}, {"score": "2:1", "probability": 0.18}],
    }


@pytest.mark.asyncio
async def test_prediction_facade_enriches_context(tmp_path: Path) -> None:
    db_path = tmp_path / "sm.sqlite"
    repo = _init_db(db_path)
    pulled = datetime(2025, 2, 14, 12, 0, tzinfo=UTC)

    repo.upsert_fixtures(
        [
            FixtureDTO(
                fixture_id=42,
                league_id=8,
                season_id=2024,
                home_team_id=501,
                away_team_id=502,
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
                team_id=501,
                position=1,
                points=65,
                payload={"team_id": 501},
            )
        ],
        pulled_at=pulled,
    )
    repo.upsert_injuries(
        [
            InjuryDTO(
                injury_id=900,
                fixture_id=42,
                team_id=501,
                league_id=8,
                player_name="John Doe",
                status="out",
                payload={"player": "John Doe"},
            )
        ],
        pulled_at=pulled,
    )

    data_source = SportmonksDataSource(db_path)
    facade: PredictionFacade = object.__new__(PredictionFacade)
    facade._fixtures = None  # type: ignore[attr-defined]
    facade._predictor = None  # type: ignore[attr-defined]
    facade._data_source = data_source  # type: ignore[attr-defined]

    prediction = facade._to_prediction(_build_prediction_payload())

    assert prediction.freshness_hours is not None and prediction.freshness_hours >= 0
    assert prediction.standings and prediction.standings[0]["points"] == 65
    assert prediction.injuries and prediction.injuries[0]["player_name"] == "John Doe"

    for modifier in prediction.modifiers:
        assert not math.isnan(float(modifier.get("delta", 0.0)))
        assert not math.isnan(float(modifier.get("impact", 0.0)))

    for value in prediction.delta_probabilities.values():
        assert not math.isnan(float(value))
