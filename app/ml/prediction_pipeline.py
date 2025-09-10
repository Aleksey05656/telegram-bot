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
    def transform(self, df: pd.DataFrame) -> pd.DataFrame: ...


class ModelRegistry(Protocol):
    def load(self, name: str): ...


class PredictionPipeline:
    def __init__(self, model_registry: ModelRegistry, preprocessor: Preprocessor):
        self.model_registry = model_registry
        self.preprocessor = preprocessor

    def predict_proba(self, df: pd.DataFrame):
        X = self.preprocessor.transform(df)
        model = self.model_registry.load("current")
        if hasattr(model, "predict_proba"):
            return model.predict_proba(X)
        return model.predict(X)
