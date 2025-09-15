"""
@file: test_run_simulation_cli.py
@description: Smoke test for run_simulation CLI with DB write and report.
@dependencies: subprocess, numpy
@created: 2025-09-15
"""
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest


@pytest.mark.needs_np
def test_run_simulation_cli(tmp_path: Path):
    db = tmp_path / "preds.sqlite"
    report = tmp_path / "report.md"
    env = {"PREDICTIONS_DB_URL": str(db)}
    cmd = [
        "python",
        "scripts/run_simulation.py",
        "--season-id",
        "default",
        "--home",
        "H",
        "--away",
        "A",
        "--rho",
        "0.1",
        "--n-sims",
        "512",
        "--calibrate",
        "--write-db",
        "--report-md",
        str(report),
    ]
    subprocess.run(cmd, check=True, env={**env, **os.environ})
    assert report.exists()
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT COUNT(*) FROM predictions")
    assert cur.fetchone()[0] > 0
    conn.close()
