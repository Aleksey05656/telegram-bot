"""
@file: test_model_matrix.py
@description: Tests for converting engineered features into model matrices.
@dependencies: numpy, pandas, pytest
@created: 2025-09-16
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.data_processor.matrix import to_model_matrix


def test_to_model_matrix_with_intercept_and_dtype() -> None:
    df = pd.DataFrame({"f1": [1.0, 2.0], "f2": [3.0, 4.0]})

    matrix = to_model_matrix(df, ["f1", "f2"], dtype=np.float32)

    assert matrix.shape == (2, 3)
    assert matrix.dtype == np.float32
    np.testing.assert_array_equal(matrix[:, 0], np.ones(2, dtype=np.float32))
    np.testing.assert_array_equal(matrix[:, 1:], df.to_numpy(dtype=np.float32))


def test_to_model_matrix_returns_tuple_for_match_features() -> None:
    df = pd.DataFrame(
        {
            "feature": [0.5, 0.7, 1.1, 0.9],
            "match_id": [0, 0, 1, 1],
            "is_home": [1, 0, 1, 0],
            "target": [2.0, 1.0, 0.0, 3.0],
        }
    )

    X_home, y_home, X_away, y_away = to_model_matrix(df, ["feature"], add_intercept=False)

    np.testing.assert_array_equal(X_home, np.array([[0.5], [1.1]]))
    np.testing.assert_array_equal(y_home, np.log1p(np.array([2.0, 0.0])))
    np.testing.assert_array_equal(X_away, np.array([[0.7], [0.9]]))
    np.testing.assert_array_equal(y_away, np.log1p(np.array([1.0, 3.0])))


def test_to_model_matrix_without_intercept() -> None:
    df = pd.DataFrame({"f1": [1.0, 2.0], "f2": [3.0, 4.0]})

    matrix = to_model_matrix(df, ["f1", "f2"], add_intercept=False)

    np.testing.assert_array_equal(matrix, df.to_numpy())


def test_to_model_matrix_missing_feature_column() -> None:
    df = pd.DataFrame({"f1": [1.0]})

    with pytest.raises(KeyError, match="Missing feature columns"):
        to_model_matrix(df, ["f1", "f2"])


def test_to_model_matrix_rejects_non_numeric_features() -> None:
    df = pd.DataFrame({"f1": [1.0], "f2": ["text"]})

    with pytest.raises(TypeError, match="must be numeric"):
        to_model_matrix(df, ["f1", "f2"])


def test_to_model_matrix_rejects_empty_dataframe() -> None:
    df = pd.DataFrame(columns=["f1"])

    with pytest.raises(ValueError, match="Cannot build a model matrix from an empty dataframe"):
        to_model_matrix(df, ["f1"])


def test_to_model_matrix_requires_feature_columns() -> None:
    df = pd.DataFrame({"f1": [1.0]})

    with pytest.raises(ValueError, match="feature_columns must contain at least one column name"):
        to_model_matrix(df, [])
