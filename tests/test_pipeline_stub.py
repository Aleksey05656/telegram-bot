"""
@file: test_pipeline_stub.py
@description: stub test for PredictionPipeline
@dependencies: app.ml.prediction_pipeline
@created: 2025-09-10
"""

import pandas as pd
from app.ml.prediction_pipeline import PredictionPipeline


class _Preproc:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.fillna(0)


class _Registry:
    class _M:
        def predict_proba(self, X):
            import numpy as np
            return np.full((len(X), 2), 0.5)

    def load(self, name: str):
        return self._M()


def test_pipeline_predicts():
    pipe = PredictionPipeline(model_registry=_Registry(), preprocessor=_Preproc())
    out = pipe.predict_proba(pd.DataFrame({"a": [1, 2, 3]}))
    assert out.shape == (3, 2)
