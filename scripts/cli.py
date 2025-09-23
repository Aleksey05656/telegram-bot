"""
@file: cli.py
@description: Unified CLI for retrain orchestration (run, schedule, status).
@dependencies: click, pandas, numpy, LocalModelRegistry, metrics
@created: 2025-09-16
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data_processor import build_features, to_model_matrix, validate_input
from app.ml.model_registry import LocalModelRegistry
from metrics import ece_poisson, logloss_poisson
from ml.modifiers_model import ModifiersModel
from scripts import train_glm
from scripts.train_modifiers import _prepare_modifier_features
from workers import runtime_scheduler
from workers.retrain_scheduler import schedule_retrain


def _candidate_training_paths(season_id: str) -> list[Path]:
    base = str(season_id)
    candidates: list[Path] = []
    for prefix in (Path("data"), Path("database")):
        candidates.append(prefix / "training" / f"{base}.parquet")
        candidates.append(prefix / "training" / f"{base}.csv")
        candidates.append(prefix / f"{base}.parquet")
        candidates.append(prefix / f"{base}.csv")
    return candidates


def _generate_stub_training_data() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=8, freq="7D")
    return pd.DataFrame(
        {
            "home_team": ["A", "B", "C", "A", "D", "C", "B", "A"],
            "away_team": ["B", "C", "A", "D", "A", "B", "D", "C"],
            "date": dates,
            "xG_home": [1.2, 0.9, 1.4, 1.0, 1.1, 1.3, 0.8, 1.2],
            "xG_away": [0.7, 1.1, 0.6, 1.2, 0.9, 0.8, 1.0, 0.7],
            "goals_home": [2, 1, 3, 1, 2, 2, 0, 1],
            "goals_away": [0, 1, 1, 2, 1, 1, 1, 0],
        }
    )


def _load_training_frame(season_id: str) -> tuple[pd.DataFrame, str]:
    for path in _candidate_training_paths(season_id):
        if not path.exists():
            continue
        if path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df, str(path)
    df = _generate_stub_training_data()
    return df, "synthetic"


def _ensure_artifact_dir(season_id: str) -> Path:
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    registry_root = Path(os.getenv("MODEL_REGISTRY_PATH", str(data_root / "artifacts")))
    path = registry_root / season_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_model_info(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_modifier_training_data(
    validated: pd.DataFrame,
    features: pd.DataFrame,
    lambda_home: np.ndarray,
    lambda_away: np.ndarray,
) -> pd.DataFrame:
    home_features = (
        features.loc[features["is_home"] == 1, "match_id"].astype(int).reset_index(drop=True)
    )
    away_features = (
        features.loc[features["is_home"] == 0, "match_id"].astype(int).reset_index(drop=True)
    )
    base_home = pd.DataFrame({"match_id": home_features, "lambda_home": lambda_home})
    base_away = pd.DataFrame({"match_id": away_features, "lambda_away": lambda_away})
    base = base_home.merge(base_away, on="match_id", how="inner")

    ordered = validated.sort_values("date", kind="stable").reset_index(drop=True).copy()
    ordered["match_id"] = np.arange(len(ordered), dtype=int)
    merged = ordered.merge(base, on="match_id", how="left")
    merged["target_home"] = merged["goals_home"].astype(float).clip(lower=1e-3)
    merged["target_away"] = merged["goals_away"].astype(float).clip(lower=1e-3)
    return merged


def _train_modifiers_and_metrics(
    season_id: str,
    validated: pd.DataFrame,
    features: pd.DataFrame,
    lambda_home: np.ndarray,
    lambda_away: np.ndarray,
    artifact_dir: Path,
) -> dict[str, Any]:
    modifier_df = _prepare_modifier_training_data(validated, features, lambda_home, lambda_away)
    X_mod, match_ids = _prepare_modifier_features(features)
    targets = modifier_df.set_index("match_id").loc[match_ids].reset_index(drop=True)

    lambda_home_base = targets["lambda_home"].to_numpy(dtype=float)
    lambda_away_base = targets["lambda_away"].to_numpy(dtype=float)

    y_home = np.log(targets["target_home"].to_numpy(dtype=float)) - np.log(lambda_home_base)
    y_away = np.log(targets["target_away"].to_numpy(dtype=float)) - np.log(lambda_away_base)

    modifiers = ModifiersModel(alpha=1.0).fit(X_mod, y_home, y_away)
    modifiers_path = artifact_dir / "modifiers_model.pkl"
    modifiers.save(str(modifiers_path))

    final_home, final_away = modifiers.transform(lambda_home_base, lambda_away_base, X_mod)
    y_true = targets["goals_home"].astype(int).tolist() + targets["goals_away"].astype(int).tolist()
    base = lambda_home_base.tolist() + lambda_away_base.tolist()
    final = final_home.tolist() + final_away.tolist()

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

    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    reports_root = Path(os.getenv("REPORTS_DIR", str(data_root / "reports")))
    report_dir = reports_root / "metrics"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"MODIFIERS_{season_id}.md"
    report_path.write_text(table, encoding="utf-8")

    return {
        "modifiers_path": str(modifiers_path),
        "report_path": str(report_path),
        "metrics": {
            "logloss_base": base_logloss,
            "logloss_final": final_logloss,
            "logloss_delta": delta_logloss,
            "ece_base": base_ece,
            "ece_final": final_ece,
            "ece_delta": delta_ece,
        },
        "table": table,
    }


def _update_run_summary(payload: dict[str, Any]) -> None:
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    reports_root = Path(os.getenv("REPORTS_DIR", str(data_root / "reports")))
    summary_path = reports_root / "RUN_SUMMARY.md"
    lines = [
        "",
        "## CLI retrain",
        f"- Season: {payload['season']}",
        f"- Data source: {payload['data_source']}",
        (
            "- GLM artifacts: "
            f"{payload['artifacts']['glm_home']}, {payload['artifacts']['glm_away']}"
        ),
        f"- Model info: {payload['artifacts']['model_info']}",
    ]
    modifiers = payload.get("modifiers")
    if modifiers:
        lines.append(f"- Modifiers: {modifiers['modifiers_path']}")
        metrics = modifiers["metrics"]
        lines.append(
            "- Metrics: "
            f"logloss Δ {metrics['logloss_delta']:.4f}, ece Δ {metrics['ece_delta']:.4f}"
        )
        lines.append(f"- Metrics report: {modifiers['report_path']}")
    else:
        lines.append("- Modifiers: skipped")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _run_retrain(season_id: str, alpha: float, l2: float, with_modifiers: bool) -> dict[str, Any]:
    df_raw, data_source = _load_training_frame(season_id)
    validated = validate_input(df_raw)
    artifact_dir = _ensure_artifact_dir(season_id)

    model_home, model_away, info = train_glm.train_models(df_raw, alpha, l2)
    registry = LocalModelRegistry()
    glm_home_path = Path(registry.save(model_home, "glm_home", season=season_id))
    glm_away_path = Path(registry.save(model_away, "glm_away", season=season_id))

    info_payload = dict(info)
    info_payload["season_id"] = season_id
    info_payload["data_source"] = data_source
    info_payload["artifacts"] = {
        "glm_home": str(glm_home_path),
        "glm_away": str(glm_away_path),
    }
    info_path = artifact_dir / "model_info.json"
    _save_model_info(info_path, info_payload)

    result: dict[str, Any] = {
        "season": season_id,
        "data_source": data_source,
        "artifacts": {
            "glm_home": str(glm_home_path),
            "glm_away": str(glm_away_path),
            "model_info": str(info_path),
        },
        "metrics": {
            "score_home": info.get("score_home"),
            "score_away": info.get("score_away"),
            "n_samples": info.get("n_samples"),
        },
    }

    modifiers_result: dict[str, Any] | None = None
    if with_modifiers:
        features = build_features(validated)
        X_home, _, X_away, _ = to_model_matrix(features)
        lambda_home = np.exp(model_home.predict(X_home))
        lambda_away = np.exp(model_away.predict(X_away))
        modifiers_result = _train_modifiers_and_metrics(
            season_id,
            validated,
            features,
            lambda_home,
            lambda_away,
            artifact_dir,
        )
        result["modifiers"] = modifiers_result

    _update_run_summary(
        {
            "season": season_id,
            "data_source": data_source,
            "artifacts": result["artifacts"],
            "modifiers": modifiers_result,
        }
    )
    return result


@click.group()
def cli() -> None:
    """Utility commands for training orchestration."""


@cli.group()
def retrain() -> None:
    """Retrain related operations."""


@retrain.command()
@click.option("--season-id", default="default", show_default=True, help="Season identifier.")
@click.option("--alpha", default=0.005, type=float, show_default=True, help="Recency decay.")
@click.option("--l2", default=1.0, type=float, show_default=True, help="L2 regularization for GLM.")
@click.option("--with-modifiers", is_flag=True, help="Train modifiers and validate metrics.")
def run(season_id: str, alpha: float, l2: float, with_modifiers: bool) -> None:
    """Run GLM training pipeline and optional modifiers validation."""
    try:
        result = _run_retrain(season_id, alpha, l2, with_modifiers)
    except Exception as exc:  # pragma: no cover - error path
        click.echo(f"[error] retrain failed: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(
        " | ".join(
            [
                f"season={result['season']}",
                f"glm_home={result['artifacts']['glm_home']}",
                f"glm_away={result['artifacts']['glm_away']}",
            ]
        )
    )
    modifiers = result.get("modifiers")
    if modifiers:
        metrics = modifiers["metrics"]
        click.echo(
            " | ".join(
                [
                    f"modifiers={modifiers['modifiers_path']}",
                    f"logloss_delta={metrics['logloss_delta']:.4f}",
                    f"ece_delta={metrics['ece_delta']:.4f}",
                ]
            )
        )
    else:
        click.echo("modifiers=skipped")


@retrain.command()
@click.option("--cron", default=None, help="Cron expression for retrain job.")
def schedule(cron: str | None) -> None:
    """Register retrain job in runtime scheduler."""
    try:
        effective = schedule_retrain(runtime_scheduler.register, cron_expr=cron or None)
    except Exception as exc:  # pragma: no cover - error path
        click.echo(f"[error] failed to schedule retrain: {exc}", err=True)
        raise SystemExit(1) from exc
    click.echo(f"scheduled cron={effective}")


@retrain.command()
def status() -> None:
    """Print registered jobs and aggregated counter."""
    jobs = runtime_scheduler.list_jobs()
    total = runtime_scheduler.jobs_registered_total()
    click.echo(
        json.dumps({"jobs": jobs, "jobs_registered_total": total}, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    cli()
