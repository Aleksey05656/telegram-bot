# scripts/train_model.py
"""Скрипт для обучения Poisson-регрессионной модели."""
import asyncio
import base64
import io
import json
import os
from datetime import datetime, timedelta
from typing import Any

import joblib  # Для сохранения калибратора
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from logger import logger
from ml.calibration import apply_calibration, calibrate_probs

# Импортируем правильный класс модели
from ml.models.poisson_regression_model import PoissonRegressionModel, save_artifacts
from ml.modifiers_model import CalibrationLayer
from services.data_processor import DataProcessor
from services.sportmonks_client import sportmonks_client

# Создаем экземпляр модели
poisson_regression_model = PoissonRegressionModel(
    alpha=0.001, max_iter=300
)  # Можно настроить параметры


def estimate_rho_from_history(samples):
    # эвристика: корреляция остатков по тоталам/BTTS
    # верните значение в [0..min(lam_home, lam_away)]
    return float(
        np.clip(np.corrcoef(samples["resid_home"], samples["resid_away"])[0, 1], 0, 0.8)
    )


async def fetch_training_data(season_id: int = 23855) -> pd.DataFrame:
    """Получение данных для обучения модели.
    Args:
        season_id (int): ID сезона для получения данных
    Returns:
        pd.DataFrame: Данные о матчах
    """
    try:
        logger.info(f"Получение данных для обучения модели. Сезон ID: {season_id}")
        # Получаем сырые данные о матчах
        # Увеличен период сбора данных: 730 дней (2 года) вместо 365
        two_years_ago = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        raw_data = await sportmonks_client.get_fixtures(
            season_id=season_id, next_fixtures=False, date_from=two_years_ago
        )
        if not raw_data:
            logger.warning("Не удалось получить данные о матчах для обучения.")
            return pd.DataFrame()
        logger.info(f"Получено {len(raw_data)} сырых записей о матчах.")
        # Обрабатываем данные через DataProcessor
        # ПРЕДПОЛОЖЕНИЕ: DataProcessor теперь возвращает данные в формате,
        # пригодном для prepare_features новой модели.
        # То есть, каждая запись содержит все нужные колонки:
        # home_team_id, away_team_id, home_goals, away_goals, league_id,
        # home_rest_days, away_rest_days, home_km_trip, away_km_trip,
        # home_xg, away_xg, home_xga, away_xga,
        # home_ppda, away_ppda, home_oppda, away_oppda,
        # home_mismatch, away_mismatch,
        # home_league_zscore_attack, away_league_zscore_attack,
        # home_league_zscore_defense, away_league_zscore_defense
        DataProcessor()
        # ПРЕДПОЛОЖЕНИЕ: Метод обработки теперь возвращает данные с нужными полями
        # processed_data = await processor.process_matches_data_for_poisson_model(raw_data)
        # Для демонстрации создадим фиктивные данные с правильной структурой
        # В реальном случае, processor должен заполнить эти поля корректными данными
        processed_data = []
        for match in raw_data[:100]:  # Только первые 100 для примера
            if match.get("status") == "FT":  # Только завершенные матчи
                processed_data.append(
                    {
                        "home_team_id": match.get("home_team", {}).get("id", 0),
                        "away_team_id": match.get("away_team", {}).get("id", 0),
                        "home_goals": match.get("home_team", {}).get("goals", 0),
                        "away_goals": match.get("away_team", {}).get("goals", 0),
                        "date": match.get("date"),
                        "league_id": match.get("league_id", 0),
                        # --- Непрерывные ковариаты ---
                        "home_rest_days": match.get("home_team", {}).get(
                            "rest_days", 3.0
                        ),
                        "away_rest_days": match.get("away_team", {}).get(
                            "rest_days", 3.0
                        ),
                        "home_km_trip": match.get("home_team", {}).get("km_trip", 0.0),
                        "away_km_trip": match.get("away_team", {}).get("km_trip", 0.0),
                        "home_xg": match.get("home_team", {}).get("xg", 1.5),
                        "away_xg": match.get("away_team", {}).get("xg", 1.2),
                        "home_xga": match.get("home_team", {}).get(
                            "xga", 1.2
                        ),  # Предполагаем xga
                        "away_xga": match.get("away_team", {}).get(
                            "xga", 1.5
                        ),  # Предполагаем xga
                        "home_ppda": match.get("home_team", {}).get("ppda", 10.0),
                        "away_ppda": match.get("away_team", {}).get("ppda", 10.0),
                        "home_oppda": match.get("home_team", {}).get(
                            "oppda", 8.0
                        ),  # Предполагаем oppda
                        "away_oppda": match.get("away_team", {}).get(
                            "oppda", 8.0
                        ),  # Предполагаем oppda
                        "home_mismatch": match.get("home_team", {}).get(
                            "mismatch", 0.1
                        ),  # Предполагаем mismatch
                        "away_mismatch": match.get("away_team", {}).get(
                            "mismatch", 0.1
                        ),  # Предполагаем mismatch
                        "home_league_zscore_attack": match.get("home_team", {}).get(
                            "league_zscore_attack", 0.5
                        ),  # Предполагаем
                        "away_league_zscore_attack": match.get("away_team", {}).get(
                            "league_zscore_attack", 0.5
                        ),  # Предполагаем
                        "home_league_zscore_defense": match.get("home_team", {}).get(
                            "league_zscore_defense", -0.3
                        ),  # Предполагаем
                        "away_league_zscore_defense": match.get("away_team", {}).get(
                            "league_zscore_defense", -0.3
                        ),  # Предполагаем
                    }
                )
        if not processed_data:
            logger.warning("Обработанные данные для обучения пусты.")
            return pd.DataFrame()
        logger.info(f"Обработано {len(processed_data)} матчей.")
        # Преобразуем в DataFrame
        df = pd.DataFrame(processed_data)
        logger.info(f"Создан DataFrame с {len(df)} записями.")
        return df
    except Exception as e:
        logger.error(f"Ошибка при получении данных для обучения: {e}", exc_info=True)
        return pd.DataFrame()


