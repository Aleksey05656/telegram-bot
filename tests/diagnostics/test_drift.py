"""
/**
 * @file: tests/diagnostics/test_drift.py
 * @description: Synthetic PSI/KS drift detection tests.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tools.drift_report import generate_report


def _synthetic(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "home_xg": rng.normal(1.4, 0.2, size=200),
            "away_xg": rng.normal(1.2, 0.25, size=200),
            "home_xga": rng.normal(1.1, 0.2, size=200),
            "away_xga": rng.normal(1.0, 0.25, size=200),
            "form_home": rng.normal(0.0, 0.5, size=200),
            "form_away": rng.normal(0.0, 0.5, size=200),
            "home_advantage": rng.normal(0.2, 0.05, size=200),
            "fatigue_delta": rng.normal(0.0, 0.2, size=200),
            "goals_home": rng.poisson(1.5, size=200),
            "goals_away": rng.poisson(1.3, size=200),
        }
    )


def test_drift_detected(tmp_path: Path) -> None:
    reference = _synthetic(1)
    current = reference.copy()
    current["home_xg"] *= 1.3
    current["form_home"] += 0.5

    ref_path = tmp_path / "ref.csv"
    cur_path = tmp_path / "cur.csv"
    reference.to_csv(ref_path, index=False)
    current.to_csv(cur_path, index=False)

    report = generate_report(
        current_path=str(cur_path),
        reference_path=str(ref_path),
        ref_days=90,
        reports_dir=tmp_path,
        psi_warn=0.1,
        psi_fail=0.2,
    )

    assert any(stat.status == "❌" for stat in report.features)


def test_drift_thresholds(tmp_path: Path, monkeypatch) -> None:
    ref = _synthetic(2)
    cur = _synthetic(2)

    out_dir = tmp_path / "drift"
    out_dir.mkdir()

    ref_path = out_dir / "ref.csv"
    cur_path = out_dir / "cur.csv"
    ref.to_csv(ref_path, index=False)
    cur.to_csv(cur_path, index=False)

    report = generate_report(
        current_path=str(cur_path),
        reference_path=str(ref_path),
        ref_days=90,
        reports_dir=out_dir,
        psi_warn=0.1,
        psi_fail=0.2,
    )

    assert all(stat.status == "✅" for stat in report.features)
