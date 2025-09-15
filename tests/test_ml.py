"""
@file: tests/test_ml.py
@description: Unit tests for ML utilities
@dependencies: ml/models/bivariate_poisson.py
@created: 2025-08-24
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")


pytestmark = pytest.mark.needs_np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ml.models.bivariate_poisson import estimate_rho, outcome_probabilities  # noqa: E402


def test_estimate_rho_linear_model():
    features = {
        "style_mismatch": 1.0,
        "match_importance": 1.0,
        "fatigue_intensity": 0.0,
    }
    rho = estimate_rho(features, default_rho=0.1)
    assert rho == pytest.approx(0.13, rel=1e-5)


def test_outcome_probabilities_sum_to_one():
    probs = outcome_probabilities(1.0, 1.0, 0.1)
    assert sum(probs.values()) == pytest.approx(1.0, rel=1e-6)
