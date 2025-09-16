"""
@file: features.py
@description: Feature construction scaffold for the data processor package.
@dependencies: pandas
@created: 2025-09-16

Feature engineering scaffolding for the data processor.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

_EMPTY_ERROR = "Cannot build features from an empty dataframe."


def build_features(df: pd.DataFrame, *, windows: Iterable[int] = (5, 10)) -> pd.DataFrame:
    """Construct model features based on rolling windows.

    TODO: add transformations after validation and profiling are complete.

    Args:
        df: Validated dataframe.
        windows: Iterable with rolling window sizes for aggregations.

    Returns:
        Dataframe with engineered features once implemented.

    Raises:
        ValueError: If the dataframe is empty.
        NotImplementedError: While the feature builder is not implemented.
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    # Keep the signature exercised until the feature builder is implemented.
    _ = tuple(windows)

    raise NotImplementedError("TODO: implement feature engineering.")