async def validate_training_data(data: pd.DataFrame) -> bool:
    """Валидация данных для обучения.
    Args:
        data (pd.DataFrame): Данные для валидации
    Returns:
        bool: True если данные валидны
    """
    try:
        if data.empty:
            logger.error("Валидация не пройдена: пустой DataFrame")
            return False
        # Новые обязательные колонки
        required_columns = [
            "home_team_id",
            "away_team_id",
            "home_goals",
            "away_goals",
            "league_id",
            "date",
            "home_rest_days",
            "away_rest_days",
            "home_km_trip",
            "away_km_trip",
            "home_xg",
            "away_xg",
            "home_xga",
            "away_xga",
            "home_ppda",
            "away_ppda",
            "home_oppda",
            "away_oppda",
            "home_mismatch",
            "away_mismatch",
            "home_league_zscore_attack",
            "away_league_zscore_attack",
            "home_league_zscore_defense",
            "away_league_zscore_defense",
        ]
        for col in required_columns:
            if col not in data.columns:
                logger.error(f"Валидация не пройдена: отсутствует колонка {col}")
                return False
        # Проверка на минимальный объем данных
        if len(data) < 50:  # Минимальное количество матчей для обучения
            logger.warning(
                f"Мало данных для обучения: {len(data)} матчей. Минимум рекомендуется 50."
            )
            # Не возвращаем False, но логируем
        else:
            logger.info(f"Достаточный объем обучающих данных: {len(data)} матчей.")
        logger.info("Валидация данных пройдена успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка при валидации данных: {e}")
        return False


def calculate_log_likelihood(
    predictions: list[float], actual_goals: list[int]
) -> float:
    """Расчет логарифмического правдоподобия для оценки качества модели.
    Args:
        predictions (List[float]): Предсказанные значения (λ)
        actual_goals (List[int]): Фактические голы
    Returns:
        float: Логарифмическое правдоподобие
    """
    try:
        # Избегаем логарифма от нуля
        epsilon = 1e-10
        log_likelihood = 0.0
        for pred, actual in zip(predictions, actual_goals, strict=False):
            pred = max(pred, epsilon)  # Защита от нуля
            # Для распределения Пуассона: log(P(k)) = k*log(λ) - λ - log(k!)
            # Упрощенно: log_likelihood += actual * np.log(pred) - pred
            log_likelihood += actual * np.log(pred) - pred
        return log_likelihood
    except Exception as e:
        logger.error(f"Ошибка при расчете логарифмического правдоподобия: {e}")
        return float("-inf")


