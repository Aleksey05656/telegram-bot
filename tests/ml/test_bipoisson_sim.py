"""
@file: test_bipoisson_sim.py
@description: Validate bivariate Poisson simulator markets.
@dependencies: numpy
@created: 2025-09-15
"""
import numpy as np
import pytest

from ml.sim.bivariate_poisson import simulate_bipoisson
from services.simulator import Simulator


@pytest.mark.needs_np
def test_covariance_monotonic():
    lam_h, lam_a = 1.4, 1.2
    covs = []
    for rho in [0.0, 0.3, 0.6]:
        h, a = simulate_bipoisson(lam_h, lam_a, rho, n_sims=20000, seed=0)
        covs.append(np.cov(h, a)[0, 1])
    assert covs[0] <= covs[1] <= covs[2]


@pytest.mark.needs_np
def test_market_normalization():
    sim = Simulator()
    result = sim.run(1.3, 1.1, rho=0.1, n_sims=5000)

    probs = result["1x2"]
    assert probs["1"] + probs["x"] + probs["2"] == pytest.approx(1.0, 1e-6)

    for vals in result["totals"].values():
        assert vals["over"] + vals["under"] == pytest.approx(1.0, 1e-3)

    cs_total = sum(result["cs"].values())
    assert cs_total == pytest.approx(1.0, 1e-6)
