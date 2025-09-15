"""
@file: test_modifiers_metrics.py
@description: Validate base vs final modifier metrics.
@dependencies: services/prediction_pipeline.py, metrics/metrics.py
@created: 2025-09-15
"""
import math

import pandas as pd

from metrics import get_recorded_metrics
from services.prediction_pipeline import PredictionPipeline


def test_modifiers_metrics() -> None:
    class _Pre:
        def transform(self, df: pd.DataFrame) -> pd.DataFrame:  # type: ignore
            return df[["x"]]

    class _Model:
        def predict(self, X):  # type: ignore
            return [1.0] * len(X)

    class _Modifier:
        def transform(self, h, a, X):  # type: ignore
            return h, a

    class _Registry:
        def load(self, name: str, season: str | None = None):  # type: ignore
            if name in {"glm_home", "glm_away"}:
                return _Model()
            if name == "modifiers_model":
                return _Modifier()
            raise KeyError

    df = pd.DataFrame(
        {
            "x": [0, 1],
            "home_goals": [1, 0],
            "away_goals": [0, 2],
        }
    )
    pipe = PredictionPipeline(_Pre(), _Registry())
    pipe.predict_proba(df)
    metrics = get_recorded_metrics()
    assert metrics["glm_base_logloss"] == metrics["glm_mod_final_logloss"]
    assert metrics["glm_base_ece"] == metrics["glm_mod_final_ece"]
    assert not math.isnan(metrics["glm_base_logloss"])
    assert not math.isnan(metrics["glm_mod_final_ece"])
