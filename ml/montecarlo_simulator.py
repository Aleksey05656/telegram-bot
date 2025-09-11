/**
 * @file: montecarlo_simulator.py
 * @description: Минимальный Пуассон-симулятор для расчёта рынков.
 * @dependencies: numpy
 * @created: 2025-08-23
 */
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class SimResult:
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    over_3_5: float
    btts: float
    top_scorelines: List[Tuple[str, float]]


def simulate(
    n_iter: int,
    lambda_home: float,
    lambda_away: float,
    seed: Optional[int] = None,
    top_n: int = 5,
) -> SimResult:
    rng = np.random.default_rng(seed)
    home_goals = rng.poisson(lam=lambda_home, size=n_iter)
    away_goals = rng.poisson(lam=lambda_away, size=n_iter)

    home_win = float(np.mean(home_goals > away_goals))
    draw = float(np.mean(home_goals == away_goals))
    away_win = float(np.mean(home_goals < away_goals))
    over_2_5 = float(np.mean(home_goals + away_goals > 2.5))
    over_3_5 = float(np.mean(home_goals + away_goals > 3.5))
    btts = float(np.mean((home_goals > 0) & (away_goals > 0)))

    scorelines = {
        f"{h}-{a}": count / n_iter
        for (h, a), count in zip(
            *np.unique(np.stack([home_goals, away_goals], axis=1), axis=0, return_counts=True)
        )
    }
    top_scores = sorted(scorelines.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return SimResult(home_win, draw, away_win, over_2_5, over_3_5, btts, top_scores)