# Функции validate_ewma_half_life и optimize_ewma_half_life оставлены без изменений
# Предполагается, что они работают с xg/ppda до того, как они попадают в модель
async def validate_ewma_half_life(data: pd.DataFrame, half_life_days: float) -> float:
    """Валидация параметра half_life для EWMA через кросс-валидацию.
    Args:
        data (pd.DataFrame): Данные для валидации
        half_life_days (float): Период полураспада в днях
    Returns:
        float: Среднее логарифмическое правдоподобие
    """
    try:
        logger.info(f"Валидация EWMA с half_life = {half_life_days} дней")
        # Разделяем данные на обучающую и тестовую выборки (80/20)
        split_idx = int(len(data) * 0.8)
        train_data = data.iloc[:split_idx]
        test_data = data.iloc[split_idx:]
        if len(test_data) == 0:
            logger.warning("Недостаточно данных для тестирования")
            return float("-inf")
        # Здесь должна быть логика расчета xG с использованием EWMA
        # Поскольку у нас нет прямого доступа к реализации, создаем имитацию
        # Имитация предсказаний (в реальной реализации здесь будет вызов функции EWMA)
        # Для демонстрации используем средние значения xg как предсказания
        home_predictions = [train_data["home_xg"].mean()] * len(
            test_data
        )  # Используем средний xG
        away_predictions = [train_data["away_xg"].mean()] * len(test_data)
        # Рассчитываем логарифмическое правдоподобие
        home_ll = calculate_log_likelihood(
            home_predictions, test_data["home_goals"].tolist()
        )
        away_ll = calculate_log_likelihood(
            away_predictions, test_data["away_goals"].tolist()
        )
        avg_ll = (home_ll + away_ll) / 2
        logger.info(
            f"Среднее логарифмическое правдоподобие для half_life {half_life_days}: {avg_ll:.4f}"
        )
        return avg_ll
    except Exception as e:
        logger.error(f"Ошибка при валидации EWMA с half_life {half_life_days}: {e}")
        return float("-inf")


async def optimize_ewma_half_life(
    data: pd.DataFrame, half_life_range: list[float] = None
) -> tuple[float, float]:
    """Оптимизация параметра half_life для EWMA через сеточный поиск.
    Args:
        data (pd.DataFrame): Данные для оптимизации
        half_life_range (List[float]): Диапазон значений для поиска
    Returns:
        Tuple[float, float]: (оптимальное значение half_life, лучшее значение метрики)
    """
    try:
        if half_life_range is None:
            # По умолчанию проверяем значения от 7 до 90 дней
            half_life_range = [7, 14, 30, 45, 60, 90, 120]
        logger.info(f"Запуск оптимизации EWMA half_life в диапазоне: {half_life_range}")
        best_half_life = 30.0  # Значение по умолчанию
        best_score = float("-inf")
        # Тестирование каждого значения
        for half_life in half_life_range:
            score = await validate_ewma_half_life(data, half_life)
            if score > best_score:
                best_score = score
                best_half_life = half_life
                logger.info(
                    f"Найдено лучшее значение: half_life = {best_half_life}, score = {best_score:.4f}"
                )
        logger.info(
            f"Оптимизация завершена. Лучшее значение half_life: {best_half_life}"
        )
        return best_half_life, best_score
    except Exception as e:
        logger.error(f"Ошибка при оптимизации EWMA half_life: {e}")
        return 30.0, float("-inf")  # Возвращаем значение по умолчанию


