"""
/**
 * @file: app/diagnostics/calibration.py
 * @description: Calibration utilities (ECE, reliability diagrams) for probability forecasts.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    from matplotlib import pyplot as plt

    HAS_MPL = True
except ModuleNotFoundError:  # pragma: no cover - optional
    plt = None  # type: ignore[assignment]
    HAS_MPL = False


@dataclass
class CalibrationBin:
    lower: float
    upper: float
    predicted: float
    observed: float
    count: int


@dataclass
class ReliabilityResult:
    bins: list[CalibrationBin]
    ece: float


def reliability_table(probabilities: Iterable[float], outcomes: Iterable[int], *, bins: int = 10) -> ReliabilityResult:
    probs = np.clip(np.asarray(list(probabilities), dtype=float), 1e-6, 1 - 1e-6)
    obs = np.asarray(list(outcomes), dtype=int)
    if probs.size != obs.size:
        raise ValueError("probabilities and outcomes length mismatch")
    edges = np.linspace(0.0, 1.0, bins + 1)
    bin_ids = np.digitize(probs, edges, right=True)
    calibration_bins: list[CalibrationBin] = []
    total = probs.size
    ece = 0.0
    for bin_index in range(1, len(edges)):
        mask = bin_ids == bin_index
        if not mask.any():
            continue
        bin_probs = probs[mask]
        bin_obs = obs[mask]
        predicted_mean = float(bin_probs.mean())
        observed_rate = float(bin_obs.mean())
        weight = bin_probs.size / total
        ece += weight * abs(predicted_mean - observed_rate)
        calibration_bins.append(
            CalibrationBin(
                lower=float(edges[bin_index - 1]),
                upper=float(edges[bin_index]),
                predicted=predicted_mean,
                observed=observed_rate,
                count=int(bin_probs.size),
            )
        )
    return ReliabilityResult(bins=calibration_bins, ece=float(ece))


def expected_calibration_error(probabilities: Iterable[float], outcomes: Iterable[int], *, bins: int = 10) -> float:
    return reliability_table(probabilities, outcomes, bins=bins).ece


def plot_reliability(result: ReliabilityResult, output: Path) -> None:
    if not HAS_MPL:
        return
    if not result.bins:
        return
    x = [bin.predicted for bin in result.bins]
    y = [bin.observed for bin in result.bins]
    plt.figure(figsize=(5, 5))
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="ideal")
    plt.scatter(x, y, s=[max(bin.count, 1) * 5 for bin in result.bins], alpha=0.7)
    plt.xlabel("Predicted probability")
    plt.ylabel("Observed frequency")
    plt.title("Reliability diagram")
    plt.grid(True, linestyle=":", alpha=0.5)
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output)
    plt.close()
