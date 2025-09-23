"""
/**
 * @file: tests/diagnostics/test_drift_thresholds.py
 * @description: Ensures WARN/FAIL thresholds trigger correct statuses and exit codes.
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from diagtools.drift import DriftConfig, DriftThresholds, run


def _frame(seed: int, size: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=size, freq="D")
    seasons = np.full(size, "2024/2025")
    return pd.DataFrame(
        {
            "match_date": dates,
            "league": rng.choice(["EPL", "LaLiga"], size=size),
            "season": seasons,
            "home_xg": rng.normal(1.3, 0.1, size=size),
            "away_xg": rng.normal(1.1, 0.1, size=size),
            "home_xga": rng.normal(1.2, 0.1, size=size),
            "away_xga": rng.normal(1.0, 0.1, size=size),
            "form_home": rng.normal(0.1, 0.2, size=size),
            "form_away": rng.normal(0.1, 0.2, size=size),
            "home_advantage": rng.normal(0.2, 0.02, size=size),
            "fatigue_delta": rng.normal(0.0, 0.1, size=size),
        }
    )


def test_warn_status(tmp_path: Path) -> None:
    reference = _frame(111, 200)
    current = reference.copy()
    current["home_xg"] *= 1.03
    config = DriftConfig(
        reports_dir=tmp_path,
        ref_days=60,
        ref_rolling_days=30,
        thresholds=DriftThresholds(psi_warn=0.02, psi_fail=1.0, ks_p_warn=0.02, ks_p_fail=0.0),
    )
    result = run(config, current_df=current, reference_frames={"anchor": reference})
    assert result.worst_status == "WARN"


def test_fail_exit_code(tmp_path: Path) -> None:
    reference = _frame(222, 240)
    current = reference.copy()
    current["home_xg"] *= 1.6
    current["form_home"] += 0.9
    ref_path = tmp_path / "ref.csv"
    cur_path = tmp_path / "cur.csv"
    reference.to_csv(ref_path, index=False)
    current.to_csv(cur_path, index=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "diagtools.drift",
            "--reports-dir",
            str(tmp_path / "reports"),
            "--current-path",
            str(cur_path),
            "--ref-path",
            str(ref_path),
            "--psi-warn",
            "0.05",
            "--psi-fail",
            "0.1",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
