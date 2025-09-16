"""
@file: features.py
@description: Feature engineering utilities for match level statistics.
@dependencies: pandas
@created: 2025-09-16
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd
from pandas.api.types import is_numeric_dtype

_EMPTY_ERROR = "Cannot build features from an empty dataframe."
_WINDOW_ERROR = "At least one rolling window must be provided."
_NUMERIC_ERROR = "No numeric columns available for rolling aggregations."
_GROUP_ERROR = "group_key '%s' is not present in the dataframe."
_SORT_ERROR = "sort_key '%s' is not present in the dataframe."
_RATIO_ERROR = "ratio column '%s/%s' is not present in the dataframe."
_MATCH_ERROR = "Missing match specific columns: %s"

_MATCH_COLUMNS = {
    "home_team",
    "away_team",
    "date",
    "xG_home",
    "xG_away",
    "goals_home",
    "goals_away",
}

_ROLLING_MAP = {
    "xg_for": "rolling_xg_for",
    "xg_against": "rolling_xg_against",
    "goals_for": "rolling_goals_for",
    "goals_against": "rolling_goals_against",
}


def _prepare_windows(windows: Iterable[int]) -> list[int]:
    """Validate and normalize rolling window values."""
    normalized: list[int] = []
    for window in windows:
        if not isinstance(window, int) or window <= 0:
            msg = f"Rolling window must be a positive integer. Received: {window!r}"
            raise ValueError(msg)
        if window not in normalized:
            normalized.append(window)
    return normalized


def _numeric_columns(df: pd.DataFrame, excluded: Sequence[str]) -> list[str]:
    """Return numeric columns excluding identifiers and sort keys."""
    numeric = [col for col in df.columns if is_numeric_dtype(df[col])]
    return [col for col in numeric if col not in excluded]


def _build_match_features(
    df: pd.DataFrame,
    windows_list: Sequence[int],
    *,
    min_periods: int,
) -> pd.DataFrame:
    missing = [column for column in _MATCH_COLUMNS if column not in df.columns]
    if missing:
        raise KeyError(_MATCH_ERROR % missing)

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date", kind="stable").reset_index(drop=True)
    match_ids = result.index.astype(int)

    optional_passthrough = [col for col in ("season", "season_id") if col in result.columns]

    home = pd.DataFrame(
        {
            "match_id": match_ids,
            "team_id": result["home_team"].astype(str),
            "opponent_id": result["away_team"].astype(str),
            "is_home": 1,
            "date": result["date"],
            "xg_for": result["xG_home"].astype(float),
            "xg_against": result["xG_away"].astype(float),
            "goals_for": result["goals_home"].astype(float),
            "goals_against": result["goals_away"].astype(float),
        }
    )
    away = pd.DataFrame(
        {
            "match_id": match_ids,
            "team_id": result["away_team"].astype(str),
            "opponent_id": result["home_team"].astype(str),
            "is_home": 0,
            "date": result["date"],
            "xg_for": result["xG_away"].astype(float),
            "xg_against": result["xG_home"].astype(float),
            "goals_for": result["goals_away"].astype(float),
            "goals_against": result["goals_home"].astype(float),
        }
    )
    for column in optional_passthrough:
        home[column] = result[column].values
        away[column] = result[column].values

    long_df = pd.concat([home, away], ignore_index=True)
    long_df["target"] = long_df["goals_for"].astype(float)

    long_df = long_df.sort_values(["team_id", "date", "is_home"], kind="stable").reset_index(
        drop=True
    )
    rest_days = (
        long_df.groupby("team_id", sort=False)["date"]
        .diff()
        .dt.days.fillna(0)
        .clip(lower=0)
        .astype(int)
    )
    long_df["rest_days"] = rest_days

    grouped = long_df.groupby("team_id", sort=False)
    for window in windows_list:
        for source, prefix in _ROLLING_MAP.items():
            shifted = grouped[source].shift(1)
            rolled = (
                shifted.rolling(window=window, min_periods=min_periods)
                .mean()
                .reset_index(level=0, drop=True)
            )
            fallback = shifted.reset_index(level=0, drop=True)
            values = rolled.fillna(fallback).fillna(0.0).astype(float)
            long_df[f"{prefix}_{window}"] = values

    long_df = long_df.sort_values(["match_id", "is_home"], kind="stable").reset_index(drop=True)
    return long_df


def _build_generic_features(
    df: pd.DataFrame,
    *,
    group_key: str | None,
    sort_key: str | None,
    windows_list: Sequence[int],
    min_periods: int,
) -> pd.DataFrame:
    result = df.copy()
    excluded_columns: list[str] = []

    if group_key:
        if group_key not in result.columns:
            raise KeyError(_GROUP_ERROR % group_key)
        excluded_columns.append(group_key)

    if sort_key:
        if sort_key not in result.columns:
            raise KeyError(_SORT_ERROR % sort_key)
        excluded_columns.append(sort_key)

    sort_columns: list[str] = []
    if group_key:
        sort_columns.append(group_key)
    if sort_key and sort_key not in sort_columns:
        sort_columns.append(sort_key)

    if sort_columns:
        result = result.sort_values(sort_columns, kind="stable")

    numeric_cols = _numeric_columns(result, excluded_columns)
    if not numeric_cols:
        raise ValueError(_NUMERIC_ERROR)

    def _rolling_features(data: pd.DataFrame) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for window in windows_list:
            rolled = data[numeric_cols].rolling(window=window, min_periods=min_periods).mean()
            rolled = rolled.add_suffix(f"_rolling_mean_{window}")
            frames.append(rolled)
        return pd.concat(frames, axis=1)

    if group_key:
        rolling_parts: list[pd.DataFrame] = []
        for _, group in result.groupby(group_key, sort=False):
            rolling_parts.append(_rolling_features(group))
        rolling_df = pd.concat(rolling_parts).sort_index(kind="stable")
    else:
        rolling_df = _rolling_features(result)

    return result.join(rolling_df)


def build_features(
    df: pd.DataFrame,
    *,
    group_key: str | None = None,
    sort_key: str | None = None,
    windows: Iterable[int] = (3, 5),
    min_periods: int | None = None,
    ratio_pairs: Sequence[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Build rolling statistical features and optional ratios for a dataframe.

    Args:
        df: Input dataframe with match level statistics.
        group_key: Column used to partition rolling computations. When ``None``
            the rolling windows are computed on the entire dataframe.
        sort_key: Column describing chronological order within groups. When
            provided the dataframe is sorted by the requested columns before
            computing rolling values.
        windows: Rolling window sizes used for mean aggregations.
        min_periods: Minimum number of observations required to compute a
            rolling mean. Defaults to ``1`` when not provided.
        ratio_pairs: Optional column pairs ``(numerator, denominator)``. For
            each pair a new ``"{numerator}_per_{denominator}"`` column is
            created.

    Returns:
        A dataframe augmented with rolling features and optional ratios.

    Raises:
        ValueError: If the dataframe is empty, no numeric columns are available
            or when window parameters are invalid.
        KeyError: If required grouping, sorting or ratio columns are missing.
    """
    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    windows_list = _prepare_windows(windows)
    if not windows_list:
        raise ValueError(_WINDOW_ERROR)

    min_periods = 1 if min_periods is None else min_periods

    if _MATCH_COLUMNS.issubset(df.columns):
        result = _build_match_features(df, windows_list, min_periods=min_periods)
    else:
        result = _build_generic_features(
            df,
            group_key=group_key,
            sort_key=sort_key,
            windows_list=windows_list,
            min_periods=min_periods,
        )

    if ratio_pairs:
        for numerator, denominator in ratio_pairs:
            if numerator not in result.columns or denominator not in result.columns:
                raise KeyError(_RATIO_ERROR % (numerator, denominator))
            denom_series = result[denominator]
            if not is_numeric_dtype(denom_series):
                msg = f"Denominator column '{denominator}' must be numeric to compute ratios."
                raise TypeError(msg)
            safe_denom = denom_series.where(denom_series != 0, pd.NA)
            result[f"{numerator}_per_{denominator}"] = result[numerator] / safe_denom

    return result
