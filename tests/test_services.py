"""
@file: tests/test_services.py
@description: Unit tests for service utility functions
@dependencies: services/data_processor.py
@created: 2025-08-24
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.needs_np

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_compute_rest_days():
    from services.data_processor import compute_rest_days  # noqa: E402

    match_date = datetime(2023, 8, 10)
    last_match = datetime(2023, 8, 5)
    assert compute_rest_days(match_date, last_match) == 5


def test_haversine_km():
    from services.data_processor import haversine_km  # noqa: E402

    distance = haversine_km(0.0, 0.0, 0.0, 1.0)
    assert distance == pytest.approx(111.19, rel=1e-2)
