"""
@file: modifiers_model.py
@description: Linear modifiers for Poisson lambdas with capping.
@dependencies: numpy, pandas, joblib, sklearn
@created: 2025-09-15
"""
from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


@dataclass
class ModifiersModel:
    cap_low: float = 0.7
    cap_high: float = 1.4
    alpha: float = 1.0

    def __post_init__(self) -> None:
        self.model_home = Ridge(alpha=self.alpha)
        self.model_away = Ridge(alpha=self.alpha)
        self.feature_names: list[str] | None = None

    def fit(self, X: pd.DataFrame, y_home: np.ndarray, y_away: np.ndarray) -> ModifiersModel:
        self.feature_names = list(X.columns)
        self.model_home.fit(X, y_home)
        self.model_away.fit(X, y_away)
        return self

    def transform(
        self,
        lam_home: np.ndarray,
        lam_away: np.ndarray,
        X: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray]:
        X = X[self.feature_names] if self.feature_names else X
        delta_home = self.model_home.predict(X)
        delta_away = self.model_away.predict(X)
        fac_home = np.clip(np.exp(delta_home), self.cap_low, self.cap_high)
        fac_away = np.clip(np.exp(delta_away), self.cap_low, self.cap_high)
        return lam_home * fac_home, lam_away * fac_away

    def save(self, path: str) -> None:
        joblib.dump(
            {
                "cap_low": self.cap_low,
                "cap_high": self.cap_high,
                "alpha": self.alpha,
                "feature_names": self.feature_names,
                "model_home": self.model_home,
                "model_away": self.model_away,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> ModifiersModel:
        obj = joblib.load(path)
        inst = cls(cap_low=obj["cap_low"], cap_high=obj["cap_high"], alpha=obj["alpha"])
        inst.feature_names = obj["feature_names"]
        inst.model_home = obj["model_home"]
        inst.model_away = obj["model_away"]
        return inst