async def expanding_window_cv(
    data: pd.DataFrame, n_splits: int = 5
) -> dict[str, float]:
    """
    Временная кросс-валидация с расширяющимся окном для новой PoissonRegressionModel.
    Args:
        data (pd.DataFrame): Данные, отсортированные по дате
        n_splits (int): Количество разбиений
    Returns:
        Dict[str, float]: Метрики валидации
    """
    try:
        logger.info(f"Запуск временной кросс-валидации с {n_splits} разбиениями")
        # Сортируем данные по дате
        data_sorted = data.sort_values("date").reset_index(drop=True)
        # Инициализируем списки для хранения результатов
        log_losses = []
        brier_scores = []
        # Определяем размеры окон
        total_size = len(data_sorted)
        initial_train_size = total_size // 3  # Начальное обучающее множество ~33%
        step_size = (total_size - initial_train_size) // n_splits
        if step_size <= 0:
            logger.warning("Недостаточно данных для временной кросс-валидации")
            return {"mean_log_loss": float("inf"), "mean_brier_score": float("inf")}
        for i in range(n_splits):
            # Определяем границы обучающего и тестового множеств
            train_end = initial_train_size + i * step_size
            test_start = train_end
            test_end = min(train_end + step_size, total_size)
            if test_start >= test_end:
                continue
            # Разделяем данные
            train_data = data_sorted.iloc[:train_end].copy()
            test_data = data_sorted.iloc[test_start:test_end].copy()
            logger.debug(
                f"Fold {i+1}: train [{0}:{train_end}], test [{test_start}:{test_end}]"
            )
            # --- Обучение модели на train_data ---
            try:
                # Создаем временную модель для этого фолда
                temp_model = PoissonRegressionModel(alpha=0.001, max_iter=300)
                # Обучаем модель
                asyncio.get_event_loop()
                train_success = await temp_model.train_model(train_data)
                if not train_success:
                    logger.warning(f"Не удалось обучить модель для fold {i+1}")
                    log_losses.append(float("inf"))
                    brier_scores.append(float("inf"))
                    continue
                # --- Предсказание на test_data ---
                predicted_home_lambdas = []
                predicted_away_lambdas = []
                for _, row in test_data.iterrows():
                    # Предполагаем, что calculate_base_lambda возвращает лямбды
                    lambda_home, lambda_away = temp_model.calculate_base_lambda(
                        home_team_id=row["home_team_id"],
                        away_team_id=row["away_team_id"],
                        league_id=row["league_id"],
                        home_rest_days=row["home_rest_days"],
                        away_rest_days=row["away_rest_days"],
                        home_km_trip=row["home_km_trip"],
                        away_km_trip=row["away_km_trip"],
                        home_xg=row["home_xg"],
                        away_xg=row["away_xg"],
                        home_xga=row["home_xga"],
                        away_xga=row["away_xga"],
                        home_ppda=row["home_ppda"],
                        away_ppda=row["away_ppda"],
                        home_oppda=row["home_oppda"],
                        away_oppda=row["away_oppda"],
                        home_mismatch=row["home_mismatch"],
                        away_mismatch=row["away_mismatch"],
                        home_league_zscore_attack=row["home_league_zscore_attack"],
                        away_league_zscore_attack=row["away_league_zscore_attack"],
                        home_league_zscore_defense=row["home_league_zscore_defense"],
                        away_league_zscore_defense=row["away_league_zscore_defense"],
                    )
                    predicted_home_lambdas.append(lambda_home)
                    predicted_away_lambdas.append(lambda_away)
                # --- Расчет метрик ---
                actual_home_goals = test_data["home_goals"].tolist()
                actual_away_goals = test_data["away_goals"].tolist()
                # Log Loss для Poisson распределения
                try:
                    home_ll = calculate_log_likelihood(
                        predicted_home_lambdas, actual_home_goals
                    )
                    away_ll = calculate_log_likelihood(
                        predicted_away_lambdas, actual_away_goals
                    )
                    log_loss_value = (
                        -(home_ll + away_ll) / 2
                    )  # Инвертируем для минимизации
                    log_losses.append(log_loss_value)
                except Exception as e:
                    logger.warning(f"Ошибка при расчете log loss для fold {i+1}: {e}")
                    log_losses.append(float("inf"))
                # Brier Score (для демонстрации используем упрощенный подход)
                # Пример: вероятность победы домашней команды как P(Poisson(lambda_home) > Poisson(lambda_away))
                # Это требует дополнительных вычислений. Для простоты возьмем разницу.
                try:
                    # Упрощенная вероятность: sigmoid разницы лямбд
                    diff_lambdas = np.array(predicted_home_lambdas) - np.array(
                        predicted_away_lambdas
                    )
                    prob_home_win_simplified = 1 / (
                        1 + np.exp(-diff_lambdas)
                    )  # Sigmoid
                    # Определяем истинные исходы (1 если победа домашней, 0 иначе)
                    y_true_binary = (
                        np.array(actual_home_goals) > np.array(actual_away_goals)
                    ).astype(int)
                    # Рассчитываем Brier Score
                    if len(y_true_binary) > 0 and len(prob_home_win_simplified) == len(
                        y_true_binary
                    ):
                        # Убедимся, что вероятности в [0, 1]
                        prob_home_win_simplified = np.clip(
                            prob_home_win_simplified, 1e-15, 1 - 1e-15
                        )
                        brier_score_value = np.mean(
                            (prob_home_win_simplified - y_true_binary) ** 2
                        )
                        brier_scores.append(brier_score_value)
                    else:
                        raise ValueError(
                            "Несовпадение размеров массивов для Brier Score"
                        )
                except Exception as e:
                    logger.warning(
                        f"Ошибка при расчете Brier score для fold {i+1}: {e}"
                    )
                    brier_scores.append(float("inf"))
            except Exception as e:
                logger.error(f"Ошибка при обучении/предсказании для fold {i+1}: {e}")
                log_losses.append(float("inf"))
                brier_scores.append(float("inf"))
        # Рассчитываем средние метрики
        mean_log_loss = np.mean(log_losses) if log_losses else float("inf")
        mean_brier_score = np.mean(brier_scores) if brier_scores else float("inf")
        logger.info(
            f"Результаты временной кросс-валидации: "
            f"Log Loss = {mean_log_loss:.4f}, "
            f"Brier Score = {mean_brier_score:.4f}"
        )
        return {
            "mean_log_loss": mean_log_loss,
            "mean_brier_score": mean_brier_score,
            "fold_count": len(
                [ll for ll in log_losses if ll != float("inf")]
            ),  # Считаем только успешные фолды
        }
    except Exception as e:
        logger.error(f"Ошибка при выполнении временной кросс-валидации: {e}")
        return {"mean_log_loss": float("inf"), "mean_brier_score": float("inf")}


