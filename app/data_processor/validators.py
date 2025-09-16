"""
@file: validators.py
@description: Column validation utilities for data processing.
@dependencies: pandas, data_processor.validate_required_columns
@created: 2025-09-10
"""
from __future__ import annotations

import pandas as pd

try:  # pragma: no cover - legacy import fallback
    from data_processor import validate_required_columns as _impl  # type: ignore
except Exception:  # pragma: no cover - fallback path exercised in tests
    _impl = None


def validate_required_columns(df: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    """Ensure that the dataframe contains the requested columns.

    The helper reuses the legacy :mod:`data_processor` implementation when it is
    available to keep backward compatibility while new modules are extracted.
    The fallback performs a lightweight column presence check.
    """
    if _impl:
        return _impl(df, required)

    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df
