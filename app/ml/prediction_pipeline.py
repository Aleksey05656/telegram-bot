"""
@file: prediction_pipeline.py
@description: model prediction pipeline with preprocessing and model registry
@dependencies: pandas, Preprocessor, ModelRegistry
@created: 2025-09-10
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class Preprocessor(Protocol):
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


class ModelRegistry(Protocol):
    def load(self, name: str, season: int | None = None):
        ...


class PredictionPipeline:
    def __init__(
        self,
        model_registry: ModelRegistry,
        preprocessor: Preprocessor,
        season: int | None = None,
    ):
        self.model_registry = model_registry
        self.preprocessor = preprocessor
        self.season = season

    def predict_proba(self, df: pd.DataFrame, season: int | None = None):
        X = self.preprocessor.transform(df)
        model = self.model_registry.load("base_glm", season=season or self.season)
        if hasattr(model, "predict_proba"):
            return model.predict_proba(X)
        return model.predict(X)
