"""
@file: train_base_glm.py
@description: stub training procedure for base GLM model
@dependencies: pandas
@created: 2025-09-10
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .model_registry import LocalModelRegistry


class DummyModel:
    def predict_proba(self, X):
        import numpy as np

        # равномерный заглушечный предикт на 2 класса
        p = np.full((len(X), 2), 0.5, dtype=float)
        return p


def train_base_glm(
    train_df: pd.DataFrame | None,
    cfg: dict | None,
    *,
    season_id: int | None = None,
    registry: LocalModelRegistry | None = None,
) -> Any:
    """
    Минимальная заглушка обучения GLM:
    - возвращает и сохраняет DummyModel в реестр
    - встраивается в pipeline до появления реального обучения
    """
    model = DummyModel()
    reg = registry or LocalModelRegistry()
    reg.save(model, "base_glm", season=season_id)
    return model
