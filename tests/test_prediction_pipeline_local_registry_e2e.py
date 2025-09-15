"""
@file: test_prediction_pipeline_local_registry_e2e.py
@description: e2e test for PredictionPipeline with LocalModelRegistry
@dependencies: app.ml.prediction_pipeline, app.ml.model_registry
@created: 2025-09-17
"""

from __future__ import annotations

import pytest

from app.ml.model_registry import LocalModelRegistry
from app.ml.prediction_pipeline import PredictionPipeline

pytest.importorskip("numpy")
pytest.importorskip("pandas")

pytestmark = pytest.mark.needs_np

try:  # pragma: no cover
    import numpy as np
    import pandas as pd
except Exception:  # pragma: no cover
    np = None
    pd = None


class _Preproc:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.fillna(0)


class _Model:
    def predict_proba(self, X):
        return np.full((len(X), 2), 0.5)


def test_pipeline_with_local_registry(tmp_path):
    reg = LocalModelRegistry(base_dir=tmp_path)
    reg.save(_Model(), "base_glm", season=2024)
    pipe = PredictionPipeline(model_registry=reg, preprocessor=_Preproc(), season=2024)
    out = pipe.predict_proba(pd.DataFrame({"a": [1, 2, 3]}))
    assert out.shape == (3, 2)
