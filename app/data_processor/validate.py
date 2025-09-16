"""
@file: validate.py
@description: Input validation helpers for the consolidated data processor pipeline.
@dependencies: pandas, numpy
@created: 2025-09-16

Validation helpers for match-level raw datasets that feed the feature builder.
"""

from __future__ import annotations

from typing import Final, Iterable

import numpy as np
import pandas as pd

_EMPTY_ERROR: Final[str] = "Input dataframe is empty; validation requires source data."
_REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "home_team",
    "away_team",
    "date",
    "xG_home",
    "xG_away",
    "goals_home",
    "goals_away",
)
_TEAM_COLUMNS: Final[tuple[str, str]] = ("home_team", "away_team")
_XG_COLUMNS: Final[tuple[str, str]] = ("xG_home", "xG_away")
_GOAL_COLUMNS: Final[tuple[str, str]] = ("goals_home", "goals_away")


def _ensure_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def _validate_team_columns(df: pd.DataFrame) -> None:
    for column in _TEAM_COLUMNS:
        if df[column].isnull().any():
            raise ValueError(f"team column '{column}' contains null values")
        coerced = df[column].astype(str).str.strip()
        if (coerced == "").any():
            raise ValueError(f"team column '{column}' contains empty strings")
        df[column] = coerced


def _validate_numeric(df: pd.DataFrame, columns: Iterable[str], *, integer: bool = False) -> None:
    for column in columns:
        series = pd.to_numeric(df[column], errors="coerce")
        if series.isnull().any():
            raise ValueError(f"column '{column}' must be numeric")
        if (series < 0).any():
            raise ValueError(f"column '{column}' must be non-negative")
        if integer:
            if not np.all(np.isclose(series, series.round())):
                raise ValueError(f"column '{column}' must contain integer values")
            series = series.round().astype(int)
        df[column] = series


def _validate_date(df: pd.DataFrame) -> None:
    converted = pd.to_datetime(df["date"], errors="coerce", utc=False)
    if converted.isnull().any():
        raise ValueError("column 'date' must contain valid datetime values")
    df["date"] = converted.dt.tz_localize(None)


def validate_input(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise a raw dataframe prior to feature engineering.

    Args:
        df: Raw dataframe with match level observations.

    Returns:
        A validated dataframe copy with consistent dtypes.

    Raises:
        ValueError: If the dataframe is empty or violates schema constraints.
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    df = df.copy()
    _ensure_columns(df, _REQUIRED_COLUMNS)
    _validate_date(df)
    _validate_team_columns(df)
    _validate_numeric(df, _XG_COLUMNS, integer=False)
    _validate_numeric(df, _GOAL_COLUMNS, integer=True)

    duplicates = df.duplicated(subset=["home_team", "away_team", "date"], keep=False)
    if duplicates.any():
        duplicated_rows = df.loc[duplicates, ["home_team", "away_team", "date"]]
        formatted = duplicated_rows.to_dict(orient="records")
        raise ValueError(f"duplicate match entries detected: {formatted}")

    return df.reset_index(drop=True)
