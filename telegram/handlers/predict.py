# telegram/handlers/predict.py
"""Обработчик команды /predict для прогнозирования результатов матчей."""
import asyncio
import json
import re
import uuid
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from logger import logger
# Импортируем task_manager для постановки задач в очередь
from workers.task_manager import task_manager
# Импортируем кэш из Postgres
from database.cache_postgres import cache
# Импортируем модуль логирования в БД
from database.db_logging import log_prediction
router = Router()
class PredictionStates(StatesGroup):
    waiting_for_teams = State()
def process_team_names(text: str) -> Optional[Tuple[str, str]]:
    """Извлекает названия команд из текста сообщения."""
    try:
        # Убираем команду /predict и лишние пробелы
        command_part = "/predict"
        if text.startswith(command_part):
            message_text = text[len(command_part):].strip()
        else:
            message_text = text.strip()
        # Разделяем по тире
        parts = [p.strip() for p in message_text.split(' - ') if p.strip()]
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            # Попробуем обработать случаи с лишними дефисами или пробелами
            # Например, "Команда1 - - Команда2" или "Команда1-Команда2"
            # Разделяем по шаблону: один или несколько дефисов, возможно окружены пробелами
            parts = re.split(r'\s*-\s*', message_text)
            parts = [p for p in parts if p] # Убираем пустые строки
            if len(parts) >= 2:
                return parts[0], parts[-1] # Берем первую и последнюю как названия
            else:
                return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении названий команд: {e}")
        return None
def compute_probs(lambda_home: float, lambda_away: float,
                  use_bivariate: bool = False) -> Dict[str, float]:
    """Вычисление вероятностей рынков.
    Args:
        lambda_home (float): λ домашней команды
        lambda_away (float): λ гостевой команды
        use_bivariate (bool): Использовать Bivariate Poisson модель
    Returns:
        Dict[str, float]: Словарь вероятностей
    """
    try:
        from ml.models.poisson_model import poisson_model
        logger.info(f"Вычисление вероятностей: λ_дом={lambda_home:.3f}, λ_гост={lambda_away:.3f}")
        # Подготавливаем входные данные для модели
        input_data = {
            "expected_home_goals": lambda_home,
            "expected_away_goals": lambda_away
        }
        # Получаем вероятности от Poisson модели
        poisson_result = poisson_model.predict(input_data)
        # Преобразуем результат в словарь вероятностей
        probabilities = {
            "probability_home_win": poisson_result.get("probability_home_win", 0.0),
            "probability_draw": poisson_result.get("probability_draw", 0.0),
            "probability_away_win": poisson_result.get("probability_away_win", 0.0),
            "probability_over_2_5": poisson_result.get("probability_over", 0.0),
            "probability_under_2_5": poisson_result.get("probability_under", 0.0),
            "probability_btts_yes": poisson_result.get("probability_btts_yes", 0.0),
            "probability_btts_no": poisson_result.get("probability_btts_no", 0.0)
        }
        logger.info(f"Вероятности рассчитаны: {probabilities}")
        return probabilities
    except Exception as e:
        logger.error(f"Ошибка при вычислении вероятностей: {e}", exc_info=True)
        return {}
def compute_confidence_from_margin(probs: Dict[str, float]) -> float:
    """Вычисление уверенности на основе маржи между вероятностями.
    Args:
        probs (Dict[str, float]): Словарь вероятностей {"home": p1, "draw": p2, "away": p3}
    Returns:
        float: Уровень уверенности (0-1)
    """
    try:
        import numpy as np
        if not probs:
            logger.warning("Пустой словарь вероятностей для расчета уверенности")
            return 0.0
        # Получаем значения вероятностей
        prob_values = [
            probs.get("probability_home_win", 0),
            probs.get("probability_draw", 0),
            probs.get("probability_away_win", 0)
        ]
        non_zero_probs = [p for p in prob_values if p > 0]
        if not non_zero_probs:
            logger.warning("Все вероятности равны 0 для расчета уверенности")
            return 0.0
        max_prob = max(prob_values)
        min_prob = min(non_zero_probs)  # Минимум среди ненулевых
        # Расчет маржи
        margin = max_prob - min_prob
        # Нормализация уверенности (простой способ)
        # Можно заменить на более сложную формулу
        confidence = max(0.0, min(1.0, margin * 2))  # Пример нормализации
        logger.debug(f"Рассчитана уверенность: {confidence:.3f} (маржа: {margin:.3f})")
        return confidence
    except Exception as e:
        logger.error(f"Ошибка при вычислении уверенности: {e}", exc_info=True)
        return 0.0
