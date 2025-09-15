"""
@file: bivariate_poisson.py
@description: Simulate correlated Poisson goal counts.
@dependencies: numpy
@created: 2025-09-15
"""
from __future__ import annotations

import numpy as np


def simulate_bivariate_poisson(
    lam_home: float, lam_away: float, rho: float, size: int
) -> tuple[np.ndarray, np.ndarray]:
    """Generate bivariate Poisson samples via shared component method."""
    lam_shared = max(rho, 0.0)
    lam1 = max(lam_home - lam_shared, 0.0)
    lam2 = max(lam_away - lam_shared, 0.0)
    shared = np.random.poisson(lam_shared, size)
    home = np.random.poisson(lam1, size) + shared
    away = np.random.poisson(lam2, size) + shared
    return home, away
