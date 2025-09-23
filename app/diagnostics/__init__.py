"""
/**
 * @file: app/diagnostics/__init__.py
 * @description: Convenience exports for diagnostics utilities (calibration, invariance, etc.).
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from .calibration import expected_calibration_error, reliability_table
from .coverage import monte_carlo_coverage
from .invariance import bipoisson_swap_check, scoreline_symmetry

__all__ = [
    "expected_calibration_error",
    "reliability_table",
    "monte_carlo_coverage",
    "bipoisson_swap_check",
    "scoreline_symmetry",
]
