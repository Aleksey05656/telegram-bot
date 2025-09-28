"""
@file: train_glm.py
@description: Train Poisson GLMs for home and away goals with recency weights.
@dependencies: pandas, numpy, scikit-learn, joblib
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from typing import TYPE_CHECKING

from scripts._optional import optional_dependency

joblib = optional_dependency("joblib")
np = optional_dependency("numpy")
pd = optional_dependency("pandas")
PoissonRegressor = optional_dependency("sklearn.linear_model", attr="PoissonRegressor")

if TYPE_CHECKING:  # pragma: no cover - typing aid
    import joblib as _joblib
    import numpy as _np
    import pandas as _pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data_processor import build_features, to_model_matrix, validate_input


def load_dataframe(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    if p.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    raise ValueError(f"unsupported format: {p.suffix}")


def _compute_recency_weights(dates: pd.Series, alpha: float) -> np.ndarray:
    if dates.empty:
        return np.array([], dtype=float)
    anchor = dates.max()
    age_days = (anchor - dates).dt.days.astype(float)
    return np.exp(-alpha * age_days)


def train_models(df: pd.DataFrame, alpha: float, l2: float):
    validated = validate_input(df)
    features = build_features(validated)
    X_home, y_home, X_away, y_away = to_model_matrix(features)

    home_dates = features.loc[features["is_home"] == 1, "date"].reset_index(drop=True)
    away_dates = features.loc[features["is_home"] == 0, "date"].reset_index(drop=True)
    w_home = _compute_recency_weights(home_dates, alpha)
    w_away = _compute_recency_weights(away_dates, alpha)

    home = PoissonRegressor(alpha=l2)
    away = PoissonRegressor(alpha=l2)
    home.fit(X_home, y_home, sample_weight=w_home)
    away.fit(X_away, y_away, sample_weight=w_away)
    info = {
        "versions": {
            "sklearn": PoissonRegressor.__module__.split(".")[0],
            "pandas": pd.__version__,
        },
        "n_samples": int(len(validated)),
        "alpha": alpha,
        "l2": l2,
        "score_home": float(home.score(X_home, y_home, sample_weight=w_home)),
        "score_away": float(away.score(X_away, y_away, sample_weight=w_away)),
    }
    return home, away, info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--l2", type=float, default=0.0)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    raw_df = load_dataframe(args.input)
    model_home, model_away, info = train_models(raw_df, args.alpha, args.l2)
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    registry_root = Path(os.getenv("MODEL_REGISTRY_PATH", str(data_root / "artifacts")))
    out_dir = registry_root / str(args.season_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_home, out_dir / "glm_home.pkl")
    joblib.dump(model_away, out_dir / "glm_away.pkl")
    with open(out_dir / "model_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
