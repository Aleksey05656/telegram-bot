"""
@file: test_validate.py
@description: Tests for the input validation helpers of the data processor package.
@dependencies: pandas, pytest
@created: 2025-09-16
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.validate import validate_input
from app.data_processor.validators import validate_required_columns


def test_validate_required_columns_success() -> None:
    df = pd.DataFrame({"team": ["A"], "value": [1.0]})

    result = validate_required_columns(df, ["team", "value"])

    pd.testing.assert_frame_equal(result, df)


def test_validate_required_columns_missing_column() -> None:
    df = pd.DataFrame({"team": ["A"]})

    with pytest.raises(ValueError, match="Missing required columns:"):
        validate_required_columns(df, ["team", "value"])


def test_validate_input_handles_match_columns() -> None:
    df = pd.DataFrame(
        {
            "home_team": ["A"],
            "away_team": ["B"],
            "date": ["2024-01-01"],
            "xG_home": [1.2],
            "xG_away": [0.9],
            "goals_home": [2],
            "goals_away": [1],
        }
    )

    validated = validate_input(df)

    assert pd.api.types.is_datetime64_any_dtype(validated["date"])
    assert set(df.columns).issubset(validated.columns)


def test_validate_input_requires_complete_match_columns() -> None:
    df = pd.DataFrame(
        {
            "home_team": ["A"],
            "away_team": ["B"],
            "xG_home": [1.2],
            "xG_away": [0.9],
            "goals_home": [2],
            "goals_away": [1],
        }
    )

    with pytest.raises(KeyError, match="Missing required match columns"):
        validate_input(df)


def test_validate_input_happy_path_sorts_and_checks_types() -> None:
    df = pd.DataFrame(
        {
            "team_id": ["B", "A", "A", "B"],
            "match_date": pd.to_datetime(["2024-08-04", "2024-08-01", "2024-08-03", "2024-08-02"]),
            "goals_for": [3, 1, 0, 2],
            "goals_against": [0, 0, 2, 1],
            "xg": [1.4, 0.9, 0.4, 1.2],
        }
    )

    validated = validate_input(
        df,
        required_columns=["team_id", "match_date", "goals_for", "goals_against", "xg"],
        numeric_columns=["goals_for", "goals_against", "xg"],
        non_null_columns=["match_date"],
        unique_subset=["team_id", "match_date"],
        sort_by=["team_id", "match_date"],
    )

    assert validated.index.tolist() == [0, 1, 2, 3]
    assert list(validated["team_id"]) == ["A", "A", "B", "B"]
    assert validated.loc[0, "match_date"] < validated.loc[1, "match_date"]
    assert validated.loc[2, "match_date"] < validated.loc[3, "match_date"]


def test_validate_input_detects_duplicates() -> None:
    df = pd.DataFrame(
        {
            "team_id": ["A", "A"],
            "match_date": pd.to_datetime(["2024-08-01", "2024-08-01"]),
            "goals_for": [1, 2],
        }
    )

    with pytest.raises(ValueError, match="Duplicate rows detected"):
        validate_input(df, unique_subset=["team_id", "match_date"])


def test_validate_input_detects_null_values() -> None:
    df = pd.DataFrame(
        {
            "team_id": ["A", "A"],
            "match_date": [pd.Timestamp("2024-08-01"), pd.NaT],
            "goals_for": [1, 2],
        }
    )

    with pytest.raises(ValueError, match="contains null values"):
        validate_input(df, non_null_columns=["match_date"])


def test_validate_input_detects_non_numeric_columns() -> None:
    df = pd.DataFrame(
        {
            "team_id": ["A"],
            "goals_for": ["one"],
        }
    )

    with pytest.raises(TypeError, match="must be numeric"):
        validate_input(df, numeric_columns=["goals_for"])


def test_validate_input_missing_sort_key() -> None:
    df = pd.DataFrame({"team_id": ["A"], "goals_for": [1]})

    with pytest.raises(KeyError, match="sort_by columns are missing"):
        validate_input(df, sort_by=["match_date"])
