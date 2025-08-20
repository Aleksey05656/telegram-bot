# services/recommendation_engine.py
"""Сервис для генерации комплексных прогнозов и рекомендаций."""
# (cleanup) удалены неиспользуемые импорты asyncio и timedelta
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import numpy as np
from logger import logger
from config import CONFIDENCE, get_settings
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
    def __init__(self, sportmonks_client, *args, **kwargs):
        """Инициализация Recommendation Engine."""
        super().__init__(*args, **kwargs)
        self.settings = get_settings()
        self.poisson_model = poisson_model
        self.regression_model = poisson_regression_model
        # Инициализация сервисов
        self.data_processor = data_processor
        self.modifier = prediction_modifier
        self.home_advantage_factor = 1.15 # Базовое преимущество домашней команды
        # Инициализация клиента
        self.sportmonks_client = sportmonks_client
        # Инициализация калибратора вероятностей для 1X2
        try:
            self.calibrator = ProbabilityCalibrator(
                keys=["home_win", "draw", "away_win"],
                weights={"draw": 0.7},            # пример: чуть мягче калибровать ничью
                strict_guard=True,
                max_shift=0.25,
                max_weight_on_large_shift=0.5,
            )
        except Exception:
            # не блокируем работу движка, если калибратор недоступен
            self.calibrator = None
        logger.info("RecommendationEngine инициализирован")

    @staticmethod
    def _confidence_from_probs(probs: Dict[str, float]) -> float:
        """
        Универсальный расчёт confidence:
        - 3-исход: margin(top1 - top2) для {home_win,draw,away_win} или probability_*.
        - 2-исход: |p1 - p2| для {yes,no} или {over,under} или {p1,p2}.
        """
        keys = set(probs.keys())
        # 3-way
        if {"home_win", "draw", "away_win"}.issubset(keys) or \
           {"probability_home_win", "probability_draw", "probability_away_win"}.issubset(keys):
            h = float(probs.get("home_win", probs.get("probability_home_win", 0.0)))
            d = float(probs.get("draw", probs.get("probability_draw", 0.0)))
            a = float(probs.get("away_win", probs.get("probability_away_win", 0.0)))
            vals = sorted([h, d, a], reverse=True)
            return float(max(0.0, min(1.0, (vals[0] - vals[1]) if len(vals) >= 2 else 0.0)))
        # 2-way
        if {"yes", "no"}.issubset(keys):
            p1, p2 = float(probs["yes"]), float(probs["no"])
            return float(max(0.0, min(1.0, abs(p1 - p2))))
        if {"over", "under"}.issubset(keys):
            p1, p2 = float(probs["over"]), float(probs["under"])
            return float(max(0.0, min(1.0, abs(p1 - p2))))
        if {"p1", "p2"}.issubset(keys):
            p1, p2 = float(probs["p1"]), float(probs["p2"])
            return float(max(0.0, min(1.0, abs(p1 - p2))))
        # fallback
        try:
            vals = sorted([float(v) for v in probs.values()], reverse=True)
            return float(max(0.0, min(1.0, (vals[0] - vals[1]) if len(vals) >= 2 else 0.0)))
        except Exception:
            return 0.0

    @staticmethod
    def _penalize_confidence(
        base: float, *, missing_ratio: float = 0.0, freshness_minutes: float = 0.0
    ) -> float:
        """Применяем штрафы за пропуски и устаревшие данные."""
        try:
            c = float(base)
            c *= 1 - float(CONFIDENCE.get("missing_penalty_alpha", 0.2)) * float(missing_ratio)
            freshness_penalty = float(CONFIDENCE.get("freshness_penalty_alpha", 0.15)) * (
                float(freshness_minutes) / 60.0
            )
            c *= max(0.0, 1 - freshness_penalty)
            return float(max(0.0, min(1.0, c)))
        except Exception:
            return base

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
            # ⚙️ Калибруем 1X2 вероятности, если калибратор доступен
            if hasattr(self, "calibrator") and self.calibrator is not None:
                try:
                    # Поддерживаем оба набора ключей: probability_* или home/draw/away
                    to_calibrate = {
                        "home_win": float(poisson_result.get("home_win", poisson_result.get("probability_home_win", 0.0))),
                        "draw": float(poisson_result.get("draw", poisson_result.get("probability_draw", 0.0))),
                        "away_win": float(poisson_result.get("away_win", poisson_result.get("probability_away_win", 0.0))),
                    }
                    calibrated_1x2 = self.calibrator.predict(to_calibrate)
                    # возвращаем в исходный нейминг, которым далее пользуется код
                    poisson_result.update({
                        "home_win": calibrated_1x2.get("home_win", to_calibrate["home_win"]),
                        "draw": calibrated_1x2.get("draw", to_calibrate["draw"]),
                        "away_win": calibrated_1x2.get("away_win", to_calibrate["away_win"]),
                        "probability_home_win": calibrated_1x2.get("home_win", to_calibrate["home_win"]),
                        "probability_draw": calibrated_1x2.get("draw", to_calibrate["draw"]),
                        "probability_away_win": calibrated_1x2.get("away_win", to_calibrate["away_win"]),
                    })
                except Exception as _e:
                    logger.warning("Calibrator skipped: %s", _e)
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
                base_conf = self._confidence_from_probs(poisson_result)
                confidence = self._penalize_confidence(
                    base_conf,
                    missing_ratio=missing_ratio,
                    freshness_minutes=missing_data_info.get("data_freshness_minutes", 0.0),
                )
            except Exception as _e:
                logger.warning("Ошибка при расчёте confidence: %s", _e)
                confidence = 0.0
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
    async def _calculate_base_lambdas(self, match_data: Dict, team_stats: Dict) -> List[float]:
        """Расчет базовых параметров λ."""
        try:
            # В реальной реализации здесь будет расчет λ
            # Например, с использованием poisson_regression_model
            # Для примера возвращаем заглушку
            return [1.5, 1.2]  # Значения по умолчанию
        except Exception as e:
            logger.error(f"Ошибка при расчете базовых λ: {e}")
            return [1.5, 1.2]  # Значения по умолчанию
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
    async def _generate_betting_recommendations(
        self,
        lambda_home: float,
        lambda_away: float,
        probabilities: Dict[str, float],
        match_context: Dict[str, Any],
        missing_data_info: Optional[Dict[str, Any]] = None,
    ) -> List[BettingRecommendation]:
        """Генерация рекомендаций по ставкам."""
        try:
            logger.debug("Генерация рекомендаций по ставкам")
            recommendations: List[BettingRecommendation] = []
            missing_ratio = (missing_data_info or {}).get("missing_ratio", 0.0)
            data_freshness_minutes = (missing_data_info or {}).get("data_freshness_minutes", 0.0)
            # === Result market ===
            home_prob = float(probabilities.get("probability_home_win", probabilities.get("home_win", 0.0)))
            draw_prob = float(probabilities.get("probability_draw", probabilities.get("draw", 0.0)))
            away_prob = float(probabilities.get("probability_away_win", probabilities.get("away_win", 0.0)))
            result_confidence = self._confidence_from_probs({
                "probability_home_win": home_prob,
                "probability_draw": draw_prob,
                "probability_away_win": away_prob,
            })
            res_risk = (
                RiskLevel.HIGH if result_confidence < 0.15 else
                RiskLevel.MEDIUM if result_confidence < 0.3 else
                RiskLevel.LOW
            )
            if home_prob > 0.5:
                rec = BettingRecommendation(
                    market="1X2",
                    selection="Home",
                    confidence=result_confidence,
                    risk_level=res_risk,
                    reasoning="Высокая вероятность победы домашней команды",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            if draw_prob > 0.5:
                rec = BettingRecommendation(
                    market="1X2",
                    selection="Draw",
                    confidence=result_confidence,
                    risk_level=RiskLevel.HIGH,
                    reasoning="Высокая вероятность ничьей",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            if away_prob > 0.5:
                rec = BettingRecommendation(
                    market="1X2",
                    selection="Away",
                    confidence=result_confidence,
                    risk_level=res_risk,
                    reasoning="Высокая вероятность победы гостевой команды",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            # === Totals market ===
            over_prob = float(probabilities.get("probability_over_2_5", probabilities.get("over", 0.0)))
            under_prob = float(probabilities.get("probability_under_2_5", probabilities.get("under", 0.0)))
            total_confidence = self._confidence_from_probs({"over": over_prob, "under": under_prob})
            tot_risk = (
                RiskLevel.HIGH if total_confidence < 0.1 else
                RiskLevel.MEDIUM if total_confidence < 0.25 else
                RiskLevel.LOW
            )
            if over_prob > 0.5:
                rec = BettingRecommendation(
                    market="Totals",
                    selection="Over",
                    confidence=total_confidence,
                    risk_level=tot_risk,
                    reasoning="Высокая вероятность тотала больше 2.5",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            if under_prob > 0.5:
                rec = BettingRecommendation(
                    market="Totals",
                    selection="Under",
                    confidence=total_confidence,
                    risk_level=tot_risk,
                    reasoning="Высокая вероятность тотала меньше 2.5",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            # === BTTS market ===
            btts_yes_prob = float(probabilities.get("probability_btts_yes", probabilities.get("yes", 0.0)))
            btts_no_prob = float(probabilities.get("probability_btts_no", probabilities.get("no", 0.0)))
            btts_confidence = self._confidence_from_probs({"yes": btts_yes_prob, "no": btts_no_prob})
            btts_risk = (
                RiskLevel.HIGH if btts_confidence < 0.1 else
                RiskLevel.MEDIUM if btts_confidence < 0.25 else
                RiskLevel.LOW
            )
            if btts_yes_prob > 0.5:
                rec = BettingRecommendation(
                    market="BTTS",
                    selection="Yes",
                    confidence=btts_confidence,
                    risk_level=btts_risk,
                    reasoning="Высокая вероятность того, что обе команды забьют",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            if btts_no_prob > 0.5:
                rec = BettingRecommendation(
                    market="BTTS",
                    selection="No",
                    confidence=btts_confidence,
                    risk_level=btts_risk,
                    reasoning="Высокая вероятность того, что одна из команд не забьёт",
                )
                penalized_confidence = self._penalize_confidence(
                    rec.confidence,  # base
                    missing_ratio=missing_ratio,
                    freshness_minutes=data_freshness_minutes,
                )
                rec.confidence = penalized_confidence
                recommendations.append(rec)
            # === Bivariate Poisson adjustment ===
            if self.settings.MODEL_FLAGS.get("enable_bivariate_poisson", False) and HAS_BIVARIATE_POISSON:
                try:
                    # Bivariate Poisson коррекции (безопасный вызов)
                    try:
                        rho = estimate_rho(match_context)
                    except Exception:
                        rho = 0.0
                    bivar_model = BivariatePoisson(lambda_home, lambda_away, rho)
                    btts_yes_corr, btts_no_corr = bivar_model.calculate_btts()
                    over_corr, under_corr = bivar_model.calculate_totals()
                    btts_corr_probs = {"yes": btts_yes_corr, "no": btts_no_corr}
                    total_corr_probs = {"over": over_corr, "under": under_corr}
                    # Скорректированные вероятности BTTS/Тоталов (ключи {'yes','no'} и {'over','under'})
                    btts_conf = self._confidence_from_probs(btts_corr_probs)
                    total_conf = self._confidence_from_probs(total_corr_probs)
                    if btts_yes_corr > 0.5 and not any(r.market == "BTTS" and r.selection == "Yes" for r in recommendations):
                        risk_level = (
                            RiskLevel.HIGH if btts_conf < 0.1 else
                            RiskLevel.MEDIUM if btts_conf < 0.25 else
                            RiskLevel.LOW
                        )
                        rec = BettingRecommendation(
                            market="BTTS",
                            selection="Yes",
                            confidence=btts_conf,
                            risk_level=risk_level,
                            reasoning="Высокая вероятность 'Обе забьют' (с корреляцией)",
                        )
                        penalized_confidence = self._penalize_confidence(
                            rec.confidence,  # base
                            missing_ratio=missing_ratio,
                            freshness_minutes=data_freshness_minutes,
                        )
                        rec.confidence = penalized_confidence
                        recommendations.append(rec)
                    if over_corr > 0.5 and not any(r.market == "Totals" and r.selection == "Over" for r in recommendations):
                        risk_level = (
                            RiskLevel.HIGH if total_conf < 0.1 else
                            RiskLevel.MEDIUM if total_conf < 0.25 else
                            RiskLevel.LOW
                        )
                        rec = BettingRecommendation(
                            market="Totals",
                            selection="Over",
                            confidence=total_conf,
                            risk_level=risk_level,
                            reasoning="Высокая вероятность Over (с корреляцией)",
                        )
                        penalized_confidence = self._penalize_confidence(
                            rec.confidence,  # base
                            missing_ratio=missing_ratio,
                            freshness_minutes=data_freshness_minutes,
                        )
                        rec.confidence = penalized_confidence
                        recommendations.append(rec)
                except Exception as bivar_error:
                    logger.error(f"Ошибка при использовании Bivariate Poisson: {bivar_error}")
            return recommendations
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            return []
# Создание экземпляра движка рекомендаций
recommendation_engine = RecommendationEngine()


class ProbabilityCalibrator:
    def __init__(
        self,
        method: str = "platt",
        keys: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        strict_guard: bool = True,
        max_shift: float = 0.25,
        max_weight_on_large_shift: float = 0.5,
    ):
        self.method = method
        self.keys = keys or []
        self.weights = weights or {}
        self.strict_guard = bool(strict_guard)
        self.max_shift = float(max(0.0, max_shift))
        self.max_weight_on_large_shift = float(min(1.0, max(0.0, max_weight_on_large_shift)))
        self._models: Dict[str, Any] = {}

    def fit(self, p_base: Dict[str, np.ndarray], y_true: np.ndarray) -> "ProbabilityCalibrator":
        from sklearn.isotonic import IsotonicRegression
        from sklearn.linear_model import LogisticRegression
        for key, p in p_base.items():
            if self.method == "isotonic":
                m = IsotonicRegression(out_of_bounds="clip")
                self._models[key] = m.fit(p, (y_true == (key)).astype(float))
            else:
                m = LogisticRegression(max_iter=1000)
                self._models[key] = m.fit(p.reshape(-1, 1), (y_true == (key)).astype(int))
        return self

    def predict(self, probs: Dict[str, float]) -> Dict[str, float]:
        """
        Калибруем вероятности по ключам.
        - Если у модели есть predict_proba → используем вероятность положительного класса ([:, 1]).
        - Иначе, если есть predict (напр. IsotonicRegression) → используем её вывод.
        - Иначе, если есть transform → пробуем transform.
        - Иначе оставляем исходное p.
        Дополнительно поддерживается блендинг по весам: final = w*calibrated + (1-w)*original, w∈[0,1].
        Если self.keys указан, калибруем только эти ключи; прочие — pass-through.
        """
        calibrated: Dict[str, float] = {}

        # набор ключей для прохода: либо заданные, либо все из probs
        iter_keys = list(self.keys) if self.keys else list(probs.keys())

        for k in iter_keys:
            if k not in probs:
                # ключ не задан во входе — пропускаем
                continue
            original_p = float(probs[k])
            m = self._models.get(k)

            # по умолчанию — исходная вероятность
            cal_p = original_p

            if m is not None:
                try:
                    # 1) Классификаторы с predict_proba (например, LogisticRegression)
                    if hasattr(m, "predict_proba"):
                        proba = m.predict_proba([[original_p]])
                        # Надёжный разбор без лишних shape-предикатов
                        try:
                            # классическая форма (1, 2)
                            cal_p = float(proba[0][1])
                        except Exception:
                            try:
                                # если это numpy-подобный объект
                                cal_p = float(getattr(proba, "squeeze", lambda: proba)())
                            except Exception:
                                # списки/кортежи и пр.
                                if isinstance(proba, (list, tuple)):
                                    if proba and isinstance(proba[0], (list, tuple)) and len(proba[0]) >= 2:
                                        cal_p = float(proba[0][1])
                                    elif proba:
                                        cal_p = float(proba[0])
                                else:
                                    cal_p = original_p
                    # 2) Регрессоры/калибраторы с predict (напр. IsotonicRegression)
                    elif hasattr(m, "predict"):
                        y = m.predict([[original_p]])
                        # y может быть массивом/списком или скаляром
                        cal_p = float(y[0]) if hasattr(y, "__len__") else float(y)
                    # 3) Редкий случай — только transform
                    elif hasattr(m, "transform"):
                        y = m.transform([[original_p]])
                        # часто transform возвращает 2D; берём [0][0] при наличии
                        if hasattr(y, "__len__"):
                            try:
                                cal_p = float(y[0][0])
                            except Exception:
                                cal_p = float(y[0]) if hasattr(y, "__len__") else float(y)
                        else:
                            cal_p = float(y)
                except Exception:
                    # на любой ошибке откатываемся к исходной вероятности
                    cal_p = original_p

            # приводим в [0,1]
            cal_p = max(0.0, min(1.0, cal_p))

            # применяем блендинг по весу (сила калибровки)
            w = float(self.weights.get(k, 1.0))
            # зажимаем вес в [0,1] на всякий случай
            if w < 0.0:
                w = 0.0
            elif w > 1.0:
                w = 1.0
            # сторожок: если калибровка слишком далеко ушла от исходной p — ограничим влияние
            if self.strict_guard and abs(cal_p - original_p) > self.max_shift:
                w = min(w, self.max_weight_on_large_shift)
            final_p = w * cal_p + (1.0 - w) * original_p

            calibrated[k] = float(max(0.0, min(1.0, final_p)))

        # Для ключей, не попавших в iter_keys (когда self.keys задан), перенесём как есть:
        if self.keys:
            for k, p in probs.items():
                if k not in calibrated:
                    calibrated[k] = float(max(0.0, min(1.0, p)))

        # гарантируем присутствие всех ключей из self.keys,
        # даже если каких-то значений нет во входе probs
        if self.keys:
            for k in self.keys:
                if k not in calibrated:
                    calibrated[k] = float(max(0.0, min(1.0, float(probs.get(k, 0.0)))))
        # если после добора словарь всё ещё пуст (например, и self.keys, и probs фактически пустые)
        if not calibrated:
            if self.keys:
                # инициализируем ключи из self.keys нулями, чтобы не падать на нормализации
                for k in self.keys:
                    if k not in calibrated:
                        calibrated[k] = 0.0
            else:
                # переносим всё, что есть в probs, приводя к [0,1]
                for k, p in probs.items():
                    calibrated[k] = float(max(0.0, min(1.0, float(p))))

        # безопасная нормализация
        s = sum(calibrated.values())
        if s <= 0:
            # возвращаем корректную «нулевую» дистрибуцию по имеющимся ключам
            return {k: 0.0 for k in calibrated}
        return {k: (v / s) for k, v in calibrated.items()}

    # Для ансамблирования нескольких моделей используйте EnsembleCombiner.
