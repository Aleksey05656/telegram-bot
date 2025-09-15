"""
@file: test_modifiers.py
@description: Verify modifiers model capping and pipeline usage.
@dependencies: pandas, numpy, joblib, subprocess
@created: 2025-09-15
"""
import os
import subprocess
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.ml.model_registry import LocalModelRegistry
from ml.modifiers_model import ModifiersModel
from services.prediction_pipeline import PredictionPipeline


class _Pre:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[["x1"]]


class Const:
    def predict(self, X):
        return np.ones(len(X))


class SeasonRegistry(LocalModelRegistry):
    def __init__(self, season: int, base_dir: str = "artifacts"):
        super().__init__(base_dir)
        self.season = season

    def load(self, name: str):  # type: ignore[override]
        return super().load(name, season=self.season)

    def save(self, model, name: str):  # type: ignore[override]
        return super().save(model, name, season=self.season)


@pytest.mark.needs_np
def test_modifiers_training_and_application(tmp_path):
    df = pd.DataFrame(
        {
            "lambda_home": [1.0, 1.0],
            "lambda_away": [1.0, 1.0],
            "target_home": [1.5, 0.8],
            "target_away": [0.8, 1.5],
            "x1": [1.0, -1.0],
        }
    )
    data_path = tmp_path / "mods.csv"
    df.to_csv(data_path, index=False)
    season = 2025
    subprocess.run(
        [
            "python",
            "scripts/train_modifiers.py",
            "--season-id",
            str(season),
            "--alpha",
            "1.0",
            "--input",
            str(data_path),
        ],
        check=True,
        cwd=Path.cwd(),
        env={**os.environ, "PYTHONPATH": str(Path.cwd())},
    )
    art_dir = Path("artifacts") / str(season)
    model = ModifiersModel.load(art_dir / "modifiers_model.pkl")
    base = np.array([1.0])
    lam_h, lam_a = model.transform(base, base, pd.DataFrame({"x1": [10.0]}))
    assert 0.7 <= lam_h[0] <= 1.4
    assert 0.7 <= lam_a[0] <= 1.4
    registry = SeasonRegistry(season)
    registry.save(Const(), "glm_home")
    registry.save(Const(), "glm_away")
    pipeline = PredictionPipeline(_Pre(), registry)
    preds = pipeline.predict_proba(pd.DataFrame({"x1": [10.0]}))
    assert preds.shape == (1, 2)
    assert 0.7 <= preds[0, 0] <= 1.4
    assert 0.7 <= preds[0, 1] <= 1.4
