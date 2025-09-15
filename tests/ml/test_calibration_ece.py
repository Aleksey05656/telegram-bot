"""
@file: test_calibration_ece.py
@description: Test isotonic calibration reduces ECE.
@dependencies: numpy, sklearn
@created: 2025-09-15
"""
import numpy as np
import pytest

from ml.calibration import ece, isotonic_calibrate


@pytest.mark.needs_np
def test_isotonic_reduces_ece():
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, 1000)
    labels = rng.binomial(1, probs)
    before = ece(probs, labels)
    after = ece(isotonic_calibrate(probs, labels), labels)
    assert after <= before + 1e-6