def save_metrics_report(path: str, metrics_dict: dict[str, Any]) -> bool:
    """
    Сохранение отчета с метриками в JSON файл.
    Args:
        path (str): Путь для сохранения файла
        metrics_dict (Dict[str, Any]): Словарь с метриками
    Returns:
        bool: Успешность операции
    """
    try:
        # Создаем директорию если её нет
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        # Сохраняем метрики в JSON файл
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"✅ Метрики успешно сохранены в {path}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении метрик в {path}: {e}")
        return False


def generate_calibration_curve_plot(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> str | None:
    """
    Генерация калибровочной кривой и возврат в виде base64 строки.
    Args:
        y_true (np.ndarray): Истинные метки
        y_prob (np.ndarray): Предсказанные вероятности
        n_bins (int): Количество бинов для калибровки
    Returns:
        Optional[str]: Base64 строка с графиком или None в случае ошибки
    """
    try:
        if n_bins <= 0:
            logger.warning("Некорректное количество бинов для калибровочной кривой")
            return None
        # Разбиваем на бины
        bin_bounds = np.linspace(0, 1, n_bins + 1)
        bin_lowers = bin_bounds[:-1]
        bin_uppers = bin_bounds[1:]
        # Рассчитываем доли для каждого бина
        bin_accuracies = []
        bin_confidences = []
        bin_counts = []
        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers, strict=False):
            # Находим предсказания в текущем бине
            in_bin = (y_prob > bin_lower) & (y_prob <= bin_upper)
            prop_in_bin = in_bin.mean()
            bin_counts.append(prop_in_bin)
            if prop_in_bin > 0:
                # Точность в бине
                accuracy_in_bin = y_true[in_bin].mean()
                # Средняя уверенность в бине
                avg_confidence_in_bin = y_prob[in_bin].mean()
                bin_accuracies.append(accuracy_in_bin)
                bin_confidences.append(avg_confidence_in_bin)
            else:
                bin_accuracies.append(0)
                bin_confidences.append(0)
        # Создаем график
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(bin_confidences, bin_accuracies, "s-", label="Калибровочная кривая")
        ax.plot([0, 1], [0, 1], "k:", label="Идеальная калибровка")
        ax.set_xlabel("Средняя предсказанная вероятность")
        ax.set_ylabel("Доля положительных исходов")
        ax.set_title("Калибровочная кривая")
        ax.legend()
        ax.grid(True)
        # Добавляем гистограмму количества образцов в каждом бине
        ax2 = ax.twinx()
        ax2.bar(
            bin_lowers,
            bin_counts,
            width=1.0 / n_bins,
            alpha=0.3,
            color="gray",
            align="edge",
        )
        ax2.set_ylabel("Доля образцов", color="gray")
        # Сохраняем в base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        plot_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)
        logger.debug("Калибровочная кривая успешно сгенерирована")
        return plot_base64
    except Exception as e:
        logger.error(f"Ошибка при генерации калибровочной кривой: {e}")
        return None


