"""
@file: features.py
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

_EMPTY_ERROR = "Cannot build features from an empty dataframe."

    Args:
        df: Validated dataframe.
        windows: Iterable with rolling window sizes for aggregations.

    Returns:
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)
