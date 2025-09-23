"""
@file: test_mapping_collisions.py
@description: Ensure name collisions are exported to CSV and marked handled.
@dependencies: pytest, pathlib
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.data_providers.sportmonks.schemas import TeamDTO
from app.mapping.keys import normalize_name
import scripts.sm_sync as sm_sync


def _team(team_id: int, name: str) -> TeamDTO:
    return TeamDTO(
        team_id=team_id,
        name=name,
        name_normalized=normalize_name(name),
        country="England",
        payload={"id": team_id, "name": name},
    )


def test_collision_report_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    teams = [_team(1, "Example"), _team(2, "Example")]
    status = sm_sync._handle_team_collisions(teams)
    assert status == "handled"
    report_path = Path("reports") / "diagnostics" / "sportmonks_team_collisions.csv"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8").splitlines()
    assert "name_norm" in content[0]
    assert "example" in content[1]


def test_collision_status_clean_when_unique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    teams = [_team(1, "Example"), _team(2, "Other")]
    status = sm_sync._handle_team_collisions(teams)
    assert status == "clean"
    report_path = Path("reports") / "diagnostics" / "sportmonks_team_collisions.csv"
    assert not report_path.exists()
