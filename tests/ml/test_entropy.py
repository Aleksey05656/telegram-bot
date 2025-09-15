"""
@file: test_entropy.py
@description: Tests for entropy helpers.
@dependencies: pytest, numpy
@created: 2025-09-18
"""
import pytest

from ml.metrics.entropy import entropy_1x2, entropy_cs, entropy_totals, shannon_entropy


@pytest.mark.needs_np
def test_entropy_uniform_maximum():
    uniform = shannon_entropy([1 / 3, 1 / 3, 1 / 3])
    skewed = shannon_entropy([0.8, 0.1, 0.1])
    assert uniform > skewed
    e1 = entropy_1x2(1 / 3, 1 / 3, 1 / 3)["1x2"]
    assert e1 == pytest.approx(uniform)


@pytest.mark.needs_np
def test_entropy_handles_zero():
    assert shannon_entropy([1.0, 0.0]) == 0.0
    ecs = entropy_cs({"1:0": 1.0, "0:0": 0.0})["cs"]
    assert ecs == 0.0


@pytest.mark.needs_np
def test_entropy_totals_normalization():
    et = entropy_totals(0.5, 0.5)["totals"]
    assert et == pytest.approx(1.0)
