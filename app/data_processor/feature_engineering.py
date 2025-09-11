/**
 * @file: feature_engineering.py
 * @description: Feature engineering helpers.
 * @dependencies: pandas, data_processor.build_features
 * @created: 2025-09-10
 */
from __future__ import annotations

import pandas as pd

try:
    from data_processor import build_features as _impl  # type: ignore
except Exception:
    _impl = None


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    if _impl:
        return _impl(df)
    # минимальная заглушка
    df = df.copy()
    return df
