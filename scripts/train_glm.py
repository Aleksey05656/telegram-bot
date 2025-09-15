"""
@file: train_glm.py
@description: Train Poisson GLMs for home and away goals with recency weights.
@dependencies: pandas, numpy, scikit-learn, joblib
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor


def load_dataframe(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    if p.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    raise ValueError(f"unsupported format: {p.suffix}")


def train_models(df: pd.DataFrame, alpha: float, l2: float):
    feature_cols = [c for c in df.columns if c not in {"age_days", "home_goals", "away_goals"}]
    X = df[feature_cols]
    w = np.exp(-alpha * df["age_days"].astype(float))
    home = PoissonRegressor(alpha=l2)
    away = PoissonRegressor(alpha=l2)
    home.fit(X, df["home_goals"], sample_weight=w)
    away.fit(X, df["away_goals"], sample_weight=w)
    info = {
        "versions": {
            "sklearn": PoissonRegressor.__module__.split(".")[0],
            "pandas": pd.__version__,
        },
        "n_samples": int(len(df)),
        "alpha": alpha,
        "l2": l2,
        "score_home": float(home.score(X, df["home_goals"], sample_weight=w)),
        "score_away": float(away.score(X, df["away_goals"], sample_weight=w)),
    }
    return home, away, info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--l2", type=float, default=0.0)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    df = load_dataframe(args.input)
    model_home, model_away, info = train_models(df, args.alpha, args.l2)
    out_dir = Path("artifacts") / str(args.season_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_home, out_dir / "glm_home.pkl")
    joblib.dump(model_away, out_dir / "glm_away.pkl")
    with open(out_dir / "model_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
