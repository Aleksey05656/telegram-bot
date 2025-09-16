"""
@file: test_features.py
@description: Tests for the feature engineering stage of the data processor pipeline.
@dependencies: pandas, pytest
@created: 2025-09-16

Tests for :mod:`app.data_processor.features`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.features import build_features
from app.data_processor.validate import validate_input


def _make_source_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=6, freq="3D")
    return pd.DataFrame(
        {
            "home_team": ["A", "B", "C", "A", "B", "C"],
            "away_team": ["B", "C", "A", "C", "A", "B"],
            "date": dates,
            "xG_home": [1.2, 0.8, 1.5, 1.1, 0.9, 1.3],
            "xG_away": [0.7, 1.0, 0.6, 1.2, 0.8, 0.9],
            "goals_home": [2, 1, 3, 1, 0, 2],
            "goals_away": [0, 2, 1, 2, 1, 1],
        }
    )


def test_build_features_requires_non_empty_dataframe() -> None:
    with pytest.raises(ValueError, match="empty dataframe"):
        build_features(pd.DataFrame())


def test_build_features_generates_home_and_away_rows() -> None:
    df = validate_input(_make_source_df())
    features = build_features(df, windows=(3, 5))

    assert len(features) == len(df) * 2
    assert set(features["is_home"].unique()) == {0, 1}
    assert features["match_id"].nunique() == len(df)

    expected_cols = {
        "is_home",
        "rest_days",
        "rolling_xg_for_3",
        "rolling_xg_against_3",
        "rolling_xg_for_5",
        "rolling_xg_against_5",
    }
    assert expected_cols.issubset(features.columns)

    assert features["rest_days"].between(0, 14).all()
    rolling = features.filter(regex=r"^rolling_xg_")
    assert (rolling >= 0).all().all()
    assert not rolling.isnull().any().any()
