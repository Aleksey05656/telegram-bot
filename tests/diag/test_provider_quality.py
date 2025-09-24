"""
/**
 * @file: tests/diag/test_provider_quality.py
 * @description: Tests provider quality CLI exit codes and report generation.
 * @dependencies: sqlite3, pathlib, pytest, diagtools.provider_quality
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from diagtools import provider_quality


def _prepare_db(path: Path, rows: list[tuple[str, str, str, float, float, float, float]]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE provider_stats (
            provider TEXT,
            market TEXT,
            league TEXT,
            score REAL,
            coverage REAL,
            fresh_share REAL,
            lag_ms REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO provider_stats VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_provider_quality_pass(tmp_path, capsys) -> None:
    db_path = tmp_path / "providers.sqlite3"
    _prepare_db(
        db_path,
        [("csv", "1X2", "EPL", 0.75, 0.8, 0.7, 450)],
    )
    reports_dir = tmp_path / "reports"
    with pytest.raises(SystemExit) as exc:
        provider_quality.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(reports_dir),
                "--min-score",
                "0.6",
                "--min-coverage",
                "0.6",
            ]
        )
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "provider_quality" in out
    assert (reports_dir / "provider_quality.json").exists()
    assert (reports_dir / "provider_quality.md").exists()


def test_provider_quality_fail(tmp_path, capsys) -> None:
    db_path = tmp_path / "providers_fail.sqlite3"
    _prepare_db(
        db_path,
        [("http", "1X2", "EPL", 0.4, 0.5, 0.4, 900)],
    )
    reports_dir = tmp_path / "reports_fail"
    with pytest.raises(SystemExit) as exc:
        provider_quality.main(
            [
                "--db-path",
                str(db_path),
                "--reports-dir",
                str(reports_dir),
                "--min-score",
                "0.6",
                "--min-coverage",
                "0.6",
            ]
        )
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "failing providers" in out
