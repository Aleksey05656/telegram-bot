"""
@file: tests/odds/test_provider_csv.py
@description: Tests for CSV odds provider mapping and normalization.
@dependencies: asyncio, pytest
@created: 2025-09-24
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import pytest

from app.lines.mapper import LinesMapper
from app.lines.providers.csv import CSVLinesProvider


@pytest.mark.asyncio
async def test_csv_provider_reads_fixtures() -> None:
    fixtures_dir = Path("tests/fixtures/odds")
    provider = CSVLinesProvider(fixtures_dir=fixtures_dir, mapper=LinesMapper())
    date_from = datetime(2024, 9, 1, tzinfo=UTC)
    date_to = datetime(2024, 9, 3, tzinfo=UTC)
    odds = await provider.fetch_odds(date_from=date_from, date_to=date_to)
    assert len(odds) == 14
    sample = odds[0]
    assert sample.match_key
    assert sample.kickoff_utc.tzinfo is UTC
    assert sample.price_decimal > 1.0
    assert sample.market in {"1X2", "OU_2_5", "BTTS"}
    assert sample.selection in {"HOME", "DRAW", "AWAY", "OVER", "UNDER", "YES", "NO"}
