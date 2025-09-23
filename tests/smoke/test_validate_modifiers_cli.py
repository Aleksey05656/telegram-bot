"""
@file: test_validate_modifiers_cli.py
@description: Smoke test for validate_modifiers CLI.
@dependencies: scripts/validate_modifiers.py
@created: 2025-09-15
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_validate_modifiers_cli(tmp_path: Path) -> None:
    data = tmp_path / "val.csv"
    data.write_text("lambda_home,lambda_away,home_goals,away_goals\n1,1,0,0\n")
    reports_root = tmp_path / "reports"
    report = reports_root / "metrics" / "MODIFIERS_test.md"
    if report.exists():
        report.unlink()
    cmd = [
        "python",
        "scripts/validate_modifiers.py",
        "--season-id",
        "test",
        "--input",
        str(data),
        "--alpha",
        "0.1",
        "--l2",
        "1.0",
    ]
    env = {**os.environ, "REPORTS_DIR": str(reports_root)}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert proc.returncode == 0
    assert report.exists()