def penalize_confidence(confidence: float, missing_ratio: float, freshness_minutes: float, settings: Any) -> float:
    """Применение штрафа к уверенности на основе пропусков и свежести данных.
    Args:
        confidence (float): Исходная уверенность (0-1).
        missing_ratio (float): Доля пропущенных значений (0-1).
        freshness_minutes (float): Свежесть данных в минутах.
        settings (Any): Объект настроек
    Returns:
        float: Скорректированная уверенность (0-1).
    """
    try:
        # Получаем параметры штрафов из конфигурации
        missing_penalty_alpha = getattr(settings, 'CONFIDENCE', {}).get('missing_penalty_alpha', 0.2)
        freshness_penalty_alpha = getattr(settings, 'CONFIDENCE', {}).get('freshness_penalty_alpha', 0.15)
        # Применяем штраф за пропуски
        missing_penalty = 1.0 - (missing_ratio * missing_penalty_alpha)
        # Применяем штраф за свежесть (например, после 60 минут начинаем штрафовать)
        freshness_base_minutes = getattr(settings, 'CONFIDENCE', {}).get('freshness_base_minutes', 60)
        if freshness_minutes > freshness_base_minutes:
            extra_minutes = freshness_minutes - freshness_base_minutes
            freshness_penalty = 1.0 - ((extra_minutes / 60.0) * freshness_penalty_alpha)
            freshness_penalty = max(0.5, freshness_penalty)  # Минимум 50%
        else:
            freshness_penalty = 1.0
        # Комбинируем штрафы
        final_confidence = confidence * missing_penalty * freshness_penalty
        final_confidence = max(0.0, min(1.0, final_confidence))
        logger.debug(f"Применены штрафы к уверенности: "
                     f"исходная={confidence:.3f}, "
                     f"пропуски={missing_ratio:.2f} (штраф: x{missing_penalty:.3f}), "
                     f"свежесть={freshness_minutes:.1f}мин (штраф: x{freshness_penalty:.3f}), "
                     f"итоговая={final_confidence:.3f}")
        return final_confidence
    except Exception as e:
        logger.error(f"Ошибка при применении штрафа к уверенности: {e}")
        return confidence
def apply_calibrators(probabilities: Dict[str, float]) -> Dict[str, float]:
    """Применение калибраторов вероятностей (например, изотонная регрессия).
    Args:
        probabilities (Dict[str, float]): Исходные вероятности
    Returns:
        Dict[str, float]: Откалиброванные вероятности
    """
    try:
        if not probabilities:
            logger.warning("Пустые вероятности при применении калибраторов")
            return probabilities
        # Заглушка: в реальной реализации здесь будет загрузка обученных калибраторов
        logger.debug("Применение калибраторов вероятностей (заглушка)")
        # Пример простой калибровки (ничего не меняем)
        return probabilities
    except Exception as e:
        logger.error(f"Ошибка при применении калибраторов: {e}")
        return probabilities
async def log_prediction_to_db(match_id: int, features: Dict[str, Any],
                               probs: Dict[str, float], lam_home: float,
                               lam_away: float, confidence: float) -> bool:
    """Логирование прогноза в базу данных.
    Args:
        match_id (int): ID матча
        features (Dict[str, Any]): Признаки матча
        probs (Dict[str, float]): Вероятности исходов
        lam_home (float): λ домашней команды
        lam_away (float): λ гостевой команды
        confidence (float): Уверенность прогноза
    Returns:
        bool: Успешность операции
    """
    try:
        from database.db_logging import log_prediction
        success = await log_prediction(
            match_id=match_id,
            features=features,
            probs=probs,
            lam_home=lam_home,
            lam_away=lam_away,
            confidence=confidence
        )
        if success:
            logger.info(f"[{match_id}] Прогноз успешно записан в БД")
        else:
            logger.error(f"[{match_id}] Ошибка при записи прогноза в БД")
        return success
    except Exception as e:
        logger.error(f"[{match_id}] Ошибка при логировании прогноза в БД: {e}")
        return False
