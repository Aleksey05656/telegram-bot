"""
/**
 * @file: tests/diagnostics/test_drift_strata.py
 * @description: Validates stratified PSI/KS statistics per league and season.
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from diagtools.drift import DriftConfig, DriftThresholds, run


def _make_frame(seed: int, start: pd.Timestamp, n: int, leagues: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = start + pd.to_timedelta(rng.integers(0, 90, size=n), unit="D")
    league = rng.choice(leagues, size=n)
    seasons = np.where(dates.month >= 7, "2024/2025", "2023/2024")
    base = pd.DataFrame(
        {
            "match_date": dates,
            "league": league,
            "season": seasons,
            "home_xg": rng.normal(1.4, 0.2, size=n),
            "away_xg": rng.normal(1.1, 0.2, size=n),
            "home_xga": rng.normal(1.2, 0.2, size=n),
            "away_xga": rng.normal(1.0, 0.2, size=n),
            "form_home": rng.normal(0.0, 0.3, size=n),
            "form_away": rng.normal(0.0, 0.3, size=n),
            "home_advantage": rng.normal(0.18, 0.02, size=n),
            "fatigue_delta": rng.normal(0.0, 0.2, size=n),
        }
    )
    return base.sort_values("match_date").reset_index(drop=True)


def test_stratified_drift_detects_league_and_season(tmp_path: Path) -> None:
    leagues = ["EPL", "LaLiga"]
    anchor = _make_frame(101, pd.Timestamp("2023-01-01"), 400, leagues)
    rolling = anchor[anchor["match_date"] >= anchor["match_date"].max() - timedelta(days=60)].reset_index(drop=True)
    current = _make_frame(202, pd.Timestamp("2024-03-01"), 160, leagues)
    mask = current["league"] == "EPL"
    current.loc[mask, "home_xg"] *= 1.35
    current.loc[mask, "form_home"] += 0.6
    current.loc[mask, "home_advantage"] += 0.05

    config = DriftConfig(
        reports_dir=tmp_path,
        ref_days=120,
        ref_rolling_days=45,
        thresholds=DriftThresholds(psi_warn=0.1, psi_fail=0.2, ks_p_warn=0.05, ks_p_fail=0.01),
    )
    result = run(
        config,
        current_df=current,
        reference_frames={"anchor": anchor, "rolling": rolling},
    )

    anchor_status = result.status_by_reference["anchor"]
    assert anchor_status["league"] == "FAIL"
    assert anchor_status["season"] in {"WARN", "FAIL"}
    league_metrics = [m for m in result.metrics if m.scope == "league" and m.identifier == "EPL"]
    assert league_metrics, "Expected league-specific metrics"
    assert any(m.psi >= 0.2 for m in league_metrics), "PSI should highlight EPL drift"