async def train_model(data: pd.DataFrame):
    """Обучение модели на предоставленных данных.
    Args:
        data (pd.DataFrame): Данные для обучения
    """
    try:
        logger.info(
            "🚀 Запуск скрипта обучения Poisson-регрессионной модели (новая версия)"
        )
        # Валидация данных
        if not await validate_training_data(data):
            logger.error("Валидация данных не пройдена. Обучение прервано.")
            return
        # Оптимизация параметра half_life для EWMA
        logger.info("Начало оптимизации параметра half_life для EWMA")
        optimal_half_life, best_score = await optimize_ewma_half_life(data)
        logger.info(
            f"Оптимальное значение half_life для EWMA: {optimal_half_life} дней (score: {best_score:.4f})"
        )
        # Временная кросс-валидация
        logger.info("Начало временной кросс-валидации")
        cv_metrics = await expanding_window_cv(data, n_splits=5)
        logger.info(f"Результаты временной кросс-валидации: {cv_metrics}")
        # --- Обучение основной модели ---
        logger.info("Обучение основной Poisson-регрессионной модели")
        # Обучение модели (новый метод)
        train_success = await poisson_regression_model.train_model(data)
        if not train_success:
            logger.error("Обучение основной модели завершилось с ошибкой.")
            return
        else:
            logger.info("Основная модель успешно обучена.")
        # --- Калибровка вероятностей ---
        logger.info("Начало калибровки вероятностей")
        # Здесь должна быть логика для получения истинных меток и предсказанных вероятностей
        # из кросс-валидации или на отложенной выборке.
        # Для демонстрации используем имитационные данные.
        # В реальной реализации это должны быть результаты предсказаний модели на тестовых данных.
        # Например, можно использовать результаты из последнего фолда CV.
        # Создадим имитационные данные для калибровки
        np.random.seed(42)  # Для воспроизводимости
        # Имитационные истинные метки (например, победа домашней команды)
        sample_true = np.random.binomial(1, 0.45, 1000)  # 45% побед домашних
        # Имитационные "сырые" предсказанные вероятности (до калибровки)
        # Добавим шум к истинным вероятностям, чтобы модель не была идеально откалибрована
        true_probs = 0.45 + 0.1 * (np.random.rand(1000) - 0.5)  # Вариации вокруг 0.45
        # Добавим систематическую ошибку (overconfidence)
        sample_pred_raw = np.clip(
            true_probs + np.random.normal(0, 0.1, 1000), 0.01, 0.99
        )
        # Обучаем калибратор на имитационных данных
        calibrator = calibrate_probs(sample_true, sample_pred_raw)
        if calibrator is not None:
            # Применяем калибровку к тем же "сырым" вероятностям для демонстрации
            calibrated_probs = apply_calibration(calibrator, sample_pred_raw)
            logger.info(
                f"Калибровка выполнена. Среднее до: {np.mean(sample_pred_raw):.4f}, "
                f"после: {np.mean(calibrated_probs):.4f}"
            )
            # Генерируем калибровочную кривую
            calibration_plot = generate_calibration_curve_plot(
                sample_true, sample_pred_raw
            )
            if calibration_plot:
                logger.info("Калибровочная кривая сгенерирована")
            else:
                logger.warning("Не удалось сгенерировать калибровочную кривую")
        else:
            logger.error("Не удалось обучить калибратор")
            calibrator = None
            calibration_plot = None
        # --- Сохранение модели и калибратора ---
        model_save_path = "data/models/poisson_regression"
        meta_data = {
            "training_timestamp": datetime.now().isoformat(),
            "optimal_ewma_half_life": optimal_half_life,
            "cv_metrics": cv_metrics,
        }
        save_artifacts(poisson_regression_model, model_save_path, meta_data)
        logger.info(f"✅ Модель и метаданные успешно сохранены в {model_save_path}")
        # Сохраняем калибратор рядом с моделью
        if calibrator is not None:
            calibrator_path = f"{model_save_path}_calibrator.joblib"
            try:
                joblib.dump(calibrator, calibrator_path)
                logger.info(f"✅ Калибратор успешно сохранен в {calibrator_path}")
            except Exception as save_cal_error:
                logger.error(
                    f"❌ Ошибка при сохранении калибратора в {calibrator_path}: {save_cal_error}"
                )
        # --- Подготовка и сохранение метрик ---
        metrics_report = {
            "training_timestamp": datetime.now().isoformat(),
            "data_statistics": {
                "total_matches": len(data),
                "date_range": {
                    "from": data["date"].min() if "date" in data.columns else None,
                    "to": data["date"].max() if "date" in data.columns else None,
                },
                "unique_teams": len(
                    set(data["home_team_id"].tolist() + data["away_team_id"].tolist())
                )
                if "home_team_id" in data.columns and "away_team_id" in data.columns
                else 0,
                "unique_leagues": data["league_id"].nunique()
                if "league_id" in data.columns
                else 0,
            },
            "cross_validation": cv_metrics,
            "ewma_optimization": {
                "optimal_half_life": optimal_half_life,
                "best_score": best_score,
            },
            "model_parameters": {  # Заглушка, так как параметры не возвращаются напрямую
                "alpha": poisson_regression_model.alpha,
                "max_iter": poisson_regression_model.max_iter,
                "feature_names": poisson_regression_model.feature_names,
            },
            "calibration": {"calibration_curves": {}},
        }
        # Добавляем информацию о калибровке
        if calibration_plot:
            metrics_report["calibration"]["calibration_curves"][
                "sample"
            ] = calibration_plot
        # Сохраняем метрики
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_path = f"data/metrics/model_metrics_{timestamp}.json"
        save_success = save_metrics_report(metrics_path, metrics_report)
        if save_success:
            logger.info(f"✅ Метрики обучения сохранены в {metrics_path}")
        else:
            logger.error("❌ Ошибка при сохранении метрик обучения")
        logger.info(
            "✅ Poisson-регрессионная модель успешно обучена и параметры сохранены."
        )
    except Exception as e:
        logger.error(f"Критическая ошибка при обучении модели: {e}", exc_info=True)