@router.message(Command("predict"))
async def cmd_predict(message: Message, state: FSMContext):
    """Обработчик команды /predict."""
    try:
        logger.info(f"Пользователь {message.from_user.id} запустил команду /predict")
        await message.answer("Введите названия команд в формате:\n`Команда 1 - Команда 2`", parse_mode="Markdown")
        await state.set_state(PredictionStates.waiting_for_teams)
    except Exception as e:
        logger.error(f"Ошибка в обработчике cmd_predict для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        await state.clear()
@router.message(StateFilter(PredictionStates.waiting_for_teams))
async def process_teams_input(message: Message, state: FSMContext):
    """Обработка ввода названий команд."""
    try:
        text = message.text.strip()
        teams = process_team_names(text)
        if not teams:
            await message.answer("❌ Неверный формат. Пожалуйста, введите в формате:\n`Команда 1 - Команда 2`", parse_mode="Markdown")
            return
        home_team, away_team = teams
        await message.answer(f"⚽ Ищу матч: {home_team} - {away_team}")
        # Создаем уникальный ID задачи
        task_id = str(uuid.uuid4())
        logger.info(f"Создана задача прогнозирования {task_id} для матча {home_team} - {away_team}")
        # Отправляем задачу в очередь
        await task_manager.add_task(task_id, 'predict_match', {
            'home_team': home_team,
            'away_team': away_team
        })
        await message.answer(f"⏳ Задача принята. ID: `{task_id}`\nОжидайте результат...", parse_mode="Markdown")
        await state.clear()
    except Exception as e:
        logger.error(f"Критическая ошибка в обработчике process_teams_input для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке вашего запроса. Попробуйте еще раз.")
        await state.clear()
# Основная функция прогнозирования (интеграция всего пайплайна)
async def generate_full_prediction(match_id: int, home_team: str, away_team: str) -> Dict[str, Any]:
    """Генерация полного прогноза по всему пайплайну.
    Args:
        match_id (int): ID матча
        home_team (str): Название домашней команды
        away_team (str): Название гостевой команды
    Returns:
        Dict[str, Any]: Полный прогноз
    """
    try:
        logger.info(f"[{match_id}] Начало полного прогнозирования: {home_team} vs {away_team}")
        # === 1. Сбор данных и генерация фич (data_processor) ===
        features = await build_features(match_id)
        if not features:
            logger.error(f"[{match_id}] Не удалось собрать признаки")
            return {"error": "Не удалось собрать признаки"}
        # === 2. Предсказание λ с использованием Poisson-регрессионной модели ===
        lambda_home, lambda_away = await predict_lambda(features)
        # === 3. Применение модификаторов (prediction_modifier) ===
        # Модификатор погоды и поля
        lambda_home, lambda_away = apply_weather_field(
            lambda_home, lambda_away,
            features.get("weather", {}),
            features.get("weather", {}).get("pitch_type", "good")
        )
        # Модификатор неопределенности состава (ядро команды)
        core_home = features.get("core_availability", {}).get("home", 1.0)
        core_away = features.get("core_availability", {}).get("away", 1.0)
        lambda_home, lambda_away = apply_lineup_uncertainty(
            lambda_home, lambda_away, core_home, core_away
        )
        # === 4. Вычисление вероятностей рынков (poisson_model или bivariate) ===
        use_bivariate = settings.MODEL_FLAGS.get("enable_bivariate_poisson", False)
        probabilities = compute_probs(lambda_home, lambda_away, use_bivariate)
        # === 5. Вычисление уверенности на основе маржи (margin-based confidence) ===
        confidence = compute_confidence_from_margin(probabilities)
        # === 6. Применение калибровки (если включено) ===
        if settings.MODEL_FLAGS.get("enable_calibration", False):
            probabilities = apply_calibrators(probabilities)
        # === 7. Применение штрафов к уверенности (missing/freshness) ===
        missing_ratio = features.get("missing_ratio", 0.0)
        freshness_minutes = features.get("freshness_minutes", 0.0)  # Теперь используем реальное значение
        confidence = penalize_confidence(confidence, missing_ratio, freshness_minutes, settings)
        # === 8. Логирование прогноза в БД (db_logging) ===
        await log_prediction_to_db(match_id, features, probabilities, lambda_home, lambda_away, confidence)
        # === 9. Формирование финального прогноза ===
        prediction_result = {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "expected_goals": {
                "home": lambda_home,
                "away": lambda_away
            },
            "probabilities": probabilities,
            "confidence": confidence,
            "features": features,  # Можно удалить, если не нужно в ответе
            "generated_at": datetime.now().isoformat()
        }
        logger.info(f"[{match_id}] Полный прогноз сгенерирован успешно")
        return prediction_result
    except Exception as e:
        logger.error(f"[{match_id}] Критическая ошибка при генерации полного прогноза: {e}", exc_info=True)
        return {"error": str(e)}
# === Вспомогательные функции для пайплайна ===
async def build_features(match_id: int) -> Dict[str, Any]:
    """Сбор данных и генерация признаков.
    Args:
        match_id (int): ID матча
    Returns:
        Dict[str, Any]: Словарь признаков
    """
    try:
        from services.data_processor import data_processor
        from services.sportmonks_client import sportmonks_client
        logger.info(f"[{match_id}] Начало сбора данных и генерации признаков")
        # 1. Получение контекста матча
        match_context = await data_processor.get_match_context(match_id)
        if not match_context:
            logger.error(f"[{match_id}] Не удалось получить контекст матча")
            return {}
        # 2. Генерация фич (rolling/EWMA, нормировки, travel, importance, mismatch, streaks, weather imputes, missing_mask)
        features = {}
        # Добавляем базовые признаки
        features.update({
            "match_id": match_id,
            "home_team_id": match_context.get("home_team_id"),
            "away_team_id": match_context.get("away_team_id"),
            "league_id": match_context.get("league_id"),
            "match_date": match_context.get("match_date").isoformat() if match_context.get("match_date") else None,
        })
        # Добавляем статистику команд
        features.update(match_context.get("team_stats", {}))
        # Добавляем признаки усталости
        features.update(match_context.get("fatigue_features", {}))
        # Добавляем признаки важности матча
        features["match_importance"] = match_context.get("match_importance", 0.5)
        # Добавляем стилевые несоответствия
        features["style_mismatch"] = match_context.get("style_mismatch", 0.0)
        # Добавляем стрики и серии
        features["streak_features"] = match_context.get("streak_features", {})
        # Добавляем погодные данные
        features["weather"] = match_context.get("weather", {})
        # Добавляем маску пропущенных значений и долю пропусков
        features_with_mask, missing_mask = data_processor.add_missing_mask(features)
        features = features_with_mask
        features["missing_mask"] = missing_mask
        features["missing_ratio"] = sum(missing_mask.values()) / len(missing_mask) if missing_mask else 0.0
        # === Кэшируем признаки с версионированными ключами ===
        cache_key = f"features:v1:{match_id}"
        await cache.set(cache_key, features, ttl=3600)  # TTL 1 час
        logger.info(f"[{match_id}] Признаки успешно собраны и закэшированы")
        return features
    except Exception as e:
        logger.error(f"[{match_id}] Ошибка при сборе данных и генерации признаков: {e}", exc_info=True)
        return {}
async def predict_lambda(features: Dict[str, Any]) -> Tuple[float, float]:
    """Предсказание параметров λ с использованием Poisson-регрессионной модели.
    Args:
        features (Dict[str, Any]): Признаки матча
    Returns:
        Tuple[float, float]: (λ_домашней_команды, λ_гостевой_команды)
    """
    try:
        from ml.models.poisson_regression_model import poisson_regression_model
        match_id = features.get("match_id", "unknown")
        logger.info(f"[{match_id}] Начало предсказания λ")
        # Получаем параметры λ
        lambda_home, lambda_away = poisson_regression_model.calculate_base_lambda(
            features.get("home_team_id"),
            features.get("away_team_id")
        )
        # Применяем динамическое ограничение
        # (в реальной реализации здесь будет логика динамического ограничения)
        logger.info(f"[{match_id}] Предсказаны λ: домашняя={lambda_home:.3f}, гостевая={lambda_away:.3f}")
        return lambda_home, lambda_away
    except Exception as e:
        logger.error(f"Ошибка при предсказании λ: {e}")
        # Возвращаем значения по умолчанию в случае ошибки
        return 1.5, 1.2
def apply_weather_field(lambda_home: float, lambda_away: float,
                        weather: Dict[str, Any], pitch_type: str) -> Tuple[float, float]:
    """Применение модификаторов погоды и поля.
    Args:
        lambda_home (float): λ домашней команды
        lambda_away (float): λ гостевой команды
        weather (Dict[str, Any]): Данные о погоде
        pitch_type (str): Тип покрытия поля
    Returns:
        Tuple[float, float]: Скорректированные λ
    """
    try:
        from services.prediction_modifier import prediction_modifier
        # Применяем модификаторы погоды и поля
        modified_lambda_home, modified_lambda_away = prediction_modifier.apply_weather_field(
            lambda_home, lambda_away, weather, pitch_type
        )
        logger.debug(f"Применены модификаторы погоды и поля: "
                     f"домашняя {lambda_home:.3f}->{modified_lambda_home:.3f}, "
                     f"гостевая {lambda_away:.3f}->{modified_lambda_away:.3f}")
        return modified_lambda_home, modified_lambda_away
    except Exception as e:
        logger.error(f"Ошибка при применении модификаторов погоды и поля: {e}")
        return lambda_home, lambda_away
def apply_lineup_uncertainty(lambda_home: float, lambda_away: float,
                             core_home: float, core_away: float) -> Tuple[float, float]:
    """Применение модификатора неопределенности состава (ядро команды).
    Args:
        lambda_home (float): λ домашней команды
        lambda_away (float): λ гостевой команды
        core_home (float): Доля ключевых игроков домашней команды
        core_away (float): Доля ключевых игроков гостевой команды
    Returns:
        Tuple[float, float]: Скорректированные λ
    """
    try:
        from services.prediction_modifier import prediction_modifier
        # Применяем модификатор неопределенности состава
        modified_lambda_home, modified_lambda_away = prediction_modifier.apply_lineup_uncertainty(
            lambda_home, lambda_away, core_home, core_away
        )
        logger.debug(f"Применен модификатор неопределенности состава: "
                     f"домашняя {lambda_home:.3f}->{modified_lambda_home:.3f}, "
                     f"гостевая {lambda_away:.3f}->{modified_lambda_away:.3f}")
        return modified_lambda_home, modified_lambda_away
    except Exception as e:
        logger.error(f"Ошибка при применении модификатора неопределенности состава: {e}")
        return lambda_home, lambda_away
# --- Оригинальные обработчики остаются без изменений ---
async def enqueue_prediction(home_team_name: str, away_team_name: str) -> Optional[str]:
    """Постановка задачи прогнозирования в очередь.
    Args:
        home_team_name (str): Название домашней команды
        away_team_name (str): Название гостевой команды
    Returns:
        Optional[str]: Job ID или None в случае ошибки
    """
    try:
        # Создаем уникальный ID задачи
        job_id = str(uuid.uuid4())
        logger.info(f"Создание задачи прогнозирования {job_id}: {home_team_name} vs {away_team_name}")
        # Добавляем задачу в очередь через task_manager
        await task_manager.add_task(job_id, 'predict_match', {
            'home_team': home_team_name,
            'away_team': away_team_name
        })
        logger.info(f"Задача прогнозирования {job_id} поставлена в очередь")
        return job_id
    except Exception as e:
        logger.error(f"Ошибка при постановке задачи прогнозирования в очередь: {e}", exc_info=True)
        return None
@router.callback_query(F.data == "make_prediction")
async def cb_make_prediction(callback: CallbackQuery, state: FSMContext):
    """Обработчик callback для кнопки 'Сделать прогноз'."""
    try:
        logger.info(f"Пользователь {callback.from_user.id} нажал кнопку 'Сделать прогноз'")
        await callback.message.edit_text("Введите названия команд в формате:\n`Команда 1 - Команда 2`", parse_mode="Markdown")
        await state.set_state(PredictionStates.waiting_for_teams)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике cb_make_prediction для пользователя {callback.from_user.id}: {e}", exc_info=True)
        try:
            await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
# === Добавленные хелперы ===
import os, math, joblib, numpy as np
from typing import Optional, Tuple, Dict, Any
def _models_dir() -> str:
    from config import settings
    return getattr(settings, "MODELS_DIR", "models")
def _resolve_version(version: Optional[str]) -> Optional[str]:
    from config import settings
    return getattr(settings, "MODEL_VERSION", None) or version
def _pick_latest_version(path: str) -> Optional[str]:
    try:
        vers = [d for d in os.listdir(path) if d.startswith("v")]
        vers.sort(reverse=True)
        return vers[0] if vers else None
    except Exception:
        return None
def load_artifacts(league: str, market: str, version: Optional[str] = None) -> Tuple[Optional[Any], Optional[Any], Optional[Any], Optional[Any]]:
    base = _models_dir(); ver = _resolve_version(version)
    candidates = []
    league_dir = os.path.join(base, str(league), market)
    if ver: candidates.append(os.path.join(league_dir, ver))
    else:
        lv = _pick_latest_version(league_dir)
        if lv: candidates.append(os.path.join(league_dir, lv))
    global_dir = os.path.join(base, "_global", market)
    if ver: candidates.append(os.path.join(global_dir, ver))
    else:
        gv = _pick_latest_version(global_dir)
        if gv: candidates.append(os.path.join(global_dir, gv))
    base_model = modifier = calibrator = ensemble = None
    for path in candidates:
        if not path or not os.path.isdir(path): continue
        try:
            bm = os.path.join(path, "base_model.joblib")
            if os.path.isfile(bm): base_model = joblib.load(bm)
            mp = os.path.join(path, "modifier.joblib")
            if os.path.isfile(mp):
                from prediction_modifier import CalibrationLayer
                modifier = CalibrationLayer.load(mp)
            cp = os.path.join(path, "calibrator.joblib")
            if os.path.isfile(cp): calibrator = joblib.load(cp)
            ep = os.path.join(path, "ensemble.joblib")
            if os.path.isfile(ep): ensemble = joblib.load(ep)
            if base_model is not None: break
        except Exception:
            continue
    return base_model, modifier, calibrator, ensemble
def compute_confidence(prob_dist: np.ndarray, agreement: Optional[float] = None) -> float:
    eps = 1e-12; p = np.clip(prob_dist, eps, 1 - eps)
    H = -np.sum(p * np.log(p)); Hmax = math.log(len(p)) if len(p) else 1.0
    base = 1.0 - (H / Hmax)
    return float(base if agreement is None else 0.8*base + 0.2*max(0.0, min(1.0, agreement)))
def apply_postprocessing_for_1x2(league_id: str, market: str, probs_1x2: Dict[str, float]) -> Tuple[Dict[str, float], float, str]:
    base_model, modifier, calibrator, ensemble = load_artifacts(str(league_id), market, version=None)
    p = probs_1x2.copy()
    if calibrator is not None and hasattr(calibrator, "predict"):
        p_in = {k: np.array([v], dtype=float) for k, v in p.items() if k in ("home", "draw", "away")}
        try:
            p_out = calibrator.predict(p_in)
            p = {k: float(p_out.get(k, np.array([p[k]]) )[0]) for k in ("home","draw","away")}
            s = sum(p.values()); 
            if s > 0: 
                for k in p: 
                    p[k] /= s
        except Exception:
            pass
    prob_vec = np.array([p.get("home",0.0), p.get("draw",0.0), p.get("away",0.0)], dtype=float)
    conf = compute_confidence(prob_vec)
    # Версию можно прочитать из meta.json при необходимости
    return p, conf, ""
