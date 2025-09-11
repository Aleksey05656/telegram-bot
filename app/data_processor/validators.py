/**
 * @file: validators.py
 * @description: Column validation utilities for data processing.
 * @dependencies: pandas, data_processor.validate_required_columns
 * @created: 2025-09-10
 */
from __future__ import annotations

import pandas as pd

try:
    from data_processor import validate_required_columns as _impl  # type: ignore
except Exception:
    _impl = None


def validate_required_columns(df: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    if _impl:
        return _impl(df, required)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df