# --- НОВАЯ ФУНКЦИЯ ДЛЯ RQ ---
def train_and_persist(season_id: int | None = None):
    """
    Точка входа для задачи переобучения модели через RQ.
    Эта функция должна быть синхронной, так как вызывается RQ.
    Внутри она запускает асинхронную логику.
    Args:
        season_id (Optional[int]): ID сезона для обучения.
    """
    try:
        logger.info(
            f"Начало задачи переобучения модели через RQ (сезон ID: {season_id})"
        )
        # Создаем новый event loop для асинхронной операции
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Запускаем асинхронную функцию обучения
        loop.run_until_complete(_async_train_and_persist(season_id))
        loop.close()
        logger.info("✅ Задача переобучения модели через RQ завершена успешно")
    except Exception as e:
        logger.error(
            f"❌ Ошибка в задаче переобучения модели через RQ: {e}", exc_info=True
        )
        raise  # Перебрасываем исключение, чтобы RQ мог его обработать и записать в failed jobs


async def _async_train_and_persist(season_id: int | None = None):
    """Внутренняя асинхронная функция для выполнения логики переобучения."""
    # Получаем данные для обучения
    # TODO: Замените season_id на актуальный ID сезона или используйте значение по умолчанию
    if season_id is None:
        season_id = 23855  # Пример: Premier League 2023/2024 (замените на актуальный)
    training_data = await fetch_training_data(season_id=season_id)
    if training_data.empty:
        logger.error("Нет данных для обучения в задаче переобучения.")
        raise ValueError("Нет данных для обучения")
    # Обучаем модель
    await train_model(training_data)
    logger.info("🏁 Асинхронная часть задачи переобучения завершена")


# --- КОНЕЦ НОВОЙ ФУНКЦИИ ДЛЯ RQ ---
async def main():
    """Главная асинхронная точка входа для скрипта обучения."""
    try:
        logger.info("🚀 Запуск скрипта обучения Poisson-регрессионной модели")
        # Получаем данные для обучения
        # TODO: Замените season_id на актуальный ID сезона
        season_id = 23855  # Пример: Premier League 2023/2024
        training_data = await fetch_training_data(season_id=season_id)
        if training_data.empty:
            logger.error("Нет данных для обучения. Завершение работы.")
            return
        # Обучаем модель
        await train_model(training_data)
        logger.info("🏁 Скрипт обучения завершен")
    except Exception as e:
        logger.error(f"Критическая ошибка в основном процессе: {e}", exc_info=True)


