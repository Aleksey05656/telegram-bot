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

from app.data_processor import build_features, to_model_matrix, validate_input
from app.ml.model_registry import LocalModelRegistry
from services.prediction_pipeline import PredictionPipeline


class _Preprocessor:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover - simple passthrough
        return df


@pytest.mark.needs_np
def test_train_glm_and_pipeline(tmp_path):
    train_df = pd.DataFrame(
        {
            "home_team": ["A", "B", "C", "A"],
            "away_team": ["B", "C", "A", "C"],
            "date": pd.date_range("2024-01-01", periods=4, freq="7D"),
            "xG_home": [1.1, 0.8, 1.3, 0.9],
            "xG_away": [0.6, 1.0, 0.7, 1.2],
            "goals_home": [2, 0, 3, 1],
            "goals_away": [0, 1, 1, 2],
        }
    )
    data_path = tmp_path / "train.csv"
    train_df.to_csv(data_path, index=False)
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
    validated = validate_input(train_df)
    features = build_features(validated)
    X_home, _, _, _ = to_model_matrix(features)
    lambdas_home = np.exp(model_home.predict(X_home))
    assert (lambdas_home > 0).all()
    assert (lambdas_home < 10).all()
    registry = LocalModelRegistry(base_dir="artifacts")
    pipeline = PredictionPipeline(_Preprocessor(), registry)
    preds = pipeline.predict_proba(train_df)
    assert preds.shape == (len(train_df), 2)
    assert (preds > 0).all()
