# services/recommendation_engine.py
"""Сервис для генерации комплексных прогнозов и рекомендаций."""
import asyncio
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import numpy as np
from logger import logger
from config import get_settings, CONFIDENCE
# Импорт моделей
from ml.models.poisson_model import poisson_model
from ml.models.poisson_regression_model import poisson_regression_model
# Импорт нового модуля Bivariate Poisson
try:
    from ml.models.bivariate_poisson import BivariatePoisson, estimate_rho
    HAS_BIVARIATE_POISSON = True
except ImportError:
    HAS_BIVARIATE_POISSON = False
    logger.warning("Bivariate Poisson модель не доступна")
# Импорт сервисов
from services.sportmonks_client import sportmonks_client
from services.prediction_modifier import prediction_modifier
from services.data_processor import data_processor
# Импорт модуля логирования в БД
try:
    from database.db_logging import log_prediction  # async
except Exception:  # pragma: no cover
    log_prediction = None

# === Confidence helpers ===
def _confidence_from_margin(probabilities: Dict[str, float]) -> float:
    """
    Базовая уверенность как разница между топ-1 и топ-2 исходом.
    Ожидаются ключи: 'home_win', 'draw', 'away_win'.
    """
    try:
        vals = [
            float(probabilities.get("home_win", 0.0)),
            float(probabilities.get("draw", 0.0)),
            float(probabilities.get("away_win", 0.0)),
        ]
        vals.sort(reverse=True)
        margin = (vals[0] - vals[1]) if len(vals) >= 2 else 0.0
        return float(max(0.0, min(1.0, margin)))
    except Exception:
        return 0.0

def _calc_missing_ratio(team_stats: Dict[str, Any]) -> float:
    """
    Оцениваем долю пропусков по ключевым фичам с обеих сторон.
    Ожидаем структуру: {'home': {...}, 'away': {...}}.
    """
    try:
        home = (team_stats or {}).get("home", {}) or {}
        away = (team_stats or {}).get("away", {}) or {}
        keys = ["xg", "shots", "ppda", "passes", "pass_accuracy"]
        vals = [home.get(k) for k in keys] + [away.get(k) for k in keys]
        miss = sum(1 for v in vals if v is None)
        return miss / max(1, len(vals))
    except Exception:
        return 0.0

def _penalize_confidence(base: float, missing_ratio: float, freshness_minutes: float = 0.0) -> float:
    """
    Применяем штрафы за пропуски и устаревшие данные.
    Параметры берём из config.CONFIDENCE.
    """
    try:
        c = float(base)
        c *= (1 - float(CONFIDENCE.get("missing_penalty_alpha", 0.2)) * float(missing_ratio))
        c *= max(
            0.0,
            1 - float(CONFIDENCE.get("freshness_penalty_alpha", 0.15)) * (float(freshness_minutes) / 60.0),
        )
        return float(max(0.0, min(1.0, c)))
    except Exception:
        return base
class RiskLevel(Enum):
    """Уровень риска ставки."""
    LOW = "низкий"
    MEDIUM = "средний"
    HIGH = "высокий"
@dataclass
class BettingRecommendation:
    """Рекомендация по ставке."""
    market: str
    selection: str
    confidence: float
    risk_level: RiskLevel
    reasoning: str
