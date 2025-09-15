"""
@file: test_bipoisson_sim.py
@description: Validate bivariate Poisson simulator markets.
@dependencies: numpy
@created: 2025-09-15
"""
import numpy as np
import pytest

from ml.sim.bivariate_poisson import simulate_bivariate_poisson
from services.simulator import Simulator


@pytest.mark.needs_np
def test_simulator_probabilities():
    sim = Simulator()
    result = sim.run(1.2, 1.0, rho=0.1, n_sims=2000)
    probs = result["1X2"]
    total = probs["1"] + probs["X"] + probs["2"]
    assert abs(total - 1.0) < 1e-6
    assert result["BTTS"]["yes"] + result["BTTS"]["no"] == pytest.approx(1.0, 1e-6)
    assert result["Totals"]["over_2_5"] + result["Totals"]["under_2_5"] == pytest.approx(1.0, 1e-6)
    cs_total = sum(result["CS"].values())
    assert abs(cs_total - 1.0) < 1e-6
