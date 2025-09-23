"""
/**
 * @file: tools/drift_report.py
 * @description: Covariate/label/prediction drift detection utilities with PSI and KS summaries.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from matplotlib import pyplot as plt

    HAS_MPL = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    plt = None  # type: ignore[assignment]
    HAS_MPL = False

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.golden_regression import _poisson_probs, _simulate_dataset  # reuse deterministic simulation


@dataclass
class DriftStatistic:
    feature: str
    psi: float
    ks: float
    status: str
    note: str


@dataclass
class DriftReport:
    features: list[DriftStatistic]
    outcome: list[DriftStatistic]
    predictions: list[DriftStatistic]
    summary_path: Path
    json_path: Path


def _population_stability_index(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    ref_hist, bin_edges = np.histogram(reference, bins=bins)
    cur_hist, _ = np.histogram(current, bins=bin_edges)
    ref_prop = ref_hist / max(ref_hist.sum(), 1)
    cur_prop = cur_hist / max(cur_hist.sum(), 1)
    psi = 0.0
    for ref_p, cur_p in zip(ref_prop, cur_prop):
        ref_p = max(ref_p, 1e-6)
        cur_p = max(cur_p, 1e-6)
        psi += (cur_p - ref_p) * math.log(cur_p / ref_p)
    return float(psi)


def _kolmogorov_smirnov(reference: np.ndarray, current: np.ndarray) -> float:
    ref_sorted = np.sort(reference)
    cur_sorted = np.sort(current)
    all_values = np.concatenate([ref_sorted, cur_sorted])
    ref_cdf = np.searchsorted(ref_sorted, all_values, side="right") / ref_sorted.size
    cur_cdf = np.searchsorted(cur_sorted, all_values, side="right") / cur_sorted.size
    return float(np.max(np.abs(ref_cdf - cur_cdf)))


def _evaluate_series(feature: str, reference: pd.Series, current: pd.Series, psi_warn: float, psi_fail: float) -> DriftStatistic:
    ref_values = reference.dropna().to_numpy()
    cur_values = current.dropna().to_numpy()
    if ref_values.size == 0 or cur_values.size == 0:
        return DriftStatistic(feature, float("nan"), float("nan"), "⚠️", "insufficient data")
    psi = _population_stability_index(ref_values, cur_values)
    ks = _kolmogorov_smirnov(ref_values, cur_values)
    status = "✅"
    note = "stable"
    if psi >= psi_fail:
        status = "❌"
        note = f"PSI {psi:.3f} >= {psi_fail:.2f}"
    elif psi >= psi_warn:
        status = "⚠️"
        note = f"PSI {psi:.3f} >= {psi_warn:.2f}"
    return DriftStatistic(feature, psi, ks, status, note)


def _render_histogram(feature: str, reference: pd.Series, current: pd.Series, output_dir: Path) -> None:
    if not HAS_MPL:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(6, 4))
    plt.hist(reference.dropna(), bins=20, alpha=0.6, label="reference")
    plt.hist(current.dropna(), bins=20, alpha=0.6, label="current")
    plt.legend()
    plt.title(f"{feature} distribution")
    plt.tight_layout()
    plt.savefig(output_dir / f"{feature}.png")
    plt.close()


def _prepare_datasets(current_path: str | None, reference_path: str | None, ref_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if current_path and reference_path:
        current_df = pd.read_csv(current_path)
        reference_df = pd.read_csv(reference_path)
    else:
        reference_df = _simulate_dataset(seed=11)
        current_df = _simulate_dataset(seed=21)
        # Inject mild drift for demonstration: shift means
        current_df = current_df.copy()
        current_df["home_xg"] *= 1.05
        current_df["away_xg"] *= 0.95
        current_df["form_home"] += 0.2
        current_df["form_away"] -= 0.1
    return reference_df, current_df


def _collect_prediction_frame(df: pd.DataFrame) -> pd.DataFrame:
    lambda_home = df.get("lambda_home")
    lambda_away = df.get("lambda_away")
    if lambda_home is None or lambda_away is None:
        _, _, lambda_home, lambda_away, _ = _fit_for_predictions(df)
    probs = _poisson_probs(lambda_home, lambda_away)
    return pd.DataFrame(probs, columns=["home_win", "draw", "away_win"])


def _fit_for_predictions(df: pd.DataFrame) -> tuple[Any, Any, np.ndarray, np.ndarray, list[str]]:
    from tools.golden_regression import _fit_models

    model_home, model_away, lambda_home, lambda_away, feature_names = _fit_models(df)
    return model_home, model_away, lambda_home, lambda_away, feature_names


def generate_report(
    *,
    current_path: str | None = None,
    reference_path: str | None = None,
    ref_days: int = 90,
    reports_dir: Path,
    psi_warn: float,
    psi_fail: float,
) -> DriftReport:
    ref_df, cur_df = _prepare_datasets(current_path, reference_path, ref_days)

    feature_columns = ["home_xg", "away_xg", "form_home", "form_away", "home_advantage"]
    drift_stats = []
    for feature in feature_columns:
        if feature in ref_df.columns and feature in cur_df.columns:
            stat = _evaluate_series(feature, ref_df[feature], cur_df[feature], psi_warn, psi_fail)
            drift_stats.append(stat)
            _render_histogram(feature, ref_df[feature], cur_df[feature], reports_dir / "plots")

    outcome_columns = {
        "total_goals": lambda df: df["goals_home"] + df["goals_away"],
        "goal_diff": lambda df: df["goals_home"] - df["goals_away"],
    }
    outcome_stats = []
    for feature, fn in outcome_columns.items():
        stat = _evaluate_series(feature, fn(ref_df), fn(cur_df), psi_warn, psi_fail)
        outcome_stats.append(stat)
        _render_histogram(feature, fn(ref_df), fn(cur_df), reports_dir / "plots")

    pred_ref = _collect_prediction_frame(ref_df)
    pred_cur = _collect_prediction_frame(cur_df)
    prediction_stats = []
    for column in pred_ref.columns:
        stat = _evaluate_series(column, pred_ref[column], pred_cur[column], psi_warn, psi_fail)
        prediction_stats.append(stat)
        _render_histogram(f"pred_{column}", pred_ref[column], pred_cur[column], reports_dir / "plots")

    summary_lines = ["# Drift Summary", "", "| Section | Feature | PSI | KS | Status | Note |", "| --- | --- | --- | --- | --- | --- |"]

    def _append_section(section: str, stats: list[DriftStatistic]) -> None:
        for stat in stats:
            summary_lines.append(
                f"| {section} | {stat.feature} | {stat.psi:.4f} | {stat.ks:.3f} | {stat.status} | {stat.note} |"
            )

    _append_section("features", drift_stats)
    _append_section("outcome", outcome_stats)
    _append_section("prediction", prediction_stats)

    summary_path = reports_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    payload = {
        "features": [stat.__dict__ for stat in drift_stats],
        "outcome": [stat.__dict__ for stat in outcome_stats],
        "predictions": [stat.__dict__ for stat in prediction_stats],
    }
    json_path = reports_dir / "summary.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return DriftReport(drift_stats, outcome_stats, prediction_stats, summary_path, json_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drift detection report")
    parser.add_argument("--current", help="Path to current dataset", default=None)
    parser.add_argument("--reference", help="Path to reference dataset", default=None)
    parser.add_argument("--ref-days", type=int, default=int(os.getenv("DRIFT_REF_DAYS", "90")))
    parser.add_argument("--reports-dir", default=str(ROOT / "reports" / "diagnostics" / "drift"))
    parser.add_argument("--psi-warn", type=float, default=float(os.getenv("DRIFT_PSI_WARN", "0.1")))
    parser.add_argument("--psi-fail", type=float, default=float(os.getenv("DRIFT_PSI_FAIL", "0.25")))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = generate_report(
        current_path=args.current,
        reference_path=args.reference,
        ref_days=args.ref_days,
        reports_dir=reports_dir,
        psi_warn=args.psi_warn,
        psi_fail=args.psi_fail,
    )
    worst_status = "✅"
    for bucket in (report.features, report.outcome, report.predictions):
        for stat in bucket:
            if stat.status == "❌":
                worst_status = "❌"
                break
            if stat.status == "⚠️" and worst_status != "❌":
                worst_status = "⚠️"
    print(json.dumps({"status": worst_status, "summary": str(report.summary_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
