"""
/**
 * @file: app/diagnostics/invariance.py
 * @description: Invariance checks for Bi-Poisson score distributions under home/away swaps.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class InvarianceResult:
    status: str
    max_delta: float
    note: str


def _score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 6) -> np.ndarray:
    scores = np.zeros((max_goals + 1, max_goals + 1), dtype=float)
    for h in range(max_goals + 1):
        pmf_h = math.exp(-lambda_home) * lambda_home**h / math.factorial(h)
        for a in range(max_goals + 1):
            pmf_a = math.exp(-lambda_away) * lambda_away**a / math.factorial(a)
            scores[h, a] = pmf_h * pmf_a
    mass = scores.sum()
    if mass < 0.999:
        scores = scores / max(mass, 1e-9)
    return scores


def _market_vector(scores: np.ndarray) -> np.ndarray:
    home = np.tril(scores, k=-1).sum()
    draw = np.trace(scores)
    away = np.triu(scores, k=1).sum()
    return np.array([home, draw, away], dtype=float)


def bipoisson_swap_check(lambda_home: float, lambda_away: float, *, max_goals: int = 6) -> InvarianceResult:
    base = _market_vector(_score_matrix(lambda_home, lambda_away, max_goals=max_goals))
    swapped = _market_vector(_score_matrix(lambda_away, lambda_home, max_goals=max_goals))[::-1]
    delta = np.abs(base - swapped)
    max_delta = float(delta.max())
    status = "✅" if max_delta <= 1e-6 else "⚠️"
    note = f"max_delta={max_delta:.6f}"
    return InvarianceResult(status=status, max_delta=max_delta, note=note)


def scoreline_symmetry(lambda_home: float, lambda_away: float, *, top_k: int = 5, max_goals: int = 6) -> InvarianceResult:
    base_matrix = _score_matrix(lambda_home, lambda_away, max_goals=max_goals)
    swapped_matrix = _score_matrix(lambda_away, lambda_home, max_goals=max_goals)
    def _top_scores(matrix: np.ndarray) -> list[tuple[int, int, float]]:
        entries = []
        for h in range(matrix.shape[0]):
            for a in range(matrix.shape[1]):
                entries.append((h, a, matrix[h, a]))
        entries.sort(key=lambda item: item[2], reverse=True)
        return entries[:top_k]

    base = _top_scores(base_matrix)
    swapped = _top_scores(swapped_matrix)
    deltas = []
    for (h, a, p), (h_sw, a_sw, p_sw) in zip(base, swapped):
        deltas.append(abs(p - p_sw))
        if not (h == a_sw and a == h_sw):
            deltas.append(1.0)
    max_delta = float(max(deltas) if deltas else 0.0)
    status = "✅" if max_delta <= 1e-6 else "⚠️"
    note = f"top_k={top_k} max_delta={max_delta:.6f}"
    return InvarianceResult(status=status, max_delta=max_delta, note=note)
