"""
@file: calibration.py
@description: Probability calibration helpers and ECE report.
@dependencies: numpy, sklearn
@created: 2025-09-15
"""
from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression


def ece(prob: np.ndarray, label: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error for binary or multiclass probabilities."""
    prob = np.asarray(prob)
    label = np.asarray(label)
    if prob.ndim == 1:
        prob = prob[:, None]
        label = label[:, None]
    eces = []
    for j in range(prob.shape[1]):
        p = prob[:, j]
        y_true = label[:, j] if label.ndim == 2 else (label == j).astype(float)
        bins = np.linspace(0, 1, n_bins + 1)
        idx = np.digitize(p, bins) - 1
        e = 0.0
        for b in range(n_bins):
            mask = idx == b
            if not np.any(mask):
                continue
            conf = p[mask].mean()
            acc = y_true[mask].mean()
            e += p[mask].size / p.size * abs(conf - acc)
        eces.append(e)
    return float(np.mean(eces))


def isotonic_calibrate(prob: np.ndarray, label: np.ndarray) -> np.ndarray:
    """Calibrate probabilities via isotonic regression per class."""
    prob = np.asarray(prob)
    label = np.asarray(label)
    if prob.ndim == 1:
        ir = IsotonicRegression(out_of_bounds="clip")
        return ir.fit_transform(prob, label)
    calibrated = np.zeros_like(prob)
    for j in range(prob.shape[1]):
        ir = IsotonicRegression(out_of_bounds="clip")
        y = label[:, j] if label.ndim == 2 else (label == j).astype(float)
        calibrated[:, j] = ir.fit_transform(prob[:, j], y)
    return calibrated


def calibration_report(
    prob_dict: dict[str, np.ndarray], label_dict: dict[str, np.ndarray]
) -> dict[str, dict[str, float]]:
    """Compute ECE before/after isotonic calibration for given markets."""
    report: dict[str, dict[str, float]] = {}
    for key, probs in prob_dict.items():
        labels = label_dict[key]
        before = ece(probs, labels)
        after = ece(isotonic_calibrate(probs, labels), labels)
        report[key] = {"ece_before": before, "ece_after": after}
    return report
