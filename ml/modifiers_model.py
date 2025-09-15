"""
@file: modifiers_model.py
@description: Динамические модификаторы λ и калибровочный слой.
@dependencies: logger, config, numpy, pandas, joblib, sklearn
@created: 2025-08-23
"""
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from config import get_settings
from logger import logger


class PredictionModifier:
    """Сервис для применения динамических модификаторов."""

    def __init__(self):
        self.settings = get_settings()
        self.weather_modifiers = {
            "clear": 1.0,
            "sunny": 1.0,
            "partly cloudy": 1.0,
            "cloudy": 0.98,
            "overcast": 0.98,
            "mist": 0.97,
            "fog": 0.85,
            "light rain": 0.92,
            "rain": 0.88,
            "heavy rain": 0.80,
            "light snow": 0.85,
            "snow": 0.75,
            "heavy snow": 0.65,
        }
        self.pitch_modifiers = {
            "excellent": 1.05,
            "good": 1.0,
            "average": 0.98,
            "poor": 0.95,
            "very poor": 0.90,
        }

    def apply_lineup_uncertainty(
        self,
        lambda_home: float,
        lambda_away: float,
        core_avail_home: float,
        core_avail_away: float,
    ) -> tuple[float, float]:
        try:
            availability_threshold = 0.7
            factor_home = 0.98 if core_avail_home >= availability_threshold else 0.95
            factor_away = 0.98 if core_avail_away >= availability_threshold else 0.95
            modified_lambda_home = lambda_home * factor_home
            modified_lambda_away = lambda_away * factor_away
            logger.debug(
                "Применен модификатор неопределенности состава: дома %s (%.2f), в гостях %s (%.2f)",
                factor_home,
                core_avail_home,
                factor_away,
                core_avail_away,
            )
            return modified_lambda_home, modified_lambda_away
        except Exception as e:
            logger.error("Ошибка при применении модификатора неопределенности состава: %s", e)
            return lambda_home, lambda_away

    def apply_weather_field(
        self,
        lambda_home: float,
        lambda_away: float,
        weather: dict[str, Any],
        pitch_type: str,
    ) -> tuple[float, float]:
        try:
            wind_mps = weather.get("wind_mps", 0) if weather else 0
            rain_prob = weather.get("rain_prob", 0) if weather else 0
            wind_factor = 0.98 if wind_mps >= 8 else 1.0
            rain_factor = 0.98 if rain_prob >= 0.6 else 1.0
            factor = wind_factor * rain_factor
            if pitch_type and pitch_type.lower() == "artificial":
                factor *= 1.01
            modified_lambda_home = lambda_home * factor
            modified_lambda_away = lambda_away * factor
            logger.debug(
                "Применен модификатор погоды и поля: ветер %s, дождь %s, поле %s, фактор %s",
                wind_mps,
                rain_prob,
                pitch_type,
                factor,
            )
            return modified_lambda_home, modified_lambda_away
        except Exception as e:
            logger.error("Ошибка при применении модификатора погоды и поля: %s", e)
            return lambda_home, lambda_away

    async def apply_dynamic_modifiers(
        self,
        base_lambda_home: float,
        base_lambda_away: float,
        match_context: dict[str, Any],
    ) -> tuple[float, float]:
        try:
            logger.info("Начало применения динамических модификаторов...")
            modified_lambda_home = base_lambda_home
            modified_lambda_away = base_lambda_away
            importance_factor = match_context.get("importance_factor", 1.0)
            home_team_fatigue = match_context.get("home_team_fatigue", 0)
            away_team_fatigue = match_context.get("away_team_fatigue", 0)
            home_missing_key_players = match_context.get("home_missing_key_players", [])
            away_missing_key_players = match_context.get("away_missing_key_players", [])
            home_finishing = match_context.get("home_team_finishing", 0)
            away_finishing = match_context.get("away_team_finishing", 0)
            tactical_advantage = match_context.get("tactical_advantage", 0)
            weather_and_pitch = match_context.get("weather_and_pitch", {})
            weather_type = weather_and_pitch.get("weather_type")
            pitch_type = weather_and_pitch.get("pitch_type")
            modified_lambda_home *= importance_factor
            modified_lambda_away *= importance_factor
            if home_team_fatigue > 0:
                fatigue_multiplier_home = max(0.5, 1 - (home_team_fatigue * 0.05))
                modified_lambda_home *= fatigue_multiplier_home
            if away_team_fatigue > 0:
                fatigue_multiplier_away = max(0.5, 1 - (away_team_fatigue * 0.07))
                modified_lambda_away *= fatigue_multiplier_away
            if home_missing_key_players:
                reduction_factor = self._calculate_player_impact(home_missing_key_players)
                modified_lambda_home *= 1 - reduction_factor
            if away_missing_key_players:
                reduction_factor = self._calculate_player_impact(away_missing_key_players)
                modified_lambda_away *= 1 - reduction_factor
            if home_finishing != 0:
                modified_lambda_home *= 1 + (home_finishing * 0.05)
            if away_finishing != 0:
                modified_lambda_away *= 1 + (away_finishing * 0.05)
            if tactical_advantage != 0:
                tactical_multiplier = 1 + (abs(tactical_advantage) * 0.1)
                if tactical_advantage > 0:
                    modified_lambda_home *= tactical_multiplier
                else:
                    modified_lambda_away *= tactical_multiplier
            if weather_type:
                weather_mod = self.weather_modifiers.get(weather_type, 1.0)
                modified_lambda_home *= weather_mod
                modified_lambda_away *= weather_mod
            if pitch_type:
                pitch_mod = self.pitch_modifiers.get(pitch_type, 1.0)
                modified_lambda_home *= pitch_mod
                modified_lambda_away *= pitch_mod
            logger.info(
                "Динамические модификаторы применены: домашняя λ=%s, гостевая λ=%s",
                modified_lambda_home,
                modified_lambda_away,
            )
            return modified_lambda_home, modified_lambda_away
        except Exception as e:
            logger.error("Ошибка при применении модификаторов: %s", e, exc_info=True)
            return base_lambda_home, base_lambda_away

    def _calculate_player_impact(self, missing_players: list[dict[str, Any]]) -> float:
        try:
            if not missing_players:
                return 0.0
            total_impact = 0
            for player in missing_players:
                impact = player.get("xg_contribution")
                if impact is None or not isinstance(impact, int | float):
                    impact = 0.1
                total_impact += impact
            impact_coefficient = min(0.3, total_impact * 0.1)
            logger.debug(
                "Рассчитано влияние отсутствующих игроков: %s",
                impact_coefficient,
            )
            return impact_coefficient
        except Exception as e:
            logger.error("Ошибка при расчете влияния игроков: %s", e)
            return 0.0