class RecommendationEngine:
    """Движок для генерации рекомендаций."""
    def __init__(self):
        """Инициализация Recommendation Engine."""
        self.settings = get_settings()
        self.poisson_model = poisson_model
        self.regression_model = poisson_regression_model
        # Инициализация сервисов
        self.data_processor = data_processor
        self.modifier = prediction_modifier
        self.home_advantage_factor = 1.15 # Базовое преимущество домашней команды
        # Инициализация клиента
        self.sportmonks_client = sportmonks_client
        logger.info("RecommendationEngine инициализирован")
    def compute_confidence_from_margin(self, probs: Dict[str, float]) -> float:
        """Вычисление уверенности на основе маржи вероятностей.
        Args:
            probs (Dict[str, float]): Вероятности исходов
        Returns:
            float: Уровень уверенности (0-1)
        """
        try:
            # Максимальная вероятность
            max_prob = max(probs.get("probability_home_win", 0),
                           probs.get("probability_draw", 0),
                           probs.get("probability_away_win", 0))
            # Минимальная вероятность среди основных исходов
            min_prob = min(probs.get("probability_home_win", 1),
                           probs.get("probability_draw", 1),
                           probs.get("probability_away_win", 1))
            # Маржа как разница
            margin = max_prob - min_prob
            # Нормализуем уверенность (пример)
            confidence = max(0.0, min(1.0, margin * 2)) # Пример нормализации
            return confidence
        except Exception as e:
            logger.error(f"Ошибка при вычислении уверенности: {e}")
            return 0.0
    def penalize_confidence(self, confidence: float, missing_ratio: float, data_freshness_minutes: float) -> float:
        """Применение штрафа к уверенности на основе пропусков и свежести данных.
        Args:
            confidence (float): Исходная уверенность (0-1).
            missing_ratio (float): Доля пропущенных значений (0-1).
            data_freshness_minutes (float): Свежесть данных в минутах.
        Returns:
            float: Скорректированная уверенность (0-1).
        """
        try:
            # Получаем параметры штрафов из конфигурации
            missing_penalty_alpha = getattr(self.settings, 'CONFIDENCE', {}).get('missing_penalty_alpha', 0.2)
            freshness_penalty_alpha = getattr(self.settings, 'CONFIDENCE', {}).get('freshness_penalty_alpha', 0.15)
            # Применяем штраф за пропуски
            missing_penalty = 1.0 - (missing_ratio * missing_penalty_alpha)
            # Применяем штраф за свежесть (например, после 60 минут начинаем штрафовать)
            freshness_base_minutes = getattr(self.settings, 'CONFIDENCE', {}).get('freshness_base_minutes', 60)
            if data_freshness_minutes > freshness_base_minutes:
                extra_minutes = data_freshness_minutes - freshness_base_minutes
                freshness_penalty = 1.0 - ((extra_minutes / 60.0) * freshness_penalty_alpha)
                freshness_penalty = max(0.5, freshness_penalty) # Минимум 50%
            else:
                freshness_penalty = 1.0
            # Комбинируем штрафы
            final_confidence = confidence * missing_penalty * freshness_penalty
            final_confidence = max(0.0, min(1.0, final_confidence))
            return final_confidence
        except Exception as penalty_error:
            logger.error(f"Ошибка при применении штрафов к уверенности: {penalty_error}")
            return confidence
    async def generate_comprehensive_prediction(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация комплексного прогноза."""
        try:
            logger.info(f"Генерация комплексного прогноза для матча "
                        f"{match_data.get('home_team', 'Unknown')} - "
                        f"{match_data.get('away_team', 'Unknown')}")
            # Проверяем, устарела ли модель регрессии
            if self.regression_model.is_model_outdated():
                logger.warning("⚠️ Модель регрессии устарела. Прогноз может быть менее точным. "
                               "Рекомендуется запустить переобучение модели.")
            team_stats = match_data.get("team_stats", {})
            # 1. Расчет базовых λ
            base_lambdas = await self._calculate_base_lambdas(match_data, team_stats)
            # 2. Подготовка контекста матча
            match_context = await self._prepare_match_context(match_data, team_stats)
            # 3. Применение модификаторов
            modified_lambdas = await self.modifier.apply_dynamic_modifiers(
                base_lambdas[0], base_lambdas[1], match_context
            )
            # 4. Прогнозирование с использованием Poisson модели
            poisson_input = {
                "home_stats": match_data.get("home_stats", {}),
                "away_stats": match_data.get("away_stats", {}),
                "home_team": {"team_name": match_data.get("home_team")},
                "away_team": {"team_name": match_data.get("away_team")}
            }
            poisson_result = self.poisson_model.predict(poisson_input)
            # 5. Подготовка информации о пропущенных данных
            missing_ratio = _calc_missing_ratio(team_stats)
            missing_data_info = {
                "missing_ratio": missing_ratio,
                "data_freshness_minutes": 0.0  # В реальной реализации здесь будет расчет свежести данных
            }
            # 6. Генерация рекомендаций с учетом пропущенных данных
            recommendations = await self._generate_betting_recommendations(
                modified_lambdas[0], modified_lambdas[1],
                poisson_result, match_context, missing_data_info
            )
            # === Confidence: margin + penalties ===
            try:
                base_conf = _confidence_from_margin(poisson_result)
            except Exception:
                base_conf = 0.0
            confidence = _penalize_confidence(base_conf, missing_ratio, freshness_minutes=0.0)

            # 7. Агрегация результатов
            detailed_prediction = {
                "model": "ThreeLevelPoisson",
                "expected_goals": {
                    "home": round(modified_lambdas[0], 3),
                    "away": round(modified_lambdas[1], 3)
                },
                "probabilities": poisson_result,
                "best_recommendation": recommendations[0].market + ": " + recommendations[0].selection if recommendations else "Ставки не определены",
                "confidence": round(confidence, 3),
                "risk_level": recommendations[0].risk_level.value if recommendations else "высокий",
                "recommendations_count": len(recommendations),
                "generated_at": datetime.now().isoformat(),
                "missing_data_info": missing_data_info
            }
            # === Async DB log (best-effort) ===
            try:
                if log_prediction is not None:
                    match_id = (
                        match_data.get("id")
                        or match_data.get("fixture_id")
                        or match_data.get("match_id")
                        or 0
                    )
                    await log_prediction(
                        match_id=int(match_id),
                        features={"context": match_context},
                        probs=poisson_result,
                        lam_home=float(modified_lambdas[0]),
                        lam_away=float(modified_lambdas[1]),
                        confidence=float(confidence),
                    )
            except Exception as _e:
                logger.warning("Логирование прогноза не выполнено: %s", _e)
            logger.info("Комплексный прогноз сгенерирован")
            return detailed_prediction
        except Exception as e:
            logger.error(f"Ошибка при генерации комплексного прогноза: {e}", exc_info=True)
            return {
                "model": "ThreeLevelPoisson",
                "error": str(e),
                "expected_goals": {"home": 0, "away": 0},
                "probabilities": {},
                "best_recommendation": "Ставки не определены",
                "confidence": 0.0,
                "risk_level": "высокий",
                "recommendations_count": 0,
                "missing_data_info": {"missing_ratio": 0.0, "data_freshness_minutes": 0.0}
            }
    async def _calculate_base_lambdas(self, match_data: Dict, team_stats: Dict) -> Tuple[float, float]:
        """Расчет базовых параметров λ."""
        try:
            # В реальной реализации здесь будет расчет λ
            # Например, с использованием poisson_regression_model
            # Для примера возвращаем заглушку
            return 1.5, 1.2 # Значения по умолчанию
        except Exception as e:
            logger.error(f"Ошибка при расчете базовых λ: {e}")
            return 1.5, 1.2 # Значения по умолчанию
    async def _prepare_match_context(self, match_data: Dict, team_stats: Dict) -> Dict[str, Any]:
        """Подготовка контекста матча."""
        try:
            # В реальной реализации здесь будет подготовка контекста
            context = {
                "importance_factor": 1.0,
                "home_team_fatigue": 0,
                "away_team_fatigue": 0,
                "tactical_advantage": 0.0,
                "weather_and_pitch": {},
                "match_importance": 0.5,
                "style_mismatch": 0.0,
                "missing_ratio": 0.0 # Пример
            }
            return context
        except Exception as e:
            logger.error(f"Ошибка при подготовке контекста матча: {e}")
            return {}
    async def _generate_betting_recommendations(self, lambda_home: float, lambda_away: float,
                                                probabilities: Dict[str, float],
                                                match_context: Dict[str, Any],
                                                missing_data_info: Optional[Dict[str, Any]] = None) -> List[BettingRecommendation]:
        """Генерация рекомендаций по ставкам."""
        try:
            logger.debug("Генерация рекомендаций по ставкам")
            recommendations = []
            total_goals = lambda_home + lambda_away
            # 1. Рекомендация по результату матча
            home_win_prob = probabilities.get('probability_home_win', 0)
            draw_prob = probabilities.get('probability_draw', 0)
            away_win_prob = probabilities.get('probability_away_win', 0)
            # Вычисляем уверенность на основе маржи для результата матча
            result_probs = {
                "probability_home_win": home_win_prob,
                "probability_draw": draw_prob,
                "probability_away_win": away_win_prob
            }
            result_confidence = self.compute_confidence_from_margin(result_probs)
            # Простая логика рекомендаций
            if home_win_prob > 0.5 and home_win_prob > draw_prob and home_win_prob > away_win_prob:
                reasoning = "Высокая вероятность победы домашней команды"
                risk_level = RiskLevel.HIGH if result_confidence < 0.15 else RiskLevel.MEDIUM if result_confidence < 0.3 else RiskLevel.LOW
                recommendations.append(BettingRecommendation(
                    market="Результат матча",
                    selection="Победа домашней команды",
                    confidence=result_confidence,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            elif away_win_prob > 0.5 and away_win_prob > draw_prob and away_win_prob > home_win_prob:
                reasoning = "Высокая вероятность победы гостевой команды"
                risk_level = RiskLevel.HIGH if result_confidence < 0.15 else RiskLevel.MEDIUM if result_confidence < 0.3 else RiskLevel.LOW
                recommendations.append(BettingRecommendation(
                    market="Результат матча",
                    selection="Победа гостевой команды",
                    confidence=result_confidence,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            elif draw_prob > 0.4:
                reasoning = "Высокая вероятность ничьей"
                risk_level = RiskLevel.HIGH # Ничья обычно рискованнее
                recommendations.append(BettingRecommendation(
                    market="Результат матча",
                    selection="Ничья",
                    confidence=draw_prob,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            # 2. Рекомендация по тоталу
            over_prob = probabilities.get('probability_over_2_5', 0)
            under_prob = probabilities.get('probability_under_2_5', 0)
            # Вычисляем уверенность на основе маржи для тотала
            total_probs = {
                "probability_over_2_5": over_prob,
                "probability_under_2_5": under_prob
            }
            total_confidence = self.compute_confidence_from_margin(total_probs)
            if over_prob > 0.55:
                reasoning = f"Ожидаемый тотал {total_goals:.2f} голов, высокая вероятность Over"
                risk_level = RiskLevel.HIGH if total_confidence < 0.1 else RiskLevel.MEDIUM if total_confidence < 0.25 else RiskLevel.LOW
                recommendations.append(BettingRecommendation(
                    market="Тотал голов",
                    selection="Больше 2.5",
                    confidence=total_confidence,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            elif under_prob > 0.55:
                reasoning = f"Ожидаемый тотал {total_goals:.2f} голов, высокая вероятность Under"
                risk_level = RiskLevel.HIGH if total_confidence < 0.1 else RiskLevel.MEDIUM if total_confidence < 0.25 else RiskLevel.LOW
                recommendations.append(BettingRecommendation(
                    market="Тотал голов",
                    selection="Меньше 2.5",
                    confidence=total_confidence,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            # 3. Рекомендация по обе забьют (BTTS)
            btts_yes_prob = probabilities.get('probability_btts_yes', 0)
            btts_no_prob = probabilities.get('probability_btts_no', 0)
            # Вычисляем уверенность на основе маржи для BTTS
            btts_probs = {
                "probability_btts_yes": btts_yes_prob,
                "probability_btts_no": btts_no_prob
            }
            btts_confidence = self.compute_confidence_from_margin(btts_probs)
            if btts_yes_prob > 0.55:
                reasoning = "Высокая вероятность того, что обе команды забьют"
                risk_level = RiskLevel.HIGH if btts_confidence < 0.1 else RiskLevel.MEDIUM if btts_confidence < 0.25 else RiskLevel.LOW
                recommendations.append(BettingRecommendation(
                    market="Обе забьют",
                    selection="Да",
                    confidence=btts_confidence,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            elif btts_no_prob > 0.55:
                reasoning = "Высокая вероятность того, что одна из команд не забьет"
                risk_level = RiskLevel.HIGH if btts_confidence < 0.1 else RiskLevel.MEDIUM if btts_confidence < 0.25 else RiskLevel.LOW
                recommendations.append(BettingRecommendation(
                    market="Обе забьют",
                    selection="Нет",
                    confidence=btts_confidence,
                    risk_level=risk_level,
                    reasoning=reasoning
                ))
            # 4. Использование Bivariate Poisson (если включено)
            if self.settings.MODEL_FLAGS.get("enable_bivariate_poisson", False) and HAS_BIVARIATE_POISSON:
                try:
                    # Оценка rho на основе контекста матча
                    rho = estimate_rho(match_context)
                    # Создание Bivariate Poisson модели
                    bivar_model = BivariatePoisson(lambda_home, lambda_away, rho)
                    # Вычисление BTTS с корреляцией
                    btts_yes_corr, btts_no_corr = bivar_model.calculate_btts()
                    # Вычисление тоталов с корреляцией
                    over_corr, under_corr = bivar_model.calculate_totals()
                    logger.debug(f"Bivariate Poisson: BTTS(Да)={btts_yes_corr:.3f}, "
                                f"Over={over_corr:.3f}, ρ={rho:.2f}")
                    # Обновление рекомендаций с учетом корреляции
                    if btts_yes_corr > 0.55:
                        reasoning = f"Высокая вероятность 'Обе забьют' (с корреляцией)"
                        risk_level = RiskLevel.HIGH if btts_yes_corr < 0.6 else RiskLevel.MEDIUM if btts_yes_corr < 0.7 else RiskLevel.LOW
                        # Проверяем, есть ли уже такая рекомендация
                        btts_exists = any(r.market == "Обе забьют" and r.selection == "Да" for r in recommendations)
                        if not btts_exists:
                            # Вычисляем уверенность для скорректированного BTTS
                            btts_corr_probs = {"yes": btts_yes_corr, "no": btts_no_corr}
                            btts_corr_confidence = self.compute_confidence_from_margin(btts_corr_probs)
                            recommendations.append(BettingRecommendation(
                                market="Обе забьют",
                                selection="Да",
                                confidence=btts_corr_confidence,
                                risk_level=risk_level,
                                reasoning=reasoning
                            ))
                    if over_corr > 0.55:
                        reasoning = f"Высокая вероятность Over (с корреляцией)"
                        risk_level = RiskLevel.HIGH if over_corr < 0.6 else RiskLevel.MEDIUM if over_corr < 0.7 else RiskLevel.LOW
                        # Проверяем, есть ли уже такая рекомендация
                        over_exists = any(r.market == "Тотал голов" and r.selection == "Больше" for r in recommendations)
                        if not over_exists:
                            # Вычисляем уверенность для скорректированного тотала
                            total_corr_probs = {"over": over_corr, "under": under_corr}
                            total_corr_confidence = self.compute_confidence_from_margin(total_corr_probs)
                            recommendations.append(BettingRecommendation(
                                market="Тотал голов",
                                selection="Больше",
                                confidence=total_corr_confidence,
                                risk_level=risk_level,
                                reasoning=reasoning
                            ))
                except Exception as bivar_error:
                    logger.error(f"Ошибка при использовании Bivariate Poisson: {bivar_error}")
            # 5. Применение штрафа к уверенности на основе пропущенных данных
            if missing_data_info and recommendations:
                try:
                    # Получаем долю пропущенных данных
                    missing_ratio = missing_data_info.get("missing_ratio", 0.0)
                    # Получаем свежесть данных (в минутах)
                    data_freshness_minutes = missing_data_info.get("data_freshness_minutes", 0.0)
                    # Применяем штраф к уверенности каждой рекомендации
                    updated_recommendations = []
                    for rec in recommendations:
                        penalized_confidence = self.penalize_confidence(
                            rec.confidence, missing_ratio, data_freshness_minutes
                        )
                        # Создаем новую рекомендацию с обновленной уверенностью
                        updated_rec = BettingRecommendation(
                            market=rec.market,
                            selection=rec.selection,
                            confidence=penalized_confidence,
                            risk_level=rec.risk_level,
                            reasoning=rec.reasoning + f" (скорректировано: пропуски={missing_ratio:.1%})"
                        )
                        updated_recommendations.append(updated_rec)
                    recommendations = updated_recommendations
                    logger.debug(f"Применены штрафы к уверенности: пропуски={missing_ratio:.1%}, "
                                 f"свежесть={data_freshness_minutes:.1f}мин")
                except Exception as penalty_error:
                    logger.error(f"Ошибка при применении штрафов к уверенности: {penalty_error}")
                    # Возвращаем оригинальные рекомендации в случае ошибки
            return recommendations
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            return []
# Создание экземпляра движка рекомендаций
recommendation_engine = RecommendationEngine()

import numpy as np
from typing import Any, Dict
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

class ProbabilityCalibrator:
    def __init__(self, method: str = "platt"):
        self.method = method
        self.models: Dict[str, Any] = {}

    def fit(self, p_base: Dict[str, np.ndarray], y_true: np.ndarray) -> "ProbabilityCalibrator":
        for key, p in p_base.items():
            if self.method == "isotonic":
                m = IsotonicRegression(out_of_bounds="clip")
                self.models[key] = m.fit(p, (y_true==(key)).astype(float))
            else:
                m = LogisticRegression(max_iter=1000)
                self.models[key] = m.fit(p.reshape(-1,1), (y_true==(key)).astype(int))
        return self

    def predict(self, p_base: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        out = {}
        for key, p in p_base.items():
            m = self.models.get(key)
            if m is None:
                out[key] = p
            else:
                if hasattr(m, "predict_proba"):
                    out[key] = m.predict_proba(p.reshape(-1,1))[:,1]
                else:
                    out[key] = m.transform(p)
        # нормализация
        try:
            keys = list(out.keys())
            M = np.vstack([out[k] for k in keys]).T
            M = M / M.sum(axis=1, keepdims=True)
            for i,k in enumerate(keys): out[k] = M[:,i]
        except Exception:
            pass
        return out

class EnsembleCombiner:
    def __init__(self):
        self.model = LogisticRegression(max_iter=1000)
        self.keys: list[str] = []

    def fit(self, oof_preds: Dict[str, np.ndarray], y_true: np.ndarray) -> "EnsembleCombiner":
        self.keys = sorted(oof_preds.keys())
        X = np.vstack([oof_preds[k] for k in self.keys]).T
        self.model.fit(X, y_true); return self

    def predict(self, preds: Dict[str, np.ndarray]) -> np.ndarray:
        X = np.vstack([preds[k] for k in self.keys]).T
        return self.model.predict_proba(X)[:,1]
