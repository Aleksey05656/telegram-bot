"""
@file: tests/odds/test_overround.py
@description: Unit tests for overround normalization helpers.
@dependencies: pytest, app.pricing.overround
@created: 2025-09-24
"""

from __future__ import annotations

import math

import pytest

from app.pricing.overround import (
    decimal_to_probabilities,
    normalize_market,
    probabilities_to_decimal,
)


def test_decimal_to_probabilities_and_inverse() -> None:
    prices = {"home": 2.5, "draw": 3.4, "away": 3.1}
    implied = decimal_to_probabilities(prices)
    assert pytest.approx(sum(implied.values()), rel=1e-3) == sum(1.0 / v for v in prices.values())
    restored = probabilities_to_decimal(implied)
    for key in prices:
        assert math.isclose(restored[key], prices[key], rel_tol=1e-3)


def test_proportional_normalization_sum_equals_one() -> None:
    prices = {"home": 2.1, "draw": 3.5, "away": 3.4}
    normalized = normalize_market(prices, method="proportional")
    assert pytest.approx(sum(normalized.values()), rel=1e-6) == 1.0


def test_shin_normalization_softens_overround() -> None:
    prices = {"home": 1.9, "draw": 3.2, "away": 4.2}
    proportional = normalize_market(prices, method="proportional")
    shin = normalize_market(prices, method="shin")
    assert pytest.approx(sum(shin.values()), rel=1e-6) == 1.0
    assert shin["home"] < proportional["home"]
    assert shin["away"] > proportional["away"]
