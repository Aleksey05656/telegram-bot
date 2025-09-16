"""
@file: matrix.py
@description: Model matrix helpers for converting engineered features to GLM inputs.
@dependencies: pandas
@created: 2025-09-16

Helpers for constructing the modelling matrices for home and away Poisson GLMs.
"""

from __future__ import annotations

from typing import Final, Iterable

import pandas as pd

_EMPTY_ERROR = "Cannot prepare a model matrix from an empty dataframe."
_REQUIRED_FEATURE_COLUMNS: Final[set[str]] = {"is_home", "goals_home", "goals_away", "rest_days"}

ModelMatrix = tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]


def _select_feature_columns(df: pd.DataFrame) -> list[str]:
    feature_cols: list[str] = []
    if "rest_days" in df.columns:
        feature_cols.append("rest_days")
    rolling_cols = sorted(
        col for col in df.columns if col.startswith("rolling_xg_for_") or col.startswith("rolling_xg_against_")
    )
    feature_cols.extend(rolling_cols)
    return feature_cols


def _prepare_design_matrix(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    matrix = df.loc[:, list(columns)].copy().astype(float)
    matrix.insert(0, "bias", 1.0)
    return matrix


def to_model_matrix(df: pd.DataFrame) -> ModelMatrix:
    """Convert engineered features into modelling matrices for home and away teams.

    Args:
        df: Dataframe with engineered features returned by :func:`build_features`.

    Returns:
        Tuple containing design matrices and targets for home and away GLMs.

    Raises:
        ValueError: If the dataframe is empty or missing required columns.
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    missing = _REQUIRED_FEATURE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"missing required feature columns: {', '.join(sorted(missing))}")

    feature_columns = _select_feature_columns(df)
    if not feature_columns:
        raise ValueError("no feature columns available for model matrix construction")

    home_mask = df["is_home"] == 1
    away_mask = df["is_home"] == 0
    if not home_mask.any() or not away_mask.any():
        raise ValueError("feature dataframe must contain both home and away rows")

    X_home = _prepare_design_matrix(df.loc[home_mask], feature_columns).reset_index(drop=True)
    y_home = df.loc[home_mask, "goals_home"].reset_index(drop=True).astype(int)

    X_away = _prepare_design_matrix(df.loc[away_mask], feature_columns).reset_index(drop=True)
    y_away = df.loc[away_mask, "goals_away"].reset_index(drop=True).astype(int)

    return X_home, y_home, X_away, y_away
