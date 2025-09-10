"""
@file: train_base_glm.py
@description: stub training procedure for base GLM model
@dependencies: pandas
@created: 2025-09-10
"""

from __future__ import annotations
from typing import Any, Optional
import pandas as pd


class DummyModel:
    def predict_proba(self, X):
        import numpy as np
        # равномерный заглушечный предикт на 2 класса
        p = np.full((len(X), 2), 0.5, dtype=float)
        return p


def train_base_glm(train_df: Optional[pd.DataFrame], cfg: Optional[dict]) -> Any:
    """
    Минимальная заглушка обучения GLM:
    - возвращает/сохраняет DummyModel
    - встраивается в pipeline до появления реального обучения
    """
    model = DummyModel()
    # TODO: сохранить модель в реестр (локально/S3). Пока возвращаем.
    return model
