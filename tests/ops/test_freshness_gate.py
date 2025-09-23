"""
@file: test_freshness_gate.py
@description: Validate freshness diagnostics thresholds and CLI exit codes.
@dependencies: pytest, sqlite3, datetime
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.data_providers.sportmonks.metrics import sm_freshness_hours_max
from diagtools.freshness import evaluate_sportmonks_freshness, main as freshness_main


class _Settings:
    def __init__(self, db_path: Path, warn: float = 12, fail: float = 48) -> None:
        self.DB_PATH = str(db_path)
        self.SM_FRESHNESS_WARN_HOURS = warn
        self.SM_FRESHNESS_FAIL_HOURS = fail


def _prepare_db(db_path: Path, pulled_hours: float) -> None:
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
            CREATE TABLE sm_teams(
                id INTEGER PRIMARY KEY,
                name_norm TEXT,
                country TEXT,
                payload_json TEXT,
                pulled_at_utc TEXT
            );
            """
        )
        pulled_at = datetime.now(tz=UTC) - timedelta(hours=pulled_hours)
        iso = pulled_at.isoformat()
        conn.execute(
            "INSERT INTO sm_fixtures(id, league_id, season_id, home_id, away_id, kickoff_utc, status, payload_json, pulled_at_utc)"
            " VALUES(1, 8, 2024, 1, 2, ?, 'NS', '{}', ?)",
            (iso, iso),
        )
        conn.execute(
            "INSERT INTO sm_standings(league_id, season_id, team_id, position, points, payload_json, pulled_at_utc)"
            " VALUES(8, 2024, 1, 1, 10, '{}', ?)",
            (iso,),
        )
        conn.execute(
            "INSERT INTO sm_injuries(id, fixture_id, team_id, player_name, status, payload_json, pulled_at_utc)"
            " VALUES(1, 1, 1, 'John', 'fit', '{}', ?)",
            (iso,),
        )
        conn.execute(
            "INSERT INTO sm_teams(id, name_norm, country, payload_json, pulled_at_utc)"
            " VALUES(1, 'team', 'EN', '{}', ?)",
            (iso,),
        )
        conn.commit()
    finally:
        conn.close()


def test_freshness_warn_status(tmp_path: Path) -> None:
    db_path = tmp_path / "sm.sqlite"
    _prepare_db(db_path, pulled_hours=20)
    sm_freshness_hours_max.set(0)
    result = evaluate_sportmonks_freshness(_Settings(db_path))
    assert result["status"] == "WARN"
    assert sm_freshness_hours_max._value.get() >= 20


def test_freshness_cli_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "diagtools.freshness.evaluate_sportmonks_freshness",
        lambda _settings: {"status": "FAIL", "note": "", "leagues": {}, "max_hours": None},
    )
    exit_code = freshness_main(["--check"])
    assert exit_code == 2

    monkeypatch.setattr(
        "diagtools.freshness.evaluate_sportmonks_freshness",
        lambda _settings: {"status": "OK", "note": "", "leagues": {}, "max_hours": 0},
    )
    exit_code_ok = freshness_main(["--check"])
    assert exit_code_ok == 0
