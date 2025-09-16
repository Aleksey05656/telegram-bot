"""
@file: validate.py
@description: Input validation entry point for the new data processor scaffolding.
@dependencies: pandas
@created: 2025-09-16

Validation helpers for the future data processor implementation.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

_EMPTY_ERROR: Final[str] = "Input dataframe is empty; validation requires source data."


def validate_input(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the raw dataframe before feature engineering.

    TODO: implement domain-specific validation rules.

    Args:
        df: Raw input dataframe that should contain match-level observations.

    Returns:
        The validated dataframe when concrete checks are implemented.

    Raises:
        ValueError: If the dataframe is empty.
        NotImplementedError: Until the validation logic is implemented.
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    raise NotImplementedError("TODO: implement data validation logic.")
