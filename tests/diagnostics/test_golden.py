"""
/**
 * @file: tests/diagnostics/test_golden.py
 * @description: Golden regression epsilon guard tests.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from copy import deepcopy

from diagtools.golden_regression import GoldenSnapshot, build_snapshot, compare_snapshots


def test_compare_identical_snapshots_passes(monkeypatch) -> None:
    # Ensure thresholds use defaults for deterministic assertion
    monkeypatch.delenv("GOLDEN_COEF_EPS", raising=False)
    monkeypatch.delenv("GOLDEN_LAMBDA_MAPE", raising=False)
    monkeypatch.delenv("GOLDEN_PROB_EPS", raising=False)

    reference = build_snapshot(seed=42)
    diff = compare_snapshots(reference, reference)

    assert diff["status"] == "✅"
    assert diff["checks"]["coefficients_home"]["status"] == "✅"


def test_probability_delta_violation_detected(monkeypatch) -> None:
    monkeypatch.setenv("GOLDEN_PROB_EPS", "0.001")
    reference = build_snapshot(seed=7)
    altered = deepcopy(reference)
    altered.market_probabilities = [row[:] for row in reference.market_probabilities]
    altered.market_probabilities[0][0] += 0.01

    diff = compare_snapshots(altered, reference)

    assert diff["status"] == "❌"
    assert diff["checks"]["probabilities"]["status"] == "❌"
