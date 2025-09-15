"""
@file: prediction_pipeline.py
@description: Minimal prediction pipeline skeleton for production wiring.
@dependencies: pandas (optional), numpy (optional), Preprocessor, ModelRegistry
@created: 2025-09-12
"""
from typing import Any, Protocol

try:  # optional import for constrained environments
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = Any  # type: ignore


class Preprocessor(Protocol):
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


class ModelRegistry(Protocol):
    def load(self, name: str):
        ...


class _DummyModel:
    def predict_proba(self, X):
        try:
            import numpy as np

            return np.full((len(X), 2), 0.5, dtype=float)
        except Exception:  # no numpy available
            return [[0.5, 0.5] for _ in range(len(X))]


class PredictionPipeline:
    """
    Basic flow:
      df -> preprocessor.transform -> X
      model = registry.load("current") or _DummyModel()
      return model.predict_proba(X) or model.predict(X)
    """

    def __init__(self, preprocessor: Preprocessor, model_registry: ModelRegistry | None = None):
        self._pre = preprocessor
        self._reg = model_registry

    def _load_model(self):
        if self._reg is None:
            return _DummyModel()
        m = self._reg.load("current")
        return m or _DummyModel()

    def predict_proba(self, df: pd.DataFrame):
        X = self._pre.transform(df)
        model = self._load_model()
        if hasattr(model, "predict_proba"):
            return model.predict_proba(X)
        return model.predict(X)
