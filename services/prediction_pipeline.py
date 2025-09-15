"""
@file: prediction_pipeline.py
@description: Minimal prediction pipeline skeleton for production wiring.
@dependencies: pandas (optional), numpy (optional), joblib, Preprocessor, ModelRegistry
@created: 2025-09-12
"""
import os
from typing import Any, Protocol

try:  # optional import for constrained environments
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = Any  # type: ignore

from app.config import get_settings
from logger import logger
from metrics import ece_poisson, logloss_poisson, record_metrics


class Preprocessor(Protocol):
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


class ModelRegistry(Protocol):
    def load(self, name: str):
        ...


class _DummyModel:
    def predict(self, X):
        try:
            import numpy as np

            return np.ones(len(X), dtype=float)
        except Exception:  # no numpy available
            return [1.0 for _ in range(len(X))]


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

    def _load_models(self):
        if self._reg is None:
            return _DummyModel(), _DummyModel()
        try:
            return self._reg.load("glm_home"), self._reg.load("glm_away")
        except Exception:
            try:
                base_dir = getattr(self._reg, "base_dir", None)
                if base_dir is not None:
                    for sub in base_dir.iterdir():
                        m_home = self._reg.load("glm_home", season=sub.name)
                        m_away = self._reg.load("glm_away", season=sub.name)
                        return m_home, m_away
            except Exception:
                try:
                    m = self._reg.load("current")
                    return m, m
                except Exception:
                    return _DummyModel(), _DummyModel()

    def predict_proba(self, df: pd.DataFrame):
        X = self._pre.transform(df)
        model_home, model_away = self._load_models()
        if hasattr(model_home, "predict_proba") and hasattr(model_away, "predict_proba"):
            ph = model_home.predict_proba(X)
            pa = model_away.predict_proba(X)
            pred_home = ph[:, 0] if ph.ndim == 2 else ph
            pred_away = pa[:, 1] if pa.ndim == 2 else pa
        else:
            pred_home = model_home.predict(X)
            pred_away = model_away.predict(X)

        pred_home_base = pred_home
        pred_away_base = pred_away
        modifiers_applied = False
        if self._reg is not None:
            try:
                mod = self._reg.load("modifiers_model")
                pred_home, pred_away = mod.transform(pred_home, pred_away, X)
                modifiers_applied = True
                logger.info("modifiers_applied=1")
            except Exception:
                logger.debug("modifiers_applied=0")

        if {
            "home_goals",
            "away_goals",
        }.issubset(getattr(df, "columns", [])):
            y_true = df["home_goals"].tolist() + df["away_goals"].tolist()
            base_pred = list(pred_home_base) + list(pred_away_base)
            final_pred = list(pred_home) + list(pred_away)
            settings = get_settings()
            tags = {
                "service": settings.app_name,
                "env": settings.env,
                "version": settings.git_sha,
                "season": os.getenv("SEASON_ID", "default"),
                "modifiers_applied": "false",
            }
            base_logloss = logloss_poisson(y_true, base_pred)
            base_ece = ece_poisson(y_true, base_pred)
            record_metrics("glm_base_logloss", base_logloss, tags)
            record_metrics("glm_base_ece", base_ece, tags)
            tags_final = dict(tags)
            tags_final["modifiers_applied"] = "true" if modifiers_applied else "false"
            final_logloss = logloss_poisson(y_true, final_pred)
            final_ece = ece_poisson(y_true, final_pred)
            record_metrics("glm_mod_final_logloss", final_logloss, tags_final)
            record_metrics("glm_mod_final_ece", final_ece, tags_final)
        try:
            import numpy as np

            return np.column_stack([pred_home, pred_away])
        except Exception:  # pragma: no cover
            return [[h, a] for h, a in zip(pred_home, pred_away, strict=False)]
