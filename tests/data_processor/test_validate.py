"""
@file: test_validate.py
@description: Validation tests for the data processor input normalisation stage.
@dependencies: pandas, pytest
@created: 2025-09-16

Tests for :mod:`app.data_processor.validate`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.validate import validate_input


def _make_valid_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "home_team": ["Team A", "Team B"],
            "away_team": ["Team C", "Team A"],
            "date": ["2024-01-01", "2024-01-05"],
            "xG_home": [1.2, 0.9],
            "xG_away": [0.7, 1.1],
            "goals_home": [2, 1],
            "goals_away": [0, 2],
        }
    )


def test_validate_input_rejects_empty_dataframe() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_input(pd.DataFrame())


def test_validate_input_returns_copy_with_converted_types() -> None:
    df = _make_valid_df()
    validated = validate_input(df)

    assert not validated.empty
    assert validated is not df
    assert pd.api.types.is_datetime64_any_dtype(validated["date"])
    assert validated["home_team"].tolist() == ["Team A", "Team B"]
    assert validated["goals_home"].dtype.kind in {"i", "u"}


def test_validate_input_missing_column_raises() -> None:
    df = _make_valid_df().drop(columns=["xG_home"])

    with pytest.raises(ValueError, match="missing required columns"):
        validate_input(df)


def test_validate_input_invalid_numeric_values() -> None:
    df = _make_valid_df()
    df.loc[0, "xG_home"] = -0.1

    with pytest.raises(ValueError, match="non-negative"):
        validate_input(df)


def test_validate_input_invalid_goal_type() -> None:
    df = _make_valid_df()
    df.loc[0, "goals_home"] = 1.5

    with pytest.raises(ValueError, match="integer values"):
        validate_input(df)


def test_validate_input_invalid_date() -> None:
    df = _make_valid_df()
    df.loc[0, "date"] = "not-a-date"

    with pytest.raises(ValueError, match="valid datetime"):
        validate_input(df)


def test_validate_input_duplicate_match_raises() -> None:
    df = pd.concat([_make_valid_df()] * 2, ignore_index=True)

    with pytest.raises(ValueError, match="duplicate match entries"):
        validate_input(df)
