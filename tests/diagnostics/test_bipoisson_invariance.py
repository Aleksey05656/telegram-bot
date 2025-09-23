"""
/**
 * @file: tests/diagnostics/test_bipoisson_invariance.py
 * @description: Bi-Poisson invariance tests for home/away swap symmetry.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from app.diagnostics import bipoisson_swap_check, scoreline_symmetry


def test_market_probabilities_swap_symmetry() -> None:
    result = bipoisson_swap_check(1.4, 0.9)
    assert result.status == "✅"
    assert result.max_delta < 1e-6


def test_top_scorelines_swap_symmetry() -> None:
    result = scoreline_symmetry(1.2, 1.1, top_k=5)
    assert result.status == "✅"
    assert result.max_delta < 1e-6
