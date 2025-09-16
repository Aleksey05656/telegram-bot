"""
@file: test_features.py
@description: Smoke test for the data processor feature builder scaffold.
@dependencies: pandas, pytest
@created: 2025-09-16

Tests for `app.data_processor.features`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.features import build_features


def test_build_features_requires_non_empty_dataframe() -> None:
    """Feature builder should reject empty inputs."""

    df = pd.DataFrame()

    with pytest.raises(ValueError, match="empty"):
        build_features(df)
