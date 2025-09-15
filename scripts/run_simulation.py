"""
@file: run_simulation.py
@description: CLI to run Monte-Carlo simulation using bivariate Poisson.
@dependencies: numpy, json
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.simulator import Simulator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--home", type=float, required=True)
    parser.add_argument("--away", type=float, required=True)
    parser.add_argument("--rho", type=float, default=0.0)
    parser.add_argument("--n-sims", type=int, default=10000)
    args = parser.parse_args()

    sim = Simulator()
    result = sim.run(args.home, args.away, args.rho, args.n_sims)
    out_dir = Path("reports/sims")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.season_id}_{args.home}_{args.away}.json"
    sim.save(result, out_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
