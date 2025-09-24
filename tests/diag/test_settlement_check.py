"""
/**
 * @file: tests/diag/test_settlement_check.py
 * @description: Tests settlement coverage and ROI CLI thresholds.
 * @dependencies: sqlite3, pathlib, pytest, diagtools.settlement_check
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from diagtools import settlement_check


def _prepare_db(path: Path, rows: list[tuple[str, str | None, float | None, str]]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE picks_ledger (
            match_key TEXT,
            outcome TEXT,
            roi REAL,
            created_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO picks_ledger VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_settlement_check_pass(tmp_path, capsys) -> None:
    db_path = tmp_path / "settlement.sqlite3"
    now = "2025-10-07T12:00:00Z"
    _prepare_db(
        db_path,
        [
            ("match-1", "win", 25.0, now),
            ("match-2", "lose", -50.0, now),
            ("match-3", "win", 10.0, now),
        ],
    )
    reports = tmp_path / "reports"
    with pytest.raises(SystemExit) as exc:
        settlement_check.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(reports),
                "--min-coverage",
                "0.6",
                "--roi-threshold",
                "-10.0",
                "--window-days",
                "60",
            ]
        )
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "coverage=" in out
    assert (reports / "settlement_check.json").exists()


def test_settlement_check_fail(tmp_path, capsys) -> None:
    db_path = tmp_path / "settlement_fail.sqlite3"
    now = "2025-10-07T12:00:00Z"
    _prepare_db(
        db_path,
        [
            ("match-1", None, None, now),
            ("match-2", "lose", -30.0, now),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        settlement_check.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(tmp_path / "reports_fail"),
                "--min-coverage",
                "0.8",
                "--roi-threshold",
                "-5.0",
                "--window-days",
                "30",
            ]
        )
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "coverage=" in out


def test_settlement_check_no_picks(tmp_path) -> None:
    db_path = tmp_path / "settlement_empty.sqlite3"
    _prepare_db(db_path, [])
    with pytest.raises(SystemExit) as exc:
        settlement_check.main(["--db-path", str(db_path)])
    assert exc.value.code == 1
