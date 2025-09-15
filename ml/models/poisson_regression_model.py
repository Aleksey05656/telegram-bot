# ml/models/poisson_regression_model.py
import json
import os
from typing import Any

import numpy as np
import pandas as pd

from logger import logger

# Попытка импорта sklearn
try:
    from sklearn.linear_model import PoissonRegressor
    from sklearn.preprocessing import StandardScaler

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("sklearn не установлен. Обучение модели будет недоступно.")
# === НОВЫЕ ФУНКЦИИ ДЛЯ ЭТАПА 3 ===
# 3.2. Time-CV + артефакты в poisson_regression_model.py
# В конец poisson_regression_model.py:
from dataclasses import dataclass

import joblib


@dataclass
class CVFoldMetrics:
    fold_id: int
    alpha: float
    logloss: float
    brier: float | None = None


@dataclass
class CVResult:
    best_alpha: float
    folds: list[CVFoldMetrics]
    best_model: Any


def save_artifacts(model, path: str, meta: dict | None = None) -> None:
    os.makedirs(path, exist_ok=True)
    joblib.dump(model, os.path.join(path, "base_model.joblib"))
    if meta is not None:
        import json

        with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


def load_artifacts(path: str):
    return joblib.load(os.path.join(path, "base_model.joblib"))


