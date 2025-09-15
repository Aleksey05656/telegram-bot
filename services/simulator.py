"""
@file: simulator.py
@description: Monte-Carlo simulator for football markets.
@dependencies: numpy, collections
@created: 2025-09-15
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from ml.sim.bivariate_poisson import simulate_bivariate_poisson


class Simulator:
    def run(
        self, lam_home: float, lam_away: float, rho: float, n_sims: int = 10000
    ) -> dict[str, Any]:
        home, away = simulate_bivariate_poisson(lam_home, lam_away, rho, n_sims)
        probs_cs = Counter(zip(home, away, strict=False))
        total = float(n_sims)
        win1 = float(np.sum(home > away)) / total
        draw = float(np.sum(home == away)) / total
        win2 = float(np.sum(home < away)) / total
        btts = float(np.sum((home > 0) & (away > 0))) / total
        over = float(np.sum(home + away > 2.5)) / total
        under = 1.0 - over
        cs = {f"{h}:{a}": c / total for (h, a), c in probs_cs.items()}
        return {
            "1X2": {"1": win1, "X": draw, "2": win2},
            "BTTS": {"yes": btts, "no": 1 - btts},
            "Totals": {"over_2_5": over, "under_2_5": under},
            "CS": cs,
        }

    def save(self, result: dict[str, Any], path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
