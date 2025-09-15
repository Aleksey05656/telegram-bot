"""
@file: bivariate_poisson.py
@description: Simulate correlated Poisson goal counts.
@dependencies: numpy
@created: 2025-09-15
"""
from __future__ import annotations

import numpy as np


def simulate_bipoisson(
    lam_home: float,
    lam_away: float,
    rho: float,
    n_sims: int = 10000,
    seed: int | None = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate correlated goal counts using a shared component.

    Parameters
    ----------
    lam_home, lam_away:
        Expected goal rates for home and away teams. Must be positive.
    rho:
        Desired correlation coefficient (0 <= rho <= 1). Negative values clipped to 0.
    n_sims:
        Number of simulations to draw.
    seed:
        Random seed for reproducibility.
    """

    if lam_home <= 0 or lam_away <= 0:
        raise ValueError("Lambdas must be positive")

    rho = max(min(rho, 1.0), 0.0)
    lam_c = min(rho * np.sqrt(lam_home * lam_away), lam_home, lam_away)
    lam_h_ind = lam_home - lam_c
    lam_a_ind = lam_away - lam_c

    rng = np.random.default_rng(seed)
    shared = rng.poisson(lam_c, n_sims)
    home = rng.poisson(lam_h_ind, n_sims) + shared
    away = rng.poisson(lam_a_ind, n_sims) + shared
    return home, away
