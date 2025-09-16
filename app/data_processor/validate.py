"""
@file: validate.py
@description: Validation helpers ensuring consistent inputs for feature building.
@dependencies: pandas
@created: 2025-09-16
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd
from pandas.api.types import is_numeric_dtype

from .validators import validate_required_columns

_EMPTY_ERROR = "Cannot validate an empty dataframe."
_NULL_ERROR = "Column '%s' contains null values."
_NUMERIC_ERROR = "Column '%s' must be numeric."
_DUPLICATE_ERROR = "Duplicate rows detected for keys: %s"
_SORT_ERROR = "sort_by columns are missing: %s"
_MATCH_COLUMNS = {
    "home_team",
    "away_team",
    "date",
    "xG_home",
    "xG_away",
    "goals_home",
    "goals_away",
}


def _normalize_iterable(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return list(dict.fromkeys(values))


def validate_input(
    df: pd.DataFrame,
    *,
    required_columns: Iterable[str] | None = None,
    numeric_columns: Iterable[str] | None = None,
    non_null_columns: Iterable[str] | None = None,
    unique_subset: Sequence[str] | None = None,
    sort_by: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Validate dataframe invariants prior to feature engineering.

    Args:
        df: Raw dataframe to be validated.
        required_columns: Columns that must be present in the dataframe.
        numeric_columns: Columns that must contain numeric data types.
        non_null_columns: Columns that are not allowed to contain null values.
        unique_subset: Column subset that should uniquely identify each row.
        sort_by: Columns used to order the dataframe after validation.

    Returns:
        A validated (and optionally sorted) dataframe.

    Raises:
        ValueError: If the dataframe is empty, contains duplicates in the
            specified subset or null values in required columns.
        KeyError: If required columns are missing from the dataframe.
        TypeError: When columns expected to be numeric contain non numeric data.
    """
    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    validated = df.copy()
    required = _normalize_iterable(required_columns)
    numeric = _normalize_iterable(numeric_columns)
    non_null = _normalize_iterable(non_null_columns)

    match_present = bool(set(_MATCH_COLUMNS) & set(validated.columns))
    if match_present:
        missing_match = [column for column in _MATCH_COLUMNS if column not in validated.columns]
        if missing_match:
            raise KeyError(f"Missing required match columns: {missing_match}")
        for column in _MATCH_COLUMNS:
            if column not in required:
                required.append(column)
        for column in ("xG_home", "xG_away", "goals_home", "goals_away"):
            if column not in numeric and column in validated.columns:
                numeric.append(column)
        if "date" in validated.columns and "date" not in non_null:
            non_null.append("date")

    if required:
        validated = validate_required_columns(validated, required)

    if "date" in validated.columns:
        validated["date"] = pd.to_datetime(validated["date"])

    for column in non_null:
        if column not in validated.columns:
            raise KeyError(f"Column '{column}' is not present in the dataframe.")
        if validated[column].isnull().any():
            raise ValueError(_NULL_ERROR % column)

    for column in numeric:
        if column not in validated.columns:
            raise KeyError(f"Column '{column}' is not present in the dataframe.")
        if not is_numeric_dtype(validated[column]):
            raise TypeError(_NUMERIC_ERROR % column)

    if unique_subset:
        duplicated_mask = validated.duplicated(subset=list(unique_subset), keep=False)
        if duplicated_mask.any():
            duplicates = validated.loc[duplicated_mask, list(unique_subset)]
            raise ValueError(_DUPLICATE_ERROR % duplicates.to_dict(orient="records"))

    if sort_by:
        missing = [column for column in sort_by if column not in validated.columns]
        if missing:
            raise KeyError(_SORT_ERROR % missing)
        validated = validated.sort_values(list(sort_by), kind="stable").reset_index(drop=True)

    return validated
