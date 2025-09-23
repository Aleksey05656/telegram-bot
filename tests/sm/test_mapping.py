"""
@file: test_mapping.py
@description: Test Sportmonks mapping repository utilities.
@dependencies: pytest, pathlib, sqlite3
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.data_providers.sportmonks.schemas import TeamDTO, TeamPayload
from app.mapping.keys import normalize_name
from app.mapping.sportmonks_map import (
    SportmonksMappingRepository,
    TeamMappingConflict,
    TeamMappingSuggestion,
)


def _make_team(team_id: int, name: str) -> TeamDTO:
    payload: TeamPayload = {"id": team_id, "name": name, "country": "England"}
    return TeamDTO(
        team_id=team_id,
        name=name,
        name_normalized=normalize_name(name),
        country="England",
        payload=payload,
    )


def test_mapping_repository_upsert_and_suggest(tmp_path: Path) -> None:
    db_path = tmp_path / "mapping.sqlite"
    repo = SportmonksMappingRepository(str(db_path))
    repo.upsert_team(100, 10, "sample-fc")
    repo.upsert_league(99, "EPL")

    known = {"sample-fc": 10, "mock-united": 20}
    teams = [_make_team(100, "Sample FC"), _make_team(200, "Mock United")]
    suggestions, conflicts = repo.suggest_team_mappings(teams, known)

    assert TeamMappingSuggestion(sm_team_id=100, internal_team_id=10, name_norm="sample-fc") in suggestions
    assert conflicts == []

    repo.upsert_team(200, 20, "mock-united")
    assert repo.load_team_map()[200] == 20
    assert repo.load_league_map()[99] == "EPL"


def test_mapping_export_conflicts(tmp_path: Path) -> None:
    repo = SportmonksMappingRepository(str(tmp_path / "mapping.sqlite"))
    conflicts = [TeamMappingConflict(sm_team_id=1, name_norm="duplicated", candidates=(1, 2))]
    destination = tmp_path / "reports" / "conflicts.csv"
    repo.export_conflicts(conflicts, destination)
    assert destination.exists()
    content = destination.read_text(encoding="utf-8").strip().splitlines()
    assert content[0] == "sm_team_id,name_norm,candidates"
    assert "duplicated" in content[1]
