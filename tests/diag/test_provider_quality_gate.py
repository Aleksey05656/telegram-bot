"""
/**
 * @file: tests/diag/test_provider_quality_gate.py
 * @description: Tests exit codes and reporting logic for provider quality diagnostics gate.
 * @dependencies: sqlite3, pytest, diagtools.provider_quality
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from diagtools import provider_quality


def _seed_db(db_path: Path, rows: list[tuple]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE provider_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                league TEXT NOT NULL,
                market TEXT NOT NULL,
                samples INTEGER NOT NULL,
                fresh_success INTEGER NOT NULL,
                fresh_fail INTEGER NOT NULL,
                latency_sum_ms REAL NOT NULL,
                latency_sq_sum REAL NOT NULL,
                stability_z_sum REAL NOT NULL,
                stability_z_abs_sum REAL NOT NULL,
                closing_within_tol INTEGER NOT NULL,
                closing_total INTEGER NOT NULL,
                score REAL NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO provider_stats (
                provider, league, market, samples, fresh_success, fresh_fail,
                latency_sum_ms, latency_sq_sum, stability_z_sum, stability_z_abs_sum,
                closing_within_tol, closing_total, score, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def test_provider_quality_pass(tmp_path: Path) -> None:
    db_path = tmp_path / "pass.sqlite"
    reports_dir = tmp_path / "reports"
    _seed_db(
        db_path,
        [
            (
                "alpha",
                "EPL",
                "1X2",
                500,
                420,
                80,
                25_000.0,
                0.0,
                0.0,
                0.0,
                10,
                12,
                0.82,
                "2025-10-12T00:00:00Z",
            )
        ],
    )
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
                "0.5",
                "--min-samples",
                "200",
            ]
        )
    assert exc.value.code == 0
    summary = json.loads((reports_dir / "provider_quality.json").read_text(encoding="utf-8"))
    assert summary[0]["status"] == "OK"


def test_provider_quality_fail(tmp_path: Path) -> None:
    db_path = tmp_path / "fail.sqlite"
    reports_dir = tmp_path / "reports_fail"
    _seed_db(
        db_path,
        [
            (
                "beta",
                "EPL",
                "1X2",
                400,
                200,
                200,
                40_000.0,
                0.0,
                0.0,
                0.0,
                5,
                10,
                0.25,
                "2025-10-12T00:05:00Z",
            )
        ],
    )
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
                "0.5",
                "--min-samples",
                "200",
            ]
        )
    assert exc.value.code == 2
    summary = json.loads((reports_dir / "provider_quality.json").read_text(encoding="utf-8"))
    assert summary[0]["status"] == "FAIL"


def test_provider_quality_warn_on_low_samples(tmp_path: Path) -> None:
    db_path = tmp_path / "warn.sqlite"
    reports_dir = tmp_path / "reports_warn"
    _seed_db(
        db_path,
        [
            (
                "gamma",
                "EPL",
                "1X2",
                50,
                40,
                10,
                5_000.0,
                0.0,
                0.0,
                0.0,
                2,
                4,
                0.9,
                "2025-10-12T00:10:00Z",
            )
        ],
    )
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
                "0.5",
                "--min-samples",
                "200",
            ]
        )
    assert exc.value.code == 1
    summary = json.loads((reports_dir / "provider_quality.json").read_text(encoding="utf-8"))
    assert summary[0]["status"] == "WARN"
