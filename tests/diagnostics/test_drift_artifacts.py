"""
/**
 * @file: tests/diagnostics/test_drift_artifacts.py
 * @description: Verifies drift artifacts (MD/JSON/CSV/PNG and reference parquet) are produced.
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from diagtools.drift import HAS_MPL, DriftConfig, DriftThresholds, run


def _dataset(seed: int, n: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-02-01", periods=n, freq="D")
    leagues = rng.choice(["EPL", "LaLiga", "SerieA"], size=n)
    seasons = np.where(dates.month >= 7, "2024/2025", "2023/2024")
    return pd.DataFrame(
        {
            "match_date": dates,
            "league": leagues,
            "season": seasons,
            "home_xg": rng.normal(1.4, 0.15, size=n),
            "away_xg": rng.normal(1.1, 0.15, size=n),
            "home_xga": rng.normal(1.2, 0.15, size=n),
            "away_xga": rng.normal(1.0, 0.15, size=n),
            "form_home": rng.normal(0.0, 0.25, size=n),
            "form_away": rng.normal(0.0, 0.25, size=n),
            "home_advantage": rng.normal(0.19, 0.03, size=n),
            "fatigue_delta": rng.normal(0.0, 0.15, size=n),
        }
    )


def test_artifacts_created(tmp_path: Path) -> None:
    reference = _dataset(10, 360)
    current = _dataset(11, 160)
    current.loc[current["league"] == "EPL", "home_xg"] *= 1.5
    current.loc[current["league"] == "EPL", "form_home"] += 0.7

    config = DriftConfig(
        reports_dir=tmp_path,
        ref_days=120,
        ref_rolling_days=45,
        thresholds=DriftThresholds(psi_warn=0.1, psi_fail=0.2, ks_p_warn=0.05, ks_p_fail=0.01),
    )
    result = run(config, current_df=current, reference_frames={"anchor": reference})

    assert result.summary_path.exists()
    assert result.json_path.exists()
    for scope in ("global", "league", "season"):
        assert (tmp_path / f"{scope}.csv").exists()
    reference_dir = tmp_path / "reference"
    assert reference_dir.exists()
    parquet_files = list(reference_dir.glob("*.parquet"))
    assert parquet_files, "Expected reference parquet files"
    meta = json.loads((reference_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["anchor"]["rows"] == reference.shape[0]
    sha_files = list(reference_dir.glob("*.sha256"))
    assert sha_files, "Expected checksum files"
    plots = list((tmp_path / "plots").glob("*.png"))
    if HAS_MPL:
        assert plots, "Expected distribution plots"
