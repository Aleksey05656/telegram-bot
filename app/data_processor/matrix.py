"""
@file: matrix.py
@description: Model matrix builder scaffold for the data processor package.
@dependencies: pandas
@created: 2025-09-16

Helpers for constructing the modeling matrices.
"""

from __future__ import annotations

import pandas as pd

_EMPTY_ERROR = "Cannot prepare a model matrix from an empty dataframe."


ModelMatrix = tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]


def to_model_matrix(df: pd.DataFrame) -> ModelMatrix:
    """Convert engineered features into train/holdout matrices.

    TODO: split the dataset into modeling matrices when feature engineering is ready.

    Args:
        df: Dataframe with engineered features.

    Returns:
        Tuple with holdout and application matrices and targets when implemented.

    Raises:
        ValueError: If the dataframe is empty.
        NotImplementedError: Until the matrix conversion is available.
    """

    if df.empty:
        raise ValueError(_EMPTY_ERROR)

    raise NotImplementedError("TODO: implement model matrix conversion.")
