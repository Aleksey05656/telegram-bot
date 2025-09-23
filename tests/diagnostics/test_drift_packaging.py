"""
/**
 * @file: tests/diagnostics/test_drift_packaging.py
 * @description: Ensures drift CLI entrypoint works via python -m without sys.path hacks.
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_drift_cli_runs(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "diagtools.drift",
            "--reports-dir",
            str(reports_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    summary_path = reports_dir / "drift_summary.json"
    assert summary_path.exists(), result.stdout
    cli_payload = json.loads(result.stdout)
    assert cli_payload["status"], "CLI payload must expose status"
    expected_rc = 0 if cli_payload["status"] != "FAIL" else 1
    assert result.returncode == expected_rc
