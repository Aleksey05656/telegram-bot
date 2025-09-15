"""
@file: run_simulation.py
@description: CLI to run Monte-Carlo simulation using bivariate Poisson.
@dependencies: numpy, json, sqlite
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from ml.calibration import calibration_report  # noqa: E402
from services.simulator import Simulator  # noqa: E402
from storage.persistence import SQLitePredictionsStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--rho", type=float, default=0.1)
    parser.add_argument("--n-sims", type=int, default=10000)
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--report-md")
    parser.add_argument("--write-db", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    version = settings.git_sha or settings.app_version

    def guess_lambda(name: str) -> float:
        return 1.2 + (len(name) % 3) * 0.1

    lam_home = guess_lambda(args.home)
    lam_away = guess_lambda(args.away)

    sim = Simulator()
    if args.calibrate:
        result, home_arr, away_arr = sim.run(
            lam_home, lam_away, args.rho, args.n_sims, return_samples=True
        )
        prob_dict = {
            "1x2": np.tile(
                [
                    result["1x2"]["1"],
                    result["1x2"]["x"],
                    result["1x2"]["2"],
                ],
                (args.n_sims, 1),
            ),
            "btts": np.tile(
                [result["btts"]["yes"], result["btts"]["no"]],
                (args.n_sims, 1),
            ),
        }
        label_dict = {
            "1x2": np.column_stack(
                [
                    (home_arr > away_arr).astype(float),
                    (home_arr == away_arr).astype(float),
                    (home_arr < away_arr).astype(float),
                ]
            ),
            "btts": np.column_stack(
                [
                    ((home_arr > 0) & (away_arr > 0)).astype(float),
                    ((home_arr == 0) | (away_arr == 0)).astype(float),
                ]
            ),
        }
        total_goals = home_arr + away_arr
        for t, probs in result["totals"].items():
            prob_dict[f"totals_{t}"] = np.tile([probs["over"], probs["under"]], (args.n_sims, 1))
            label_dict[f"totals_{t}"] = np.column_stack(
                [
                    (total_goals > float(t)).astype(float),
                    (total_goals < float(t)).astype(float),
                ]
            )
        cs_keys = list(result["cs"].keys())
        prob_dict["cs"] = np.tile([result["cs"][k] for k in cs_keys], (args.n_sims, 1))
        labels = np.zeros((args.n_sims, len(cs_keys)))
        for i, (h, a) in enumerate(zip(home_arr, away_arr, strict=False)):
            key = f"{h}:{a}" if f"{h}:{a}" in result["cs"] else "OTHER"
            labels[i, cs_keys.index(key)] = 1.0
        label_dict["cs"] = labels

        report = calibration_report(prob_dict, label_dict)

        report_path = (
            Path(args.report_md)
            if args.report_md
            else Path(
                f"reports/metrics/ECE_simulation_{args.season_id}_{args.home}_vs_{args.away}.md"
            )
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# Simulation {args.home} vs {args.away}\n\n"
            f"version: {version}\n"
            f"season: {args.season_id}\n"
            f"rho: {args.rho}, n_sims: {args.n_sims}\n\n"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write("|market|ece_before|ece_after|delta|\n")
            f.write("|---|---|---|---|\n")
            for k, v in report.items():
                delta = v["ece_after"] - v["ece_before"]
                f.write(f"|{k}|{v['ece_before']:.4f}|{v['ece_after']:.4f}|{delta:+.4f}|\n")

    else:
        result = sim.run(lam_home, lam_away, args.rho, args.n_sims)

    if args.write_db:
        db_path = os.getenv("PREDICTIONS_DB_URL", "var/predictions.sqlite")
        store = SQLitePredictionsStore(db_path)
        match_id = f"{args.season_id}:{args.home} vs {args.away}:{date.today().isoformat()}"
        ts = datetime.utcnow().isoformat()
        records = []
        for market, selections in result.items():
            if market == "totals":
                for th, probs in selections.items():
                    records.append(
                        (
                            match_id,
                            market,
                            f"over_{th}",
                            probs["over"],
                            {"ts": ts, "season": args.season_id, "extra": {"threshold": th}},
                        )
                    )
                    records.append(
                        (
                            match_id,
                            market,
                            f"under_{th}",
                            probs["under"],
                            {"ts": ts, "season": args.season_id, "extra": {"threshold": th}},
                        )
                    )
            else:
                for sel, prob in selections.items():
                    records.append(
                        (
                            match_id,
                            market,
                            sel,
                            prob,
                            {"ts": ts, "season": args.season_id, "extra": {}},
                        )
                    )
        store.bulk_write(records)

    out_dir = Path("reports/sims")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.season_id}_{args.home}_{args.away}.json"
    sim.save(result, out_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