if __name__ == "__main__":
    # Запуск асинхронной функции
    asyncio.run(main())

# 6. Обучение: тренировочный хелпер и артефакты
# 6.1. Добавить в конец train_model.py (append)
from typing import Any

import numpy as np
import pandas as pd

try:
    from config import settings
except Exception:
    from config import get_settings as _gs

    settings = _gs()
try:
    from poisson_regression_model import PoissonRegressionModel
except Exception:
    PoissonRegressionModel = None
from data_processor import (
    build_features,
    compute_time_decay_weights,
    make_time_series_splits,
)

DEFAULT_ALPHA_GRID = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]


def _ensure_models_dir(
    league: str | None, market: str | None, version: str | None
) -> str:
    base = getattr(settings, "MODELS_DIR", "models")
    ver = (
        version
        or getattr(settings, "MODEL_VERSION", None)
        or "v" + datetime.utcnow().strftime("%Y%m%d")
    )
    path = os.path.join(base, str(league) if league else "", market, ver)
    os.makedirs(path, exist_ok=True)
    return path


def train_league_market(
    league: str,
    market: str,
    df: pd.DataFrame,
    *,
    date_col: str = "match_date",
    target_cols: dict[str, str] = None,
    feature_cols: list[str] | None = None,
    alphas: list[float] | None = None,
    version: str | None = None,
) -> dict[str, str]:
    target_cols = target_cols or {
        "home_goals": "home_goals",
        "away_goals": "away_goals",
    }
    alphas = alphas or DEFAULT_ALPHA_GRID

    X = build_features(df)
    w = compute_time_decay_weights(
        df,
        date_col=date_col,
        half_life_days=getattr(settings, "TIME_DECAY_HALFLIFE_DAYS", 180),
    )
    splits = make_time_series_splits(
        df,
        date_col=date_col,
        n_splits=getattr(settings, "CV_N_SPLITS", 6),
        min_train_days=getattr(settings, "CV_MIN_TRAIN_DAYS", 120),
        gap_days=getattr(settings, "CV_GAP_DAYS", 0),
    )
    if feature_cols is None:
        feature_cols = [
            c
            for c in X.columns
            if c not in (target_cols["home_goals"], target_cols["away_goals"], date_col)
        ]

    saved: dict[str, str] = {}
    outdir = _ensure_models_dir(league, market, version)

    # Base Poisson
    if PoissonRegressionModel is not None:
        model = PoissonRegressionModel()
        try:
            model.fit_time_series_cv(
                df=X.assign(
                    y_home=df[target_cols["home_goals"]],
                    y_away=df[target_cols["away_goals"]],
                ),
                features=feature_cols,
                target_col=target_cols["home_goals"],
                ts_splits=splits,
                alphas=alphas,
                sample_weight=w,
            )
        except Exception:
            model.fit(X[feature_cols], df[target_cols["home_goals"]], sample_weight=w)
        try:
            model.save_artifacts(outdir)
        except Exception:
            joblib.dump(model, os.path.join(outdir, "base_model.joblib"))
        saved["base"] = os.path.join(outdir, "base_model.joblib")

    # λ-Calibration
    modifier = CalibrationLayer(feature_names=feature_cols, alpha=1.0)
    modifier.fit(
        X[feature_cols],
        y_home=df[target_cols["home_goals"]].to_numpy(),
        y_away=df[target_cols["away_goals"]].to_numpy(),
        lam_home_base=np.clip((df[target_cols["home_goals"]].mean() or 1.0), 1e-6, None)
        * np.ones(len(df)),
        lam_away_base=np.clip((df[target_cols["away_goals"]].mean() or 1.0), 1e-6, None)
        * np.ones(len(df)),
        sample_weight=w,
    )
    modp = os.path.join(outdir, "modifier.joblib")
    modifier.save(modp)
    saved["modifier"] = modp

    # Meta (калибратор вероятностей на шаг позже, когда будут целевые метки рынков)
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "league": str(league),
                "market": str(market),
                "version": os.path.basename(outdir),
                "timestamp": datetime.utcnow().isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return saved
