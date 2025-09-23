"""
/**
 * @file: app/diagnostics/coverage.py
 * @description: Coverage diagnostics for Monte Carlo prediction intervals.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class CoverageResult:
    target: float
    observed: float
    tolerance: float
    status: str


def monte_carlo_coverage(samples: Iterable[float], lower: Iterable[float], upper: Iterable[float], *, target: float, tolerance: float = 0.02) -> CoverageResult:
    samples_arr = np.asarray(list(samples), dtype=float)
    lower_arr = np.asarray(list(lower), dtype=float)
    upper_arr = np.asarray(list(upper), dtype=float)
    if not (samples_arr.size and lower_arr.size and upper_arr.size):
        raise ValueError("empty arrays provided")
    if samples_arr.size != lower_arr.size or samples_arr.size != upper_arr.size:
        raise ValueError("input arrays length mismatch")
    hits = (samples_arr >= lower_arr) & (samples_arr <= upper_arr)
    observed = float(hits.mean())
    status = "✅" if abs(observed - target) <= tolerance else "❌"
    return CoverageResult(target=target, observed=observed, tolerance=tolerance, status=status)
