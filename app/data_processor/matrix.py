"""
@file: matrix.py
@description: Helpers to convert engineered features into numeric matrices.
@dependencies: numpy, pandas
@created: 2025-09-16
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

_EMPTY_ERROR = "Cannot build a model matrix from an empty dataframe."
_FEATURE_COLUMNS_ERROR = "feature_columns must contain at least one column name."
_MISSING_COLUMNS_ERROR = "Missing feature columns: %s"
_NON_NUMERIC_ERROR = "Column '%s' must be numeric to be included in the model matrix."
TARGET_COLUMN = "target"
_IS_HOME_COLUMN = "is_home"
_MATCH_ID_COLUMN = "match_id"


def _normalize_feature_columns(
    df: pd.DataFrame, feature_columns: Iterable[str] | None
) -> list[str]:
    if feature_columns is not None:
        columns = list(feature_columns)
        if not columns:
            raise ValueError(_FEATURE_COLUMNS_ERROR)
        return columns

    excluded = {TARGET_COLUMN, _IS_HOME_COLUMN, _MATCH_ID_COLUMN, "goals_for", "goals_against"}
    columns = [
        column
        for column in df.columns
        if is_numeric_dtype(df[column])
        and column not in excluded
        and not column.startswith("rolling_goals")
    ]
    if not columns:
        raise ValueError(_FEATURE_COLUMNS_ERROR)
    return columns


def _build_design_matrix(
    data: pd.DataFrame,
    columns: list[str],
    *,
    add_intercept: bool,
    dtype: type[np.floating] | type[np.float64],
) -> np.ndarray:
    matrix = data.loc[:, columns].astype(dtype).to_numpy()
    if add_intercept:
        intercept = np.ones((matrix.shape[0], 1), dtype=dtype)
        matrix = np.hstack((intercept, matrix))
    return matrix


def to_model_matrix(
    df: pd.DataFrame,
    feature_columns: Iterable[str] | None = None,
    *,
    add_intercept: bool = True,
    dtype: type[np.floating] | type[np.float64] = np.float64,
):
    """Convert engineered features into design matrices for modelling.

    The helper adapts to two scenarios:
    * Long-format match features containing ``is_home`` and ``target`` columns
      return a tuple ``(X_home, y_home, X_away, y_away)``.
    * Generic feature frames return a single design matrix.
    """
    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    columns = _normalize_feature_columns(df, feature_columns)
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(_MISSING_COLUMNS_ERROR % missing)

    for column in columns:
        if not is_numeric_dtype(df[column]):
            raise TypeError(_NON_NUMERIC_ERROR % column)

    if _IS_HOME_COLUMN in df.columns and TARGET_COLUMN in df.columns:
        home_mask = df[_IS_HOME_COLUMN] == 1
        away_mask = df[_IS_HOME_COLUMN] == 0

        X_home = _build_design_matrix(
            df.loc[home_mask], columns, add_intercept=add_intercept, dtype=dtype
        )
        X_away = _build_design_matrix(
            df.loc[away_mask], columns, add_intercept=add_intercept, dtype=dtype
        )
        y_home = np.log1p(df.loc[home_mask, TARGET_COLUMN].astype(dtype).to_numpy())
        y_away = np.log1p(df.loc[away_mask, TARGET_COLUMN].astype(dtype).to_numpy())
        return X_home, y_home, X_away, y_away

    return _build_design_matrix(df, columns, add_intercept=add_intercept, dtype=dtype)
