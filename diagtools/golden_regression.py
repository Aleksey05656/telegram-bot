"""
/**
 * @file: diagtools/golden_regression.py
 * @description: Golden baseline generation and epsilon-regression checks for GLM artefacts.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class GoldenSnapshot:
    coefficients_home: list[float]
    coefficients_away: list[float]
    lambda_baseline_home: list[float]
    lambda_baseline_away: list[float]
    metrics: dict[str, float]
    market_probabilities: list[list[float]]
    feature_names: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": self.feature_names,
            "coefficients": {"home": self.coefficients_home, "away": self.coefficients_away},
            "lambda_baseline": {
                "home": self.lambda_baseline_home,
                "away": self.lambda_baseline_away,
            },
            "metrics": self.metrics,
            "market_probabilities": self.market_probabilities,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GoldenSnapshot":
        return cls(
            coefficients_home=[float(x) for x in payload["coefficients"]["home"]],
            coefficients_away=[float(x) for x in payload["coefficients"]["away"]],
            lambda_baseline_home=[float(x) for x in payload["lambda_baseline"]["home"]],
            lambda_baseline_away=[float(x) for x in payload["lambda_baseline"]["away"]],
            metrics={k: float(v) for k, v in payload["metrics"].items()},
            market_probabilities=[[float(v) for v in row] for row in payload["market_probabilities"]],
            feature_names=list(payload["feature_names"]),
        )


def _simulate_dataset(n_rows: int = 256, seed: int = 20240920) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-08-01", periods=n_rows, freq="D")
    home_xg = rng.gamma(shape=2.2, scale=0.7, size=n_rows)
    away_xg = rng.gamma(shape=2.0, scale=0.6, size=n_rows)
    home_xga = rng.gamma(shape=2.1, scale=0.5, size=n_rows)
    away_xga = rng.gamma(shape=2.1, scale=0.55, size=n_rows)
    form_home = rng.normal(loc=0.0, scale=0.6, size=n_rows)
    form_away = rng.normal(loc=0.0, scale=0.6, size=n_rows)
    home_advantage = rng.normal(loc=0.18, scale=0.03, size=n_rows)
    fatigue_delta = rng.normal(loc=0.0, scale=0.2, size=n_rows)

    lambda_home = np.clip(
        np.exp(
            0.05
            + 0.35 * (home_xg - away_xga)
            + 0.09 * form_home
            - 0.07 * fatigue_delta
            + home_advantage
        ),
        0.2,
        5.0,
    )
    lambda_away = np.clip(
        np.exp(
            -0.02
            + 0.32 * (away_xg - home_xga)
            + 0.08 * form_away
            + 0.05 * fatigue_delta
            - 0.15 * home_advantage
        ),
        0.2,
        4.5,
    )
    goals_home = rng.poisson(lambda_home)
    goals_away = rng.poisson(lambda_away)

    return pd.DataFrame(
        {
            "date": dates,
            "home_xg": home_xg,
            "away_xg": away_xg,
            "home_xga": home_xga,
            "away_xga": away_xga,
            "form_home": form_home,
            "form_away": form_away,
            "home_advantage": home_advantage,
            "fatigue_delta": fatigue_delta,
            "goals_home": goals_home,
            "goals_away": goals_away,
        }
    )


def _fit_models(df: pd.DataFrame) -> tuple[Ridge, Ridge, np.ndarray, np.ndarray, list[str]]:
    feature_names = [
        "home_xg",
        "away_xg",
        "home_xga",
        "away_xga",
        "form_home",
        "form_away",
        "home_advantage",
        "fatigue_delta",
    ]
    X = df[feature_names].to_numpy()
    y_home = np.log1p(df["goals_home"].to_numpy())
    y_away = np.log1p(df["goals_away"].to_numpy())
    model_home = Ridge(alpha=0.35).fit(X, y_home)
    model_away = Ridge(alpha=0.35).fit(X, y_away)
    lambda_home = np.clip(np.expm1(model_home.predict(X)), 0.05, 6.0)
    lambda_away = np.clip(np.expm1(model_away.predict(X)), 0.05, 6.0)
    return model_home, model_away, lambda_home, lambda_away, feature_names


def _poisson_probs(lambda_home: np.ndarray, lambda_away: np.ndarray, max_goals: int = 10) -> np.ndarray:
    probs = np.zeros((lambda_home.size, 3))
    for idx, (lam_h, lam_a) in enumerate(zip(lambda_home, lambda_away)):
        dist_home = [math.exp(-lam_h) * lam_h**k / math.factorial(k) for k in range(max_goals + 1)]
        dist_away = [math.exp(-lam_a) * lam_a**k / math.factorial(k) for k in range(max_goals + 1)]
        total = 0.0
        outcome = [0.0, 0.0, 0.0]
        for h, p_h in enumerate(dist_home):
            for a, p_a in enumerate(dist_away):
                prob = p_h * p_a
                total += prob
                if h > a:
                    outcome[0] += prob
                elif h == a:
                    outcome[1] += prob
                else:
                    outcome[2] += prob
        if total <= 0:
            probs[idx] = [1 / 3, 1 / 3, 1 / 3]
        else:
            probs[idx] = np.asarray(outcome) / total
    return probs


def _metrics(df: pd.DataFrame, lambda_home: np.ndarray, lambda_away: np.ndarray) -> tuple[dict[str, float], np.ndarray]:
    probs = _poisson_probs(lambda_home, lambda_away)
    outcome = np.where(df["goals_home"].to_numpy() > df["goals_away"], 0, 2)
    outcome[df["goals_home"].to_numpy() == df["goals_away"].to_numpy()] = 1
    outcome_one_hot = np.eye(3)[outcome]
    clipped = np.clip(probs, 1e-6, 1 - 1e-6)
    clipped = clipped / clipped.sum(axis=1, keepdims=True)
    logloss = -np.mean(np.log(np.sum(clipped * outcome_one_hot, axis=1)))
    brier = np.mean(np.sum((clipped - outcome_one_hot) ** 2, axis=1))
    return {"logloss": float(logloss), "brier": float(brier)}, probs


def build_snapshot(seed: int = 20240920) -> GoldenSnapshot:
    df = _simulate_dataset(seed=seed)
    model_home, model_away, lambda_home, lambda_away, feature_names = _fit_models(df)
    metrics, probs = _metrics(df, lambda_home, lambda_away)
    baseline = GoldenSnapshot(
        coefficients_home=[float(v) for v in model_home.coef_],
        coefficients_away=[float(v) for v in model_away.coef_],
        lambda_baseline_home=[float(v) for v in lambda_home[:32]],
        lambda_baseline_away=[float(v) for v in lambda_away[:32]],
        metrics=metrics,
        market_probabilities=[[float(x) for x in row] for row in probs[:32]],
        feature_names=feature_names,
    )
    return baseline


def compare_snapshots(current: GoldenSnapshot, golden: GoldenSnapshot) -> dict[str, Any]:
    coef_eps = float(os.getenv("GOLDEN_COEF_EPS", "0.005"))
    lambda_mape_threshold = float(os.getenv("GOLDEN_LAMBDA_MAPE", "0.015"))
    prob_eps = float(os.getenv("GOLDEN_PROB_EPS", "0.005"))

    diff_report: dict[str, Any] = {"status": "✅", "checks": {}}

    for label, current_values, golden_values in (
        ("coefficients_home", current.coefficients_home, golden.coefficients_home),
        ("coefficients_away", current.coefficients_away, golden.coefficients_away),
    ):
        if len(current_values) != len(golden_values):
            diff_report["checks"][label] = {"status": "❌", "note": "length mismatch"}
            diff_report["status"] = "❌"
            continue
        delta = np.abs(np.array(current_values) - np.array(golden_values))
        max_delta = float(np.max(delta)) if delta.size else 0.0
        status = "✅" if max_delta <= coef_eps else "❌"
        diff_report["checks"][label] = {"status": status, "max_delta": max_delta, "threshold": coef_eps}
        if status == "❌":
            diff_report["status"] = "❌"

    def _mape(current_values: list[float], golden_values: list[float]) -> float:
        curr = np.array(current_values)
        ref = np.array(golden_values)
        denom = np.where(ref == 0, 1e-6, ref)
        return float(np.mean(np.abs((curr - ref) / denom)))

    lambda_home_mape = _mape(current.lambda_baseline_home, golden.lambda_baseline_home)
    lambda_away_mape = _mape(current.lambda_baseline_away, golden.lambda_baseline_away)
    lambda_status = "✅" if max(lambda_home_mape, lambda_away_mape) <= lambda_mape_threshold else "❌"
    diff_report["checks"]["lambda"] = {
        "status": lambda_status,
        "home_mape": lambda_home_mape,
        "away_mape": lambda_away_mape,
        "threshold": lambda_mape_threshold,
    }
    if lambda_status == "❌":
        diff_report["status"] = "❌"

    prob_delta = np.abs(np.array(current.market_probabilities) - np.array(golden.market_probabilities))
    prob_max = float(np.max(prob_delta)) if prob_delta.size else 0.0
    prob_status = "✅" if prob_max <= prob_eps else "❌"
    diff_report["checks"]["probabilities"] = {"status": prob_status, "max_delta": prob_max, "threshold": prob_eps}
    if prob_status == "❌":
        diff_report["status"] = "❌"

    metrics_delta = {
        key: abs(current.metrics[key] - golden.metrics.get(key, current.metrics[key])) for key in current.metrics
    }
    diff_report["checks"]["metrics"] = {"status": "✅", "delta": metrics_delta}

    return diff_report


def load_snapshot(path: Path) -> GoldenSnapshot | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return GoldenSnapshot.from_dict(payload)


def write_snapshot(path: Path, snapshot: GoldenSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Golden regression checker")
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"), help="Directory for golden baselines")
    parser.add_argument("--seed", type=int, default=20240920)
    parser.add_argument("--check", action="store_true", help="Validate against the existing baseline")
    parser.add_argument("--update", action="store_true", help="Recreate the baseline snapshot")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    reports_dir = Path(args.reports_dir)
    baseline_path = reports_dir / "golden" / "baseline.json"
    current_snapshot = build_snapshot(seed=args.seed)

    existing = load_snapshot(baseline_path)
    if existing is None or args.update:
        write_snapshot(baseline_path, current_snapshot)
        print(f"Baseline written to {baseline_path}")
        if args.check and existing is not None:
            diff = compare_snapshots(current_snapshot, existing)
            print(json.dumps(diff, indent=2, ensure_ascii=False))
            if diff["status"] != "✅":
                raise SystemExit(1)
        return

    if args.check:
        diff = compare_snapshots(current_snapshot, existing)
        print(json.dumps(diff, indent=2, ensure_ascii=False))
        if diff["status"] != "✅":
            raise SystemExit(1)
    else:
        write_snapshot(baseline_path, current_snapshot)
        print(f"Baseline refreshed at {baseline_path}")


if __name__ == "__main__":
    main()
