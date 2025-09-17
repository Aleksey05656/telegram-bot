"""
@file: prediction_pipeline.py
@description: Minimal prediction pipeline skeleton for production wiring.
@dependencies: pandas (optional), numpy (optional), joblib, Preprocessor, ModelRegistry
@created: 2025-09-12
"""
import os
from typing import Any, Protocol

import numpy as np

try:  # optional import for constrained environments
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = Any  # type: ignore

from app.config import get_settings
from app.data_processor import build_features, to_model_matrix, validate_input
from logger import logger
from metrics import ece_poisson, logloss_poisson, record_metrics


class Preprocessor(Protocol):
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


class ModelRegistry(Protocol):
    def load(self, name: str):
        ...


class _DummyModel:
    def predict(self, X):
        try:
            import numpy as np

            return np.ones(len(X), dtype=float)
        except Exception:  # no numpy available
            return [1.0 for _ in range(len(X))]


class PredictionPipeline:
    """
    Basic flow:
      df -> preprocessor.transform -> X
      model = registry.load("current") or _DummyModel()
      return model.predict_proba(X) or model.predict(X)
    """

    def __init__(self, preprocessor: Preprocessor, model_registry: ModelRegistry | None = None):
        self._pre = preprocessor
        self._reg = model_registry

    @staticmethod
    def _prepare_modifier_features(features: pd.DataFrame) -> pd.DataFrame:
        feature_cols = ["rest_days"] + sorted(
            col for col in features.columns if col.startswith("rolling_xg_")
        )
        if not feature_cols:
            return pd.DataFrame({"bias": [1.0]})

        home = (
            features.loc[features["is_home"] == 1, ["match_id", *feature_cols]]
            .rename(columns={col: f"{col}_home" for col in feature_cols})
            .copy()
        )
        away = (
            features.loc[features["is_home"] == 0, ["match_id", *feature_cols]]
            .rename(columns={col: f"{col}_away" for col in feature_cols})
            .copy()
        )
        combined = home.merge(away, on="match_id", how="inner")
        combined = combined.sort_values("match_id").reset_index(drop=True)
        X = combined.drop(columns="match_id")
        X.insert(0, "bias", 1.0)
        return X

    def _load_models(self):
        if self._reg is None:
            return _DummyModel(), _DummyModel()
        try:
            return self._reg.load("glm_home"), self._reg.load("glm_away")
        except Exception:
            try:
                base_dir = getattr(self._reg, "base_dir", None)
                if base_dir is not None:
                    for sub in base_dir.iterdir():
                        m_home = self._reg.load("glm_home", season=sub.name)
                        m_away = self._reg.load("glm_away", season=sub.name)
                        return m_home, m_away
            except Exception:
                try:
                    m = self._reg.load("current")
                    return m, m
                except Exception:
                    return _DummyModel(), _DummyModel()

    def predict_proba(self, df: pd.DataFrame):
        validated = validate_input(df)
        processed = self._pre.transform(validated.copy()) if self._pre is not None else validated
        features = build_features(processed)
        X_home, _, X_away, _ = to_model_matrix(features)
        modifier_features = self._prepare_modifier_features(features)

        model_home, model_away = self._load_models()
        if hasattr(model_home, "predict_proba") and hasattr(model_away, "predict_proba"):
            ph = model_home.predict_proba(X_home)
            pa = model_away.predict_proba(X_away)
            pred_home = ph[:, 0] if ph.ndim == 2 else ph
            pred_away = pa[:, 1] if pa.ndim == 2 else pa
        else:
            pred_home = model_home.predict(X_home)
            pred_away = model_away.predict(X_away)

        if hasattr(np, "asarray"):
            pred_home = np.asarray(pred_home, dtype=float)
            pred_away = np.asarray(pred_away, dtype=float)
            pred_home_base = pred_home.copy()
            pred_away_base = pred_away.copy()
        else:  # pragma: no cover - numpy unavailable fallback
            pred_home = list(pred_home)
            pred_away = list(pred_away)
            pred_home_base = list(pred_home)
            pred_away_base = list(pred_away)
        
        modifiers_applied = False
        if self._reg is not None:
            try:
                mod = self._reg.load("modifiers_model")
                pred_home, pred_away = mod.transform(pred_home, pred_away, modifier_features)
                modifiers_applied = True
                logger.info("modifiers_applied=1")
            except Exception:
                logger.debug("modifiers_applied=0")

        if {
            "goals_home",
            "goals_away",
        }.issubset(getattr(df, "columns", [])):
            y_true = df["goals_home"].tolist() + df["goals_away"].tolist()
            base_pred = list(pred_home_base) + list(pred_away_base)
            final_pred = list(pred_home) + list(pred_away)
            settings = get_settings()
            tags = {
                "service": settings.app_name,
                "env": settings.env,
                "version": settings.git_sha,
                "season": os.getenv("SEASON_ID", "default"),
                "modifiers_applied": "false",
            }
            base_logloss = logloss_poisson(y_true, base_pred)
            base_ece = ece_poisson(y_true, base_pred)
            record_metrics("glm_base_logloss", base_logloss, tags)
            record_metrics("glm_base_ece", base_ece, tags)
            tags_final = dict(tags)
            tags_final["modifiers_applied"] = "true" if modifiers_applied else "false"
            final_logloss = logloss_poisson(y_true, final_pred)
            final_ece = ece_poisson(y_true, final_pred)
            record_metrics("glm_mod_final_logloss", final_logloss, tags_final)
            record_metrics("glm_mod_final_ece", final_ece, tags_final)

        settings = get_settings()
        if settings.sim_n <= 0:
            logger.info("sim_skipped=true")
        else:
            from datetime import datetime
            from pathlib import Path

            from services.simulator import render_markdown, simulate_markets
            from storage.persistence import SQLitePredictionsStore

            lam_home = float(pred_home[0])
            lam_away = float(pred_away[0])
            markets = simulate_markets(lam_home, lam_away, settings.sim_rho, settings.sim_n)

            season = str(df.get("season", [os.getenv("SEASON_ID", "default")])[0])
            home_team = str(df.get("home", ["home"])[0])
            away_team = str(df.get("away", ["away"])[0])
            date_val = df.get("date", [datetime.utcnow()])[0]
            date_iso = (
                date_val.isoformat()
                if hasattr(date_val, "isoformat")
                else datetime.utcnow().isoformat()
            )
            match_id = f"{season}:{home_team}_vs_{away_team}:{date_iso}"
            ts_iso = datetime.utcnow().isoformat()

            store = SQLitePredictionsStore(
                os.getenv("PREDICTIONS_DB_URL", "var/predictions.sqlite")
            )
            records = []
            for sel, prob in markets.get("1x2", {}).items():
                records.append((match_id, "1x2", sel, prob, {"ts": ts_iso, "season": season}))
            for thr, sp in markets.get("totals", {}).items():
                for sel, prob in sp.items():
                    records.append(
                        (match_id, f"totals_{thr}", sel, prob, {"ts": ts_iso, "season": season})
                    )
            for sel, prob in markets.get("btts", {}).items():
                records.append((match_id, "btts", sel, prob, {"ts": ts_iso, "season": season}))
            for score, prob in markets.get("cs", {}).items():
                records.append((match_id, "cs", score, prob, {"ts": ts_iso, "season": season}))
            store.bulk_write(records)

            report_path = Path("reports/metrics") / f"SIM_{season}_{home_team}_vs_{away_team}.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                render_markdown(markets, settings.sim_n, settings.sim_rho), encoding="utf-8"
            )

            tags_sim = {
                "service": settings.app_name,
                "env": settings.env,
                "version": settings.git_sha,
                "season": season,
                "n_sims": str(settings.sim_n),
                "rho": str(settings.sim_rho),
                "modifiers_applied": "true" if modifiers_applied else "false",
            }
            record_metrics("sim_entropy_1x2", markets["entropy"]["1x2"], tags_sim)
            record_metrics("sim_entropy_totals", markets["entropy"]["totals"], tags_sim)
            record_metrics("sim_entropy_cs", markets["entropy"]["cs"], tags_sim)

        try:
            return np.column_stack([pred_home, pred_away])
        except Exception:  # pragma: no cover
            return [[h, a] for h, a in zip(pred_home, pred_away, strict=False)]
