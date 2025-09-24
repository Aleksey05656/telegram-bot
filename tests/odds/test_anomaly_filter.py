"""
/**
 * @file: tests/odds/test_anomaly_filter.py
 * @description: Unit tests for anomaly detection using z-scores and quantile thresholds.
 * @dependencies: datetime, app.lines.anomaly, app.lines.providers.base
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.lines.anomaly import OddsAnomalyDetector
from app.lines.providers.base import OddsSnapshot


def _snapshot(provider: str, price: float) -> OddsSnapshot:
    now = datetime(2025, 10, 7, 15, 0, tzinfo=UTC)
    return OddsSnapshot(
        provider=provider,
        pulled_at=now,
        match_key="m-odds",
        league="EPL",
        kickoff_utc=now,
        market="1X2",
        selection="HOME",
        price_decimal=price,
        extra=None,
    )


def test_anomaly_detector_ignores_small_sample() -> None:
    detector = OddsAnomalyDetector(z_max=2.0)
    flagged = detector.filter_anomalies([
        _snapshot("a", 2.0),
        _snapshot("b", 2.1),
    ])
    assert flagged == set()


def test_anomaly_detector_flags_outliers() -> None:
    detector = OddsAnomalyDetector(z_max=2.0, quantile=0.2)
    quotes = [
        _snapshot("a", 2.05),
        _snapshot("b", 2.00),
        _snapshot("c", 2.02),
        _snapshot("d", 2.01),
        _snapshot("shock", 3.5),
    ]
    flagged = detector.filter_anomalies(quotes, emit_metrics=False)
    assert flagged == {"shock"}


def test_anomaly_detector_quantile_bounds() -> None:
    detector = OddsAnomalyDetector(z_max=10.0, quantile=0.15)
    quotes = [
        _snapshot("low", 1.4),
        _snapshot("a", 2.0),
        _snapshot("b", 2.01),
        _snapshot("c", 1.98),
        _snapshot("d", 2.02),
        _snapshot("high", 2.9),
    ]
    flagged = detector.filter_anomalies(quotes, emit_metrics=False)
    assert {"low", "high"}.issubset(flagged)
