"""
@file: entropy.py
@description: Shannon entropy helpers for simulation markets.
@dependencies: numpy
@created: 2025-09-18
"""
from __future__ import annotations

import math
from collections.abc import Iterable


def shannon_entropy(p: Iterable[float]) -> float:
    """Compute Shannon entropy in bits avoiding log(0)."""
    total = 0.0
    for prob in p:
        if prob > 0:
            total -= prob * math.log2(prob)
    return total


def entropy_1x2(p1: float, px: float, p2: float) -> dict[str, float]:
    """Entropy for 1X2 market."""
    return {"1x2": shannon_entropy([p1, px, p2])}


def entropy_totals(p_over: float, p_under: float) -> dict[str, float]:
    """Entropy for totals market (single line)."""
    return {"totals": shannon_entropy([p_over, p_under])}


def entropy_cs(cs_probs: dict[str, float]) -> dict[str, float]:
    """Entropy for correct score market."""
    return {"cs": shannon_entropy(cs_probs.values())}
