"""
/**
 * @file: tests/value/test_calibration_fit.py
 * @description: Ensure calibration runner selects optimal thresholds per market.
 * @dependencies: app.value_calibration.backtest
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.value_calibration.backtest import (
    BacktestConfig,
    BacktestRunner,
    BacktestSample,
)


def _sample(ts: datetime, edge: float, conf: float, result: int) -> BacktestSample:
    kickoff = ts + timedelta(hours=6)
    return BacktestSample(
        pulled_at=ts,
        kickoff_utc=kickoff,
        league="L1",
        market="1X2",
        selection="HOME",
        match_key=f"{ts:%Y%m%d}",
        price_decimal=2.0 + edge / 10.0,
        edge_pct=edge,
        confidence=conf,
        result=result,
    )


def test_calibration_prefers_balanced_thresholds() -> None:
    base = datetime(2024, 1, 1, 9, 0)
    samples = [
        _sample(base, edge=2.0, conf=0.60, result=0),
        _sample(base + timedelta(days=1), edge=3.5, conf=0.65, result=1),
        _sample(base + timedelta(days=2), edge=4.2, conf=0.72, result=1),
        BacktestSample(
            pulled_at=base + timedelta(days=3),
            kickoff_utc=base + timedelta(days=3, hours=6),
            league="L1",
            market="1X2",
            selection="HOME",
            match_key="L1-004",
            price_decimal=1.8,
            edge_pct=5.5,
            confidence=0.78,
            result=1,
        ),
        _sample(base + timedelta(days=4), edge=6.5, conf=0.66, result=0),
    ]
    config = BacktestConfig(
        min_samples=1,
        validation="time_kfold",
        optim_target="loggain",
        edge_grid=[2.0, 4.0, 5.0],
        confidence_grid=[0.6, 0.7, 0.75],
        folds=2,
    )
    runner = BacktestRunner(samples)
    results = runner.calibrate(config)
    assert len(results) == 1
    record = results[0]
    assert record.tau_edge == pytest.approx(4.0)
    assert record.gamma_conf == pytest.approx(0.7)
    assert record.metrics.samples == 2
    assert record.metrics.hit_rate == pytest.approx(1.0)
