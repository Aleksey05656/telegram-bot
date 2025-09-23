"""
/**
 * @file: tests/diagnostics/test_data_quality.py
 * @description: Regression tests for data quality duplicate/missing checks.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import pandas as pd

from app.data_quality import DataQualityRunner, default_match_contract


def _base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": [1, 2, 3],
            "home_team": ["A", "B", "C"],
            "away_team": ["B", "C", "D"],
            "home_team_code": ["A", "B", "C"],
            "away_team_code": ["B", "C", "D"],
            "league": ["L1", "L1", "L2"],
            "league_code": ["L1", "L1", "L2"],
            "season": ["2023/24", "2023/24", "2024/25"],
            "season_start": [2023, 2023, 2024],
            "season_end": [2024, 2024, 2025],
            "kickoff_utc": pd.to_datetime([
                "2023-08-10T20:00:00Z",
                "2023-08-11T18:00:00Z",
                "2024-02-01T16:00:00Z",
            ]),
            "home_xg": [1.2, 0.9, 1.1],
            "away_xg": [1.1, 1.4, 0.8],
            "home_xga": [0.9, 1.2, 1.0],
            "away_xga": [1.0, 1.3, 0.7],
        }
    )


def test_duplicate_match_keys_detected() -> None:
    df = _base_frame()
    duplicate = df.iloc[[0]].copy()
    duplicate["match_id"] = 4
    dup_df = pd.concat([df, duplicate], ignore_index=True)

    runner = DataQualityRunner(default_match_contract())
    issues = {issue.name: issue for issue in runner.run_all(dup_df)}

    assert issues["match_keys"].status == "❌"
    assert issues["match_keys"].violations is not None
    assert len(issues["match_keys"].violations) >= 2


def test_missing_values_detected() -> None:
    df = _base_frame()
    df.loc[1, "home_xg"] = None

    runner = DataQualityRunner(default_match_contract())
    issues = {issue.name: issue for issue in runner.run_all(df)}

    assert issues["missing_values"].status == "❌"
    assert issues["missing_values"].violations is not None
    assert {row.column for row in issues["missing_values"].violations.itertuples()} == {"home_xg"}