# === КОНЕЦ НОВЫХ ФУНКЦИЙ ===
class PoissonRegressionModel:
    """Poisson-регрессионная модель для прогнозирования футбольных матчей с использованием sklearn."""

    def __init__(self, alpha: float = 0.001, max_iter: int = 300):
        """Инициализация Poisson-регрессионной модели.
        Args:
            alpha (float): Параметр регуляризации для PoissonRegressor.
            max_iter (int): Максимальное количество итераций для PoissonRegressor.
        """
        self.alpha = alpha
        self.max_iter = max_iter
        self.scaler = None
        self.model_home = None
        self.model_away = None
        self.feature_names = []
        # Словарь для хранения p99 значений по лигам
        self.league_p99 = {}
        # Словари для хранения мэппингов
        self.league_hash_map = {}  # league_id -> hash
        self.team_hash_map = {}  # team_id -> hash
        # Атрибут для хранения рейтингов команд
        self.team_ratings = {}
        logger.info(
            f"Инициализация Poisson-регрессионной модели (sklearn). Alpha: {alpha}, Max_iter: {max_iter}"
        )

    # === ДОБАВЛЕН МЕТОД load_ratings ===
    def load_ratings(self, filepath: str = "data/team_ratings.json"):
        """
        Загружает рейтинги команд из JSON файла.
        Args:
            filepath (str): Путь к файлу с рейтингами. По умолчанию "data/team_ratings.json".
        """
        try:
            if os.path.exists(filepath):
                with open(filepath, encoding="utf-8") as f:
                    self.team_ratings = json.load(f)
                logger.info(f"Рейтинги команд загружены из {filepath}")
                # Опционально можно обновить team_hash_map, если рейтинги влияют на него.
            else:
                logger.warning(
                    f"Файл с рейтингами {filepath} не найден. team_ratings останется пустым."
                )
                self.team_ratings = {}
        except Exception as e:
            logger.error(f"Ошибка при загрузке рейтингов из {filepath}: {e}")
            # Можно выбросить исключение или оставить self.team_ratings пустым
            self.team_ratings = {}  # Оставляем пустым в случае ошибки

    # === КОНЕЦ ДОБАВЛЕНИЯ ===

    def _hash_value(self, value: Any, max_hash: int = 1000) -> int:
        """
        Простая хэш-функция для категориальных признаков.
        Args:
            value (Any): Значение для хэширования
            max_hash (int): Максимальное значение хэша
        Returns:
            int: Хэш-значение
        """
        try:
            # Преобразуем значение в строку и вычисляем хэш
            hash_val = hash(str(value)) % max_hash
            # Убеждаемся, что хэш положительный
            return abs(hash_val)
        except Exception as e:
            logger.error(f"Ошибка при хэшировании значения {value}: {e}")
            return 0

    def prepare_features(
        self, df: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
        """
        Подготовка признаков для обучения модели.
        Args:
            df (pd.DataFrame): Исходные данные о матчах.
        Returns:
            Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]: (X_home, y_home, X_away, y_away, feature_names)
        """
        try:
            required_columns = [
                "home_team_id",
                "away_team_id",
                "home_goals",
                "away_goals",
                "league_id",
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
            if not all(col in df.columns for col in required_columns):
                missing = [col for col in required_columns if col not in df.columns]
                logger.error(f"Отсутствуют обязательные колонки: {missing}")
                return np.array([]), np.array([]), np.array([]), np.array([]), []
            df_clean = df.dropna(subset=required_columns).copy()
            if df_clean.empty:
                logger.warning("Нет данных для подготовки признаков после очистки")
                return np.array([]), np.array([]), np.array([]), np.array([]), []
            # Создаем хэши для лиг и команд, если они еще не созданы
            for league_id in df_clean["league_id"].unique():
                if league_id not in self.league_hash_map:
                    self.league_hash_map[league_id] = self._hash_value(league_id)
            for team_id in df_clean["home_team_id"].unique():
                if team_id not in self.team_hash_map:
                    self.team_hash_map[team_id] = self._hash_value(team_id)
            for team_id in df_clean["away_team_id"].unique():
                if team_id not in self.team_hash_map:
                    self.team_hash_map[team_id] = self._hash_value(team_id)
            # Создаем признаки взаимодействия
            df_clean["league_id_hash"] = df_clean["league_id"].map(self.league_hash_map)
            df_clean["home_team_id_hash"] = df_clean["home_team_id"].map(self.team_hash_map)
            df_clean["away_team_id_hash"] = df_clean["away_team_id"].map(self.team_hash_map)
            df_clean["home_league_interaction"] = (
                df_clean["home_team_id_hash"] * df_clean["league_id_hash"]
            )
            df_clean["away_league_interaction"] = (
                df_clean["away_team_id_hash"] * df_clean["league_id_hash"]
            )
            # Определяем непрерывные признаки
            continuous_features = [
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
            # Определяем категориальные признаки (хэшированные)
            categorical_features = [
                "home_team_id_hash",
                "away_team_id_hash",
                "league_id_hash",
                "home_league_interaction",
                "away_league_interaction",
            ]
            # Объединяем все признаки
            all_features = continuous_features + categorical_features
            # Создаем признаки для домашней и гостевой команд
            # Домашняя команда предсказывает свои голы
            home_feature_data = df_clean[continuous_features + categorical_features].copy()
            # Поменяем местами некоторые признаки, чтобы они отражали перспективу домашней команды
            # Например, для предсказания голов домашней команды, мы используем её атаку и оборону соперника
            # Это требует переформулировки признаков. Пример ниже - упрощенный вариант.
            # Предположим, что входные данные уже подготовлены с учетом перспективы.
            # То есть, home_xg - это xG домашней команды, away_xga - это xGA гостевой команды (которая является атакой соперника для домашней)
            # Аналогично для остальных.
            # Для домашней модели: цель - home_goals, признаки - домашние и гостевые (как оборона)
            X_home = home_feature_data.values
            y_home = df_clean["home_goals"].values
            # Для гостевой модели: цель - away_goals, признаки - гостевые и домашние (как оборона)
            # Аналогично, предполагаем, что данные подготовлены корректно.
            away_feature_data = df_clean[continuous_features + categorical_features].copy()
            X_away = away_feature_data.values
            y_away = df_clean["away_goals"].values
            logger.info(
                f"Подготовлены признаки: {len(X_home)} домашних, {len(X_away)} гостевых записей."
            )
            return X_home, y_home, X_away, y_away, all_features
        except Exception as e:
            logger.error(f"Ошибка при подготовке признаков: {e}")
            return np.array([]), np.array([]), np.array([]), np.array([]), []

    def prepare_features_for_match(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        home_rest_days: float,
        away_rest_days: float,
        home_km_trip: float,
        away_km_trip: float,
        home_xg: float,
        away_xg: float,
        home_xga: float,
        away_xga: float,
        home_ppda: float,
        away_ppda: float,
        home_oppda: float,
        away_oppda: float,
        home_mismatch: float,
        away_mismatch: float,
        home_league_zscore_attack: float,
        away_league_zscore_attack: float,
        home_league_zscore_defense: float,
        away_league_zscore_defense: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Подготовка признаков для одного матча.
        Args:
             Все параметры описывают состояние команд перед матчем.
        Returns:
            Tuple[np.ndarray, np.ndarray]: (X_home_single, X_away_single) - признаки для домашней и гостевой команд.
        """
        try:
            # Создаем хэши, если их еще нет
            if league_id not in self.league_hash_map:
                self.league_hash_map[league_id] = self._hash_value(league_id)
            if home_team_id not in self.team_hash_map:
                self.team_hash_map[home_team_id] = self._hash_value(home_team_id)
            if away_team_id not in self.team_hash_map:
                self.team_hash_map[away_team_id] = self._hash_value(away_team_id)
            league_id_hash = self.league_hash_map[league_id]
            home_team_id_hash = self.team_hash_map[home_team_id]
            away_team_id_hash = self.team_hash_map[away_team_id]
            home_league_interaction = home_team_id_hash * league_id_hash
            away_league_interaction = away_team_id_hash * league_id_hash
            # Подготавливаем признаки в том же порядке, что и при обучении
            continuous_features_home = [
                home_rest_days,
                away_rest_days,
                home_km_trip,
                away_km_trip,
                home_xg,
                away_xg,
                home_xga,
                away_xga,
                home_ppda,
                away_ppda,
                home_oppda,
                away_oppda,
                home_mismatch,
                away_mismatch,
                home_league_zscore_attack,
                away_league_zscore_attack,
                home_league_zscore_defense,
                away_league_zscore_defense,
            ]
            categorical_features_home = [
                home_team_id_hash,
                away_team_id_hash,
                league_id_hash,
                home_league_interaction,
                away_league_interaction,
            ]
            continuous_features_away = [
                away_rest_days,
                home_rest_days,
                away_km_trip,
                home_km_trip,  # Переставлены rest_days и km_trip
                away_xg,
                home_xg,
                away_xga,
                home_xga,  # Переставлены xg, xga
                away_ppda,
                home_ppda,
                away_oppda,
                home_oppda,  # Переставлены ppda, oppda
                away_mismatch,
                home_mismatch,  # Переставлен mismatch
                away_league_zscore_attack,
                home_league_zscore_attack,  # Переставлены zscore_attack
                away_league_zscore_defense,
                home_league_zscore_defense,  # Переставлены zscore_defense
            ]
            categorical_features_away = [
                away_team_id_hash,
                home_team_id_hash,
                league_id_hash,  # Переставлены team hashes
                away_league_interaction,
                home_league_interaction,  # Переставлены interactions
            ]
            X_home_single = np.array(continuous_features_home + categorical_features_home).reshape(
                1, -1
            )
            X_away_single = np.array(continuous_features_away + categorical_features_away).reshape(
                1, -1
            )
            return X_home_single, X_away_single
        except Exception as e:
            logger.error(f"Ошибка при подготовке признаков для матча: {e}")
            # Возвращаем нулевые массивы той же формы
            feature_count = (
                len(self.feature_names) if self.feature_names else 23
            )  # Примерное количество признаков
            return np.zeros((1, feature_count)), np.zeros((1, feature_count))

    def calculate_league_p99(self, matches_df: pd.DataFrame) -> dict[int, float]:
        """
        Расчет 99-го перцентиля ожидаемых голов по лигам.
        Args:
            matches_df (pd.DataFrame): Данные о матчах
        Returns:
            Dict[int, float]: Словарь {league_id: p99_lambda}
        """
        try:
            logger.info("Расчет 99-го перцентиля ожидаемых голов по лигам")
            # Группируем данные по лигам
            league_p99 = {}
            for league_id in matches_df["league_id"].unique():
                # Фильтруем данные по лиге
                league_data = matches_df[matches_df["league_id"] == league_id]
                if len(league_data) >= 10:  # Минимум 10 матчей для расчета
                    # Рассчитываем базовые λ для всех матчей в лиге
                    lambda_values = []
                    for _, row in league_data.iterrows():
                        home_team = row["home_team_id"]  # Используем ID
                        away_team = row["away_team_id"]  # Используем ID
                        # Рассчитываем базовые λ (простая оценка)
                        home_avg = league_data[league_data["home_team_id"] == home_team][
                            "home_goals"
                        ].mean()
                        away_avg = league_data[league_data["away_team_id"] == away_team][
                            "away_goals"
                        ].mean()
                        if not np.isnan(home_avg) and not np.isnan(away_avg):
                            lambda_values.extend([home_avg, away_avg])
                    if lambda_values:
                        # Рассчитываем 99-й перцентиль
                        p99 = np.percentile(lambda_values, 99)
                        league_p99[league_id] = float(p99)
                        logger.debug(
                            f"Лига {league_id}: p99 = {p99:.3f} (на основе {len(lambda_values)} значений)"
                        )
                else:
                    # Если недостаточно данных, используем значение по умолчанию
                    league_p99[league_id] = 5.0
                    logger.debug(f"Лига {league_id}: недостаточно данных, p99 = 5.0")
            self.league_p99 = league_p99
            logger.info(f"Рассчитаны p99 значения для {len(league_p99)} лиг")
            return league_p99
        except Exception as e:
            logger.error(f"Ошибка при расчете p99 по лигам: {e}")
            return {}

    def dynamic_cap(self, lam: float, p99: float) -> float:
        """
        Динамическое ограничение значения λ.
        Args:
            lam (float): Исходное значение λ
            p99 (float): 99-й перцентиль для лиги
        Returns:
            float: Ограниченное значение λ
        """
        try:
            capped_lambda = min(lam, p99)
            if lam > p99:
                logger.debug(
                    f"Ограничено значение λ: {lam:.3f} -> {capped_lambda:.3f} (p99={p99:.3f})"
                )
            return capped_lambda
        except Exception as e:
            logger.error(f"Ошибка при применении динамического ограничения: {e}")
            return lam

    async def train_model(self, training_data: pd.DataFrame) -> bool | None:
        """Обучение Poisson-регрессионной модели.
        Args:
            training_data (pd.DataFrame): Подготовленные данные для обучения
        Returns:
            Optional[bool]: True если обучение успешно, иначе None
        """
        if not HAS_SKLEARN:
            logger.error("sklearn не установлен. Невозможно обучить модель.")
            return None
        try:
            logger.info("Обучение Poisson-регрессионной модели (sklearn)")
            # Проверка наличия данных
            if training_data.empty:
                logger.error("Пустой набор данных для обучения")
                return None
            # Подготовка признаков
            X_home, y_home, X_away, y_away, feature_names = self.prepare_features(training_data)
            if len(X_home) == 0 or len(X_away) == 0:
                logger.error("Не удалось подготовить признаки для обучения.")
                return None
            self.feature_names = feature_names
            # Инициализация scaler и моделей
            self.scaler = StandardScaler()
            self.model_home = PoissonRegressor(alpha=self.alpha, max_iter=self.max_iter)
            self.model_away = PoissonRegressor(alpha=self.alpha, max_iter=self.max_iter)
            # Масштабирование признаков
            X_home_scaled = self.scaler.fit_transform(X_home)
            X_away_scaled = self.scaler.transform(X_away)  # Используем тот же scaler
            # Обучение моделей
            logger.info("Обучение модели для домашней команды...")
            self.model_home.fit(X_home_scaled, y_home)
            logger.info("Обучение модели для гостевой команды...")
            self.model_away.fit(X_away_scaled, y_away)
            # Расчет league p99 (если нужно для dynamic_cap)
            self.calculate_league_p99(training_data)
            logger.info("Модель успешно обучена")
            return True
        except Exception as e:
            logger.error(f"Критическая ошибка при обучении модели: {e}")
            return None

    def calculate_base_lambda(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        home_rest_days: float,
        away_rest_days: float,
        home_km_trip: float,
        away_km_trip: float,
        home_xg: float,
        away_xg: float,
        home_xga: float,
        away_xga: float,
        home_ppda: float,
        away_ppda: float,
        home_oppda: float,
        away_oppda: float,
        home_mismatch: float,
        away_mismatch: float,
        home_league_zscore_attack: float,
        away_league_zscore_attack: float,
        home_league_zscore_defense: float,
        away_league_zscore_defense: float,
        league_avg_goals: float = 2.5,  # Не используется напрямую, но оставлен для совместимости
    ) -> tuple[float, float]:
        """Расчет базовых параметров λ (лямбда) для домашней и гостевой команд.
        Args:
            Все параметры описывают состояние команд перед матчем.
            league_avg_goals (float): Среднее количество голов в лиге (не используется напрямую).
        Returns:
            Tuple[float, float]: (λ_домашней_команды, λ_гостевой_команды)
        """
        try:
            # Проверяем наличие обученных компонентов
            if (
                self.scaler is None
                or self.model_home is None
                or self.model_away is None
                or not self.feature_names
            ):
                logger.warning(
                    "Модель не обучена или отсутствуют компоненты. Используются усредненные значения."
                )
                return league_avg_goals, league_avg_goals
            # Подготовка признаков для конкретного матча
            X_home_single, X_away_single = self.prepare_features_for_match(
                home_team_id,
                away_team_id,
                league_id,
                home_rest_days,
                away_rest_days,
                home_km_trip,
                away_km_trip,
                home_xg,
                away_xg,
                home_xga,
                away_xga,
                home_ppda,
                away_ppda,
                home_oppda,
                away_oppda,
                home_mismatch,
                away_mismatch,
                home_league_zscore_attack,
                away_league_zscore_attack,
                home_league_zscore_defense,
                away_league_zscore_defense,
            )
            # Масштабирование признаков
            X_home_scaled = self.scaler.transform(X_home_single)
            X_away_scaled = self.scaler.transform(X_away_single)
            # Предсказание логарифмов λ
            log_lambda_home = self.model_home.predict(X_home_scaled)[0]
            log_lambda_away = self.model_away.predict(X_away_scaled)[0]
            # Преобразование из логарифма и ограничение
            lambda_home = np.clip(np.exp(log_lambda_home), 0.01, None)
            lambda_away = np.clip(np.exp(log_lambda_away), 0.01, None)
            # Применяем динамическое ограничение, если доступны p99 значения
            if league_id in self.league_p99:
                p99 = self.league_p99[league_id]
                lambda_home = self.dynamic_cap(lambda_home, p99)
                lambda_away = self.dynamic_cap(lambda_away, p99)
            else:
                # Ограничение по умолчанию
                lambda_home = min(lambda_home, 6.0)
                lambda_away = min(lambda_away, 6.0)
            logger.debug(f"Рассчитаны λ: домашняя={lambda_home:.3f}, гостевая={lambda_away:.3f}")
            return lambda_home, lambda_away
        except Exception as e:
            logger.error(f"Ошибка при расчете базовых λ: {e}")
            # Возвращаем значения по умолчанию в случае ошибки
            return league_avg_goals, league_avg_goals


# Создание экземпляра модели
poisson_regression_model = PoissonRegressionModel()
