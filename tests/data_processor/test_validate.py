"""
@file: test_validate.py
@description: Smoke test for the data processor validation scaffold.
@dependencies: pandas, pytest
@created: 2025-09-16

Tests for `app.data_processor.validate`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data_processor.validate import validate_input


def test_validate_input_rejects_empty_dataframe() -> None:
    """Validation should fail fast on empty inputs."""

    df = pd.DataFrame()

    with pytest.raises(ValueError, match="empty"):
        validate_input(df)
