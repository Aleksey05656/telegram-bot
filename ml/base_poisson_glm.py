/**
 * @file: base_poisson_glm.py
 * @description: Базовая модель Poisson-GLM для расчёта λ_home и λ_away.
 * @dependencies: numpy
 * @created: 2025-08-23
 */
from typing import Any, Dict, List

import numpy as np


class BasePoissonModel:
    """Минимальная реализация базовой Poisson-GLM."""

    async def estimate(self, match_data: Dict[str, Any], team_stats: Dict[str, Any]) -> List[float]:
        """Возвращает базовые λ для домашней и гостевой команды."""
        try:
            # Заглушка: в реальной реализации используем обученную модель.
            return [1.5, 1.2]
        except Exception:
            return [1.5, 1.2]


base_poisson_model = BasePoissonModel()
