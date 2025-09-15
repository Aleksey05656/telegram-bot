"""
@file: train_modifiers.py
@description: Train modifiers model that adjusts base lambdas.
@dependencies: pandas, numpy, joblib, sklearn
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ml.modifiers_model import ModifiersModel


def load_dataframe(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    if p.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    raise ValueError(f"unsupported format: {p.suffix}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    df = load_dataframe(args.input)
    feature_cols = [
        c
        for c in df.columns
        if c not in {"lambda_home", "lambda_away", "target_home", "target_away"}
    ]
    X = df[feature_cols]
    y_home = np.log(df["target_home"]) - np.log(df["lambda_home"])
    y_away = np.log(df["target_away"]) - np.log(df["lambda_away"])
    model = ModifiersModel(alpha=args.alpha).fit(X, y_home, y_away)
    out_dir = Path("artifacts") / str(args.season_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(out_dir / "modifiers_model.pkl")


if __name__ == "__main__":
    main()
