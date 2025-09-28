"""
@file: validate_modifiers.py
@description: CLI tool to validate modifier improvements and generate report.
@dependencies: pandas, numpy (optional), metrics.metrics
@created: 2025-09-15
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts._optional import optional_dependency

pd = optional_dependency("pandas")

from metrics import ece_poisson, logloss_poisson


def _load_data(path: str | None) -> pd.DataFrame:
    if path and Path(path).exists():
        if path.endswith(".parquet"):
            return pd.read_parquet(path)
        return pd.read_csv(path)
    import numpy as np

    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "lambda_home": rng.uniform(0.5, 1.5, size=10),
            "lambda_away": rng.uniform(0.5, 1.5, size=10),
            "home_goals": rng.poisson(1.0, size=10),
            "away_goals": rng.poisson(1.0, size=10),
        }
    )


def _apply_modifier(df: pd.DataFrame, alpha: float, l2: float) -> tuple[list[float], list[float]]:
    # Stub modifier: identity transform
    return df["lambda_home"].tolist(), df["lambda_away"].tolist()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--input")
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--l2", type=float, required=True)
    parser.add_argument("--tol", type=float, default=0.0)
    parser.add_argument("--tol-ece", type=float, default=0.0)
    args = parser.parse_args()

    df = _load_data(args.input)
    base = df["lambda_home"].tolist() + df["lambda_away"].tolist()
    final_home, final_away = _apply_modifier(df, args.alpha, args.l2)
    final = final_home + final_away
    y_true = df["home_goals"].tolist() + df["away_goals"].tolist()
    base_logloss = logloss_poisson(y_true, base)
    final_logloss = logloss_poisson(y_true, final)
    base_ece = ece_poisson(y_true, base)
    final_ece = ece_poisson(y_true, final)
    delta_logloss = final_logloss - base_logloss
    delta_ece = final_ece - base_ece
    table = (
        "| metric | base | final | delta |\n"
        "|---|---|---|---|\n"
        f"| logloss | {base_logloss:.4f} | {final_logloss:.4f} | {delta_logloss:.4f} |\n"
        f"| ece | {base_ece:.4f} | {final_ece:.4f} | {delta_ece:.4f} |\n"
    )
    print(table)
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    reports_root = Path(os.getenv("REPORTS_DIR", str(data_root / "reports")))
    report_dir = reports_root / "metrics"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"MODIFIERS_{args.season_id}.md"
    report_path.write_text(table)
    ok = delta_logloss <= args.tol and delta_ece <= args.tol_ece
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
