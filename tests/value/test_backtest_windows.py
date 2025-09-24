"""
/**
 * @file: tests/value/test_backtest_windows.py
 * @description: Validate temporal cross-validation splits for backtesting configuration.
 * @dependencies: pytest, app.value_calibration.backtest
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from app.value_calibration.backtest import (
    BacktestConfig,
    BacktestSample,
    build_windows,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "value_backtest"


def _load_samples() -> list[BacktestSample]:
    path = FIXTURES_DIR / "samples_basic.csv"
    samples: list[BacktestSample] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            samples.append(
                BacktestSample(
                    pulled_at=datetime.fromisoformat(row["pulled_at"]),
                    kickoff_utc=datetime.fromisoformat(row["kickoff_utc"]),
                    league=row["league"],
                    market=row["market"],
                    selection=row["selection"],
                    match_key=row["match_key"],
                    price_decimal=float(row["price_decimal"]),
                    edge_pct=float(row["edge_pct"]),
                    confidence=float(row["confidence"]),
                    result=int(row["result"]),
                )
            )
    return samples


@pytest.mark.parametrize(
    "folds,expected_lengths",
    [
        (2, [4, 4]),
        (3, [3, 3, 2]),
    ],
)
def test_time_kfold_windows_sizes(folds: int, expected_lengths: list[int]) -> None:
    samples = _load_samples()
    config = BacktestConfig(
        min_samples=1,
        validation="time_kfold",
        optim_target="hit",
        edge_grid=[0.0],
        confidence_grid=[0.0],
        folds=folds,
    )
    windows = build_windows(samples, config)
    assert [len(chunk) for chunk in windows] == expected_lengths
    assert windows[0][0].match_key == "M1"
    assert windows[-1][-1].match_key == "M8"


def test_walk_forward_windows_stride() -> None:
    samples = _load_samples()
    config = BacktestConfig(
        min_samples=1,
        validation="walk_forward",
        optim_target="hit",
        edge_grid=[0.0],
        confidence_grid=[0.0],
        folds=3,
        walk_step=2,
    )
    windows = build_windows(samples, config)
    assert len(windows) == 4
    assert [len(chunk) for chunk in windows] == [2, 2, 2, 2]
    assert windows[0][0].match_key == "M1"
    assert windows[-1][-1].match_key == "M8"
