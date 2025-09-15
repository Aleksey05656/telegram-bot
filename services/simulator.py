"""
@file: simulator.py
@description: Monte-Carlo simulator for football markets with entropy analytics.
@dependencies: numpy, collections, ml.metrics.entropy
@created: 2025-09-15
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ml.metrics.entropy import entropy_1x2, entropy_cs, entropy_totals
from ml.sim.bivariate_poisson import simulate_bipoisson


class Simulator:
    def run(
        self,
        lam_home: float,
        lam_away: float,
        rho: float,
        n_sims: int = 10000,
        return_samples: bool = False,
    ) -> dict[str, Any] | tuple[dict[str, Any], np.ndarray, np.ndarray]:
        home, away = simulate_bipoisson(lam_home, lam_away, rho, n_sims)
        total = float(n_sims)

        markets: dict[str, Any] = {}

        win1 = float(np.sum(home > away)) / total
        draw = float(np.sum(home == away)) / total
        win2 = float(np.sum(home < away)) / total
        markets["1x2"] = {"1": win1, "x": draw, "2": win2}

        markets["btts"] = {
            "yes": float(np.sum((home > 0) & (away > 0))) / total,
            "no": float(np.sum((home == 0) | (away == 0))) / total,
        }

        total_goals = home + away
        totals: dict[str, dict[str, float]] = {}
        for t in np.arange(0.5, 5.6, 1.0):
            over = float(np.sum(total_goals > t)) / total
            under = float(np.sum(total_goals < t)) / total
            totals[f"{t:.1f}"] = {"over": over, "under": under}
        markets["totals"] = totals

        cs: dict[str, float] = {}
        for h in range(7):
            for a in range(7):
                cs[f"{h}:{a}"] = float(np.sum((home == h) & (away == a))) / total
        other_prob = 1.0 - float(np.sum([cs[k] for k in cs]))
        cs["OTHER"] = other_prob
        markets["cs"] = cs

        ent: dict[str, float] = {}
        ent.update(entropy_1x2(win1, draw, win2))
        main_total = totals.get("2.5") or next(iter(totals.values()))
        ent.update(entropy_totals(main_total["over"], main_total["under"]))
        ent.update(entropy_cs(cs))
        markets["entropy"] = ent

        if return_samples:
            return markets, home, away
        return markets

    def save(self, result: dict[str, Any], path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


def render_markdown(markets: dict[str, Any]) -> str:
    """Render markets and entropies into a Markdown table."""
    lines = ["|Market|Selection|Prob|", "|---|---|---|"]
    for sel, prob in markets.get("1x2", {}).items():
        lines.append(f"|1X2|{sel}|{prob:.4f}|")
    if "totals" in markets:
        mt = markets["totals"].get("2.5") or next(iter(markets["totals"].values()))
        for sel, prob in mt.items():
            lines.append(f"|totals 2.5|{sel}|{prob:.4f}|")
    for sel, prob in markets.get("btts", {}).items():
        lines.append(f"|btts|{sel}|{prob:.4f}|")
    lines.append(f"|entropy|1x2|{markets['entropy']['1x2']:.4f}|")
    lines.append(f"|entropy|totals|{markets['entropy']['totals']:.4f}|")
    lines.append(f"|entropy|cs|{markets['entropy']['cs']:.4f}|")
    return "\n".join(lines)
