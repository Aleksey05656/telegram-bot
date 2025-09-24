"""
@file: app/pricing/overround.py
@description: Implied probability helpers and overround normalization strategies.
@dependencies: math
@created: 2025-09-24
"""

from __future__ import annotations

import math
from typing import Mapping


def decimal_to_probabilities(prices: Mapping[str, float]) -> dict[str, float]:
    """Convert decimal odds into implied probabilities without normalization."""

    implied: dict[str, float] = {}
    for key, price in prices.items():
        value = float(price)
        if value <= 1.0:
            raise ValueError(f"Decimal odds must be > 1.0 for {key}")
        implied[key] = 1.0 / value
    return implied


def probabilities_to_decimal(probabilities: Mapping[str, float]) -> dict[str, float]:
    """Invert probabilities back into fair decimal odds."""

    decimals: dict[str, float] = {}
    for key, prob in probabilities.items():
        value = float(prob)
        if value <= 0:
            decimals[key] = math.inf
        else:
            decimals[key] = round(1.0 / value, 4)
    return decimals


def normalize_market(
    prices: Mapping[str, float],
    *,
    method: str = "proportional",
) -> dict[str, float]:
    implied = decimal_to_probabilities(prices)
    if not implied:
        return {}
    method_normalized = method.lower()
    if method_normalized == "shin" and len(implied) == 3:
        return _normalize_shin(implied)
    return _normalize_proportional(implied)


def _normalize_proportional(probabilities: Mapping[str, float]) -> dict[str, float]:
    total = sum(probabilities.values())
    if total <= 0:
        raise ValueError("Sum of implied probabilities must be > 0")
    return {key: value / total for key, value in probabilities.items()}


def _normalize_shin(probabilities: Mapping[str, float]) -> dict[str, float]:
    raw = list(probabilities.items())
    q_values = [value for _, value in raw]
    overround = sum(q_values)
    if overround <= 1.0:
        return _normalize_proportional(probabilities)
    z = _solve_shin_parameter(q_values)
    adjusted: dict[str, float] = {}
    for (key, q_i) in raw:
        numerator = math.sqrt(z * z + 4.0 * (1.0 - z) * q_i) - z
        denominator = 2.0 * (1.0 - z)
        adjusted[key] = numerator / denominator
    total = sum(adjusted.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Failed to normalize probabilities via Shin method")
    return {key: value / total for key, value in adjusted.items()}


def _solve_shin_parameter(q_values: list[float]) -> float:
    lower = 0.0
    upper = 0.99
    mid = 0.0
    for _ in range(40):
        mid = (lower + upper) / 2.0
        denom = 2.0 * (1.0 - mid)
        if denom <= 0:
            upper = (lower + upper) / 2.0
            continue
        total = 0.0
        for q in q_values:
            total += (math.sqrt(mid * mid + 4.0 * (1.0 - mid) * q) - mid) / denom
        if abs(total - 1.0) < 1e-9:
            return mid
        if total > 1.0:
            lower = mid
        else:
            upper = mid
    return max(min(mid, 0.99), 0.0)


__all__ = [
    "decimal_to_probabilities",
    "probabilities_to_decimal",
    "normalize_market",
]
