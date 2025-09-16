"""
@file: train_modifiers.py
@description: Train modifiers model that adjusts base lambdas.
@dependencies: pandas, numpy, joblib, sklearn
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data_processor import build_features, validate_input
from ml.modifiers_model import ModifiersModel


def load_dataframe(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    if p.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    raise ValueError(f"unsupported format: {p.suffix}")


def _prepare_modifier_features(features: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    feature_cols = ["rest_days"] + sorted(
        col for col in features.columns if col.startswith("rolling_xg_")
    )

    home = (
        features.loc[features["is_home"] == 1, ["match_id", *feature_cols]]
        .rename(columns={col: f"{col}_home" for col in feature_cols})
        .copy()
    )
    away = (
        features.loc[features["is_home"] == 0, ["match_id", *feature_cols]]
        .rename(columns={col: f"{col}_away" for col in feature_cols})
        .copy()
    )

    combined = home.merge(away, on="match_id", how="inner")
    combined = combined.sort_values("match_id").reset_index(drop=True)
    match_ids = combined["match_id"].to_numpy()
    X = combined.drop(columns="match_id")
    X.insert(0, "bias", 1.0)
    return X, match_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    raw_df = load_dataframe(args.input)
    validated = validate_input(raw_df)

    required = {"lambda_home", "lambda_away", "target_home", "target_away"}
    missing = required - set(validated.columns)
    if missing:
        raise ValueError(f"missing required modifier columns: {', '.join(sorted(missing))}")

    features = build_features(validated)
    X, match_ids = _prepare_modifier_features(features)

    targets = validated.loc[match_ids].reset_index(drop=True)
    y_home = np.log(targets["target_home"].astype(float)) - np.log(targets["lambda_home"].astype(float))
    y_away = np.log(targets["target_away"].astype(float)) - np.log(targets["lambda_away"].astype(float))
    model = ModifiersModel(alpha=args.alpha).fit(X, y_home, y_away)
    out_dir = Path("artifacts") / str(args.season_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(out_dir / "modifiers_model.pkl")


if __name__ == "__main__":
    main()
