"""
@file: features.py
@description: Feature construction utilities for the unified data processor package.
@dependencies: pandas, numpy
@created: 2025-09-16

Feature engineering helpers that expand validated match data into team specific rows.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

_EMPTY_ERROR = "Cannot build features from an empty dataframe."


def _normalise_windows(windows: Iterable[int]) -> tuple[int, ...]:
    cleaned: list[int] = []
    for window in windows:
        try:
            value = int(window)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("rolling windows must be integers") from exc
        if value <= 0:
            raise ValueError("rolling windows must be positive integers")
        cleaned.append(value)
    return tuple(dict.fromkeys(sorted(cleaned)))


def _compute_rest_days(features: pd.DataFrame) -> None:
    rest = (
        features.sort_values(["team", "date", "is_home"])
        .groupby("team")["date"]
        .diff()
        .dt.days
    )
    rest = rest.fillna(14).clip(lower=0, upper=14)
    features["rest_days"] = rest.astype(int)


def _apply_rolling(features: pd.DataFrame, windows: tuple[int, ...]) -> None:
    grouped = features.sort_values(["team", "is_home", "date"]).groupby(
        ["team", "is_home"], group_keys=False
    )
    for window in windows:
        col_for = f"rolling_xg_for_{window}"
        col_against = f"rolling_xg_against_{window}"
        features[col_for] = grouped["xg_for"].transform(
            lambda s, w=window: s.shift().rolling(window=w, min_periods=1).mean()
        )
        features[col_against] = grouped["xg_against"].transform(
            lambda s, w=window: s.shift().rolling(window=w, min_periods=1).mean()
        )

    rolling_cols = [c for c in features.columns if c.startswith("rolling_xg_")]
    if rolling_cols:
        features[rolling_cols] = features[rolling_cols].fillna(0.0)


def build_features(df: pd.DataFrame, *, windows: Iterable[int] = (5, 10)) -> pd.DataFrame:
    """Construct rolling window features for each team and role.

    Args:
        df: Validated dataframe.
        windows: Iterable with rolling window sizes for aggregations.

    Returns:
        Dataframe expanded to team specific rows with engineered features.

    Raises:
        ValueError: If the dataframe is empty or configuration is invalid.
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    window_sizes = _normalise_windows(windows)
    base = df.copy().reset_index(drop=True)
    base["match_id"] = base.index

    home = base.assign(
        team=base["home_team"],
        opponent=base["away_team"],
        is_home=1,
        xg_for=base["xG_home"],
        xg_against=base["xG_away"],
    )
    away = base.assign(
        team=base["away_team"],
        opponent=base["home_team"],
        is_home=0,
        xg_for=base["xG_away"],
        xg_against=base["xG_home"],
    )

    features = pd.concat([home, away], ignore_index=True, copy=False)
    features["is_home"] = features["is_home"].astype(int)
    features["team"] = features["team"].astype(str)
    features["opponent"] = features["opponent"].astype(str)

    _compute_rest_days(features)
    _apply_rolling(features, window_sizes)

    column_order = [
        "match_id",
        "date",
        "team",
        "opponent",
        "is_home",
        "rest_days",
        "xg_for",
        "xg_against",
        "goals_home",
        "goals_away",
    ]
    rolling_cols = [c for c in features.columns if c.startswith("rolling_xg_")]
    for column in rolling_cols:
        if column not in column_order:
            column_order.append(column)

    remaining = [c for c in features.columns if c not in column_order]
    column_order.extend(remaining)

    features = features[column_order].sort_values(["match_id", "is_home", "date"]).reset_index(
        drop=True
    )
    return features
