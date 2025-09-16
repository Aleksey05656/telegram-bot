"""
@file: test_model_matrix.py
@description: Model matrix tests for the engineered features produced by the data processor.
@dependencies: pandas, pytest
@created: 2025-09-16

Tests for :mod:`app.data_processor.matrix`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.features import build_features
from app.data_processor.matrix import to_model_matrix
from app.data_processor.validate import validate_input


def _make_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "home_team": ["A", "B", "C", "A"],
            "away_team": ["B", "C", "A", "C"],
            "date": pd.date_range("2024-01-01", periods=4, freq="7D"),
            "xG_home": [1.1, 0.9, 1.4, 1.0],
            "xG_away": [0.6, 1.2, 0.8, 1.1],
            "goals_home": [2, 1, 3, 0],
            "goals_away": [0, 2, 1, 1],
        }
    )


def test_to_model_matrix_requires_non_empty_dataframe() -> None:
    with pytest.raises(ValueError, match="empty dataframe"):
        to_model_matrix(pd.DataFrame())


def test_to_model_matrix_produces_bias_and_targets() -> None:
    df = validate_input(_make_source_df())
    features = build_features(df, windows=(2,))
    X_home, y_home, X_away, y_away = to_model_matrix(features)

    assert len(X_home) == len(df)
    assert len(X_away) == len(df)
    assert y_home.notna().all()
    assert y_away.notna().all()

    assert "bias" in X_home.columns
    assert "bias" in X_away.columns
    assert all(col.startswith("rolling_xg_") or col == "rest_days" or col == "bias" for col in X_home.columns)
    assert set(y_home.tolist()) == set(df["goals_home"].tolist())
    assert set(y_away.tolist()) == set(df["goals_away"].tolist())
