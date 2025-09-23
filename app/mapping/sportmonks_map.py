"""
@file: sportmonks_map.py
@description: Helpers for aligning Sportmonks identifiers with internal entities.
@dependencies: csv, pathlib, sqlite3
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from config import Settings

from app.mapping.keys import normalize_name
from app.data_providers.sportmonks.schemas import TeamDTO


@dataclass(slots=True)
class TeamMappingSuggestion:
    sm_team_id: int
    internal_team_id: int
    name_norm: str


@dataclass(slots=True)
class TeamMappingConflict:
    sm_team_id: int
    name_norm: str
    candidates: tuple[int, ...]


class SportmonksMappingRepository:
    """Manage SQLite mapping tables between Sportmonks IDs and internal identifiers."""

    def __init__(self, db_path: str | None = None) -> None:
        settings = Settings()
        self._db_path = Path(db_path or settings.DB_PATH)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_tables()

    def ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS map_teams(
                    sm_team_id INTEGER PRIMARY KEY,
                    internal_team_id INTEGER NOT NULL,
                    name_norm TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS map_leagues(
                    sm_league_id INTEGER PRIMARY KEY,
                    internal_code TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def upsert_team(self, sm_team_id: int, internal_team_id: int, name_norm: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO map_teams(sm_team_id, internal_team_id, name_norm)
                VALUES(?, ?, ?)
                ON CONFLICT(sm_team_id) DO UPDATE SET
                    internal_team_id=excluded.internal_team_id,
                    name_norm=excluded.name_norm
                """,
                (sm_team_id, internal_team_id, name_norm),
            )
            conn.commit()

    def upsert_league(self, sm_league_id: int, internal_code: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO map_leagues(sm_league_id, internal_code)
                VALUES(?, ?)
                ON CONFLICT(sm_league_id) DO UPDATE SET internal_code=excluded.internal_code
                """,
                (sm_league_id, internal_code),
            )
            conn.commit()

    def load_team_map(self) -> dict[int, int]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT sm_team_id, internal_team_id FROM map_teams")
            return {int(row[0]): int(row[1]) for row in cursor.fetchall()}

    def load_league_map(self) -> dict[int, str]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT sm_league_id, internal_code FROM map_leagues")
            return {int(row[0]): str(row[1]) for row in cursor.fetchall()}

    def suggest_team_mappings(
        self,
        teams: Sequence[TeamDTO],
        known_names: Mapping[str, int],
    ) -> tuple[list[TeamMappingSuggestion], list[TeamMappingConflict]]:
        suggestions: list[TeamMappingSuggestion] = []
        conflicts: list[TeamMappingConflict] = []
        for team in teams:
            normalized = team.name_normalized or normalize_name(team.name)
            matches = [
                internal_id for norm, internal_id in known_names.items() if norm == normalized
            ]
            if not matches:
                continue
            unique_matches = sorted(set(matches))
            if len(unique_matches) == 1:
                suggestions.append(
                    TeamMappingSuggestion(
                        sm_team_id=team.team_id,
                        internal_team_id=unique_matches[0],
                        name_norm=normalized,
                    )
                )
            else:
                conflicts.append(
                    TeamMappingConflict(
                        sm_team_id=team.team_id,
                        name_norm=normalized,
                        candidates=tuple(unique_matches),
                    )
                )
        return suggestions, conflicts

    @staticmethod
    def export_conflicts(conflicts: Iterable[TeamMappingConflict], destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sm_team_id", "name_norm", "candidates"])
            for conflict in conflicts:
                writer.writerow([conflict.sm_team_id, conflict.name_norm, ",".join(map(str, conflict.candidates))])
