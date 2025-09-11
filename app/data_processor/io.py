/**
 * @file: io.py
 * @description: Data input/output helpers.
 * @dependencies: pandas, data_processor.load_data, data_processor.save_data
 * @created: 2025-09-10
 */
from __future__ import annotations

import pandas as pd

try:
    from data_processor import load_data as _load  # type: ignore
    from data_processor import save_data as _save
except Exception:
    _load = _save = None


def load_data(path: str) -> pd.DataFrame:
    if _load:
        return _load(path)
    return pd.read_csv(path)


def save_data(df: pd.DataFrame, path: str) -> None:
    if _save:
        _save(df, path)
        return
    df.to_csv(path, index=False)