class CalibrationLayer:
    """log(lambda') = log(lambda_base) + beta^T * features"""

    def __init__(self, feature_names: list[str] | None = None, alpha: float = 1.0):
        self.feature_names = feature_names or []
        self.model_home = Ridge(alpha=alpha)
        self.model_away = Ridge(alpha=alpha)

    def fit(
        self,
        X: pd.DataFrame,
        y_home: np.ndarray,
        y_away: np.ndarray,
        lam_home_base: np.ndarray,
        lam_away_base: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "CalibrationLayer":
        X = X[self.feature_names] if self.feature_names else X
        t_home = np.log(np.clip(y_home, 1e-6, None)) - np.log(np.clip(lam_home_base, 1e-6, None))
        t_away = np.log(np.clip(y_away, 1e-6, None)) - np.log(np.clip(lam_away_base, 1e-6, None))
        self.model_home.fit(X, t_home, sample_weight=sample_weight)
        self.model_away.fit(X, t_away, sample_weight=sample_weight)
        return self

    def transform(
        self,
        lam_home_base: np.ndarray,
        lam_away_base: np.ndarray,
        X: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray]:
        X = X[self.feature_names] if self.feature_names else X
        delta_home = self.model_home.predict(X)
        delta_away = self.model_away.predict(X)
        lam_home = np.exp(np.log(np.clip(lam_home_base, 1e-6, None)) + delta_home)
        lam_away = np.exp(np.log(np.clip(lam_away_base, 1e-6, None)) + delta_away)
        return lam_home, lam_away

    def save(self, path: str) -> None:
        joblib.dump(
            {
                "feature_names": self.feature_names,
                "model_home": self.model_home,
                "model_away": self.model_away,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "CalibrationLayer":
        obj = joblib.load(path)
        inst = cls(feature_names=obj.get("feature_names"))
        inst.model_home = obj["model_home"]
        inst.model_away = obj["model_away"]
        return inst


prediction_modifier = PredictionModifier()
