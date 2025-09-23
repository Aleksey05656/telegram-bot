"""
/**
 * @file: tests/diagnostics/test_calibration.py
 * @description: Calibration and coverage diagnostics tests.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import numpy as np

from app.diagnostics import expected_calibration_error, monte_carlo_coverage, reliability_table


def test_expected_calibration_error_low_for_well_calibrated() -> None:
    rng = np.random.default_rng(0)
    probs = np.linspace(0.05, 0.95, num=200)
    outcomes = rng.binomial(1, probs)
    ece = expected_calibration_error(probs, outcomes, bins=10)
    assert ece < 0.1


def test_reliability_table_detects_miscalibration() -> None:
    probs = np.concatenate([np.full(100, 0.8), np.full(100, 0.2)])
    outcomes = np.concatenate([np.zeros(100), np.ones(100)])
    result = reliability_table(probs, outcomes, bins=5)
    assert result.ece > 0.2


def test_monte_carlo_coverage_within_tolerance() -> None:
    rng = np.random.default_rng(42)
    samples = rng.normal(0, 1, size=1000)
    lower = np.full_like(samples, -1.28)
    upper = np.full_like(samples, 1.28)
    result = monte_carlo_coverage(samples, lower, upper, target=0.8, tolerance=0.05)
    assert result.status == "✅"
    assert abs(result.observed - 0.8) <= 0.05


def test_monte_carlo_coverage_flags_failure() -> None:
    samples = np.array([0.0, 0.0, 0.0])
    lower = np.array([-2.0, -2.0, -2.0])
    upper = np.array([-1.0, -1.0, -1.0])
    result = monte_carlo_coverage(samples, lower, upper, target=0.9, tolerance=0.02)
    assert result.status == "❌"
