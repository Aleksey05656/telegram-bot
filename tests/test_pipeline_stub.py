"""
@file: test_pipeline_stub.py
@description: stub test for PredictionPipeline
@dependencies: app.ml.prediction_pipeline
@created: 2025-09-10
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.needs_np

try:  # pragma: no cover
    import pandas as pd  # noqa: F401
except Exception:  # pragma: no cover
    pd = None


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
    from app.ml.prediction_pipeline import PredictionPipeline  # noqa: E402

    pipe = PredictionPipeline(model_registry=_Registry(), preprocessor=_Preproc())
    out = pipe.predict_proba(pd.DataFrame({"a": [1, 2, 3]}))
    assert out.shape == (3, 2)
