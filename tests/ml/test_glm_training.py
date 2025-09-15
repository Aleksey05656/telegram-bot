"""
@file: test_glm_training.py
@description: Check GLM training artifacts and pipeline integration.
@dependencies: pandas, numpy, joblib, LocalModelRegistry
@created: 2025-09-15
"""
import json
import subprocess
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.ml.model_registry import LocalModelRegistry
from services.prediction_pipeline import PredictionPipeline


class _Preprocessor:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[["x1"]]


@pytest.mark.needs_np
def test_train_glm_and_pipeline(tmp_path):
    df = pd.DataFrame(
        {
            "age_days": [0, 1, 2, 3],
            "home_goals": [1, 0, 2, 1],
            "away_goals": [0, 1, 1, 2],
            "x1": [0.1, 0.2, 0.3, 0.4],
        }
    )
    data_path = tmp_path / "train.csv"
    df.to_csv(data_path, index=False)
    season = 2024
    subprocess.run(
        [
            "python",
            "scripts/train_glm.py",
            "--season-id",
            str(season),
            "--alpha",
            "0.1",
            "--l2",
            "0.0",
            "--input",
            str(data_path),
        ],
        check=True,
    )
    art_dir = Path("artifacts") / str(season)
    assert (art_dir / "glm_home.pkl").exists()
    assert (art_dir / "glm_away.pkl").exists()
    info = json.loads((art_dir / "model_info.json").read_text())
    for key in ["versions", "n_samples", "alpha", "l2", "score_home", "score_away"]:
        assert key in info
    assert info["n_samples"] == 4
    assert info["alpha"] == 0.1
    assert info["l2"] == 0.0
    model_home = joblib.load(art_dir / "glm_home.pkl")
    lambdas = np.exp(model_home.predict(df[["x1"]]))
    assert (lambdas > 0).all()
    assert (lambdas < 10).all()
    registry = LocalModelRegistry(base_dir="artifacts")
    pipeline = PredictionPipeline(_Preprocessor(), registry)
    preds = pipeline.predict_proba(df[["x1"]])
    assert preds.shape == (len(df), 2)
    assert (preds > 0).all()
