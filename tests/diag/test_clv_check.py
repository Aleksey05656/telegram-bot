"""
/**
 * @file: tests/diag/test_clv_check.py
 * @description: Tests for diagtools.clv_check CLI exit codes and artifact generation.
 * @dependencies: sqlite3, pathlib, diagtools.clv_check
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from diagtools import clv_check


def _init_db(path: Path, values: list[float]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE picks_ledger (clv_pct REAL)")
        for value in values:
            conn.execute("INSERT INTO picks_ledger (clv_pct) VALUES (?)", (float(value),))
        conn.commit()


def test_clv_check_fails_without_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    reports_dir = tmp_path / "reports"
    _init_db(db_path, [])
    with pytest.raises(SystemExit) as excinfo:
        clv_check.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(reports_dir),
                "--threshold",
                "-5.0",
            ]
        )
    assert excinfo.value.code == 1
    assert (reports_dir / "value_clv.json").exists()
    assert (reports_dir / "value_clv.md").exists()


def test_clv_check_fails_when_below_threshold(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    reports_dir = tmp_path / "reports"
    _init_db(db_path, [-10.0, -8.0])
    with pytest.raises(SystemExit) as excinfo:
        clv_check.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(reports_dir),
                "--threshold",
                "-5.0",
            ]
        )
    assert excinfo.value.code == 2
    payload = json.loads((reports_dir / "value_clv.json").read_text(encoding="utf-8"))
    assert payload["avg_clv"] < -5.0


def test_clv_check_succeeds_with_positive_average(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    reports_dir = tmp_path / "reports"
    _init_db(db_path, [2.0, 4.0, 6.0])
    with pytest.raises(SystemExit) as excinfo:
        clv_check.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(reports_dir),
                "--threshold",
                "-1.0",
            ]
        )
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "CLV summary" in out
    payload = json.loads((reports_dir / "value_clv.json").read_text(encoding="utf-8"))
    assert payload["avg_clv"] > 0
