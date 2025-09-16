"""
@file: test_model_matrix.py
@description: Smoke test for the data processor model matrix scaffold.
@dependencies: pandas, pytest
@created: 2025-09-16

Tests for `app.data_processor.matrix`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.matrix import to_model_matrix


def test_to_model_matrix_rejects_empty_dataframe() -> None:
    """Model matrix conversion should fail for empty dataframes."""

    df = pd.DataFrame()

    with pytest.raises(ValueError, match="empty"):
        to_model_matrix(df)
