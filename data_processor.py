from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence

try:  # pragma: no cover - optional dependency guard
    import pandas as pd  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    pd = None  # type: ignore[assignment]


def parse_dt_safe(date_str: str) -> datetime | None:
    """Парсинг даты с обработкой ошибок."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Ошибка парсинга даты: {e}")
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками на Земле по формуле Хаверсина."""
    R = 6371  # Радиус Земли в километрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compute_rest_days(match_date: datetime, player_last_match: datetime) -> int:
    """Вычисление числа дней отдыха между матчами игрока."""
    return (match_date - player_last_match).days


def style_mismatch(team_style: str, opponent_style: str) -> float:
    """Расчёт коэффициента различия стилей команд."""
    if team_style == opponent_style:
        return 0
    return 1


def ewma(values: list[float], alpha: float) -> float:
    """Рассчёт экспоненциального скользящего среднего."""
    smoothed_value = values[0]
    for value in values[1:]:
        smoothed_value = alpha * value + (1 - alpha) * smoothed_value
    return smoothed_value


def add_missing_ratio(df) -> float:
    """Рассчитываем коэффициент пропусков для данных."""
    total_entries = df.size
    missing_entries = df.isnull().sum().sum()
    return missing_entries / total_entries


def load_climate_norm(location: str) -> dict:
    """Загрузка норм климатических данных по местоположению."""
    # Для примера возвращаем статичные данные
    return {
        "temperature": 25,  # Средняя температура
        "humidity": 60,  # Средняя влажность
    }


def build_features(frame):
    """Basic feature engineering placeholder used in offline QA flows."""

    if pd is None or not isinstance(frame, pd.DataFrame):  # pragma: no cover - offline stub
        return frame

    df = frame.copy()
    numeric_cols = [
        "home_goals",
        "away_goals",
        "home_xg",
        "away_xg",
        "home_form",
        "away_form",
    ]
    for column in numeric_cols:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    if {"home_goals", "away_goals"}.issubset(df.columns):
        df["goal_diff"] = df["home_goals"] - df["away_goals"]
        df["total_goals"] = df["home_goals"] + df["away_goals"]
    if {"home_form", "away_form"}.issubset(df.columns):
        df["form_delta"] = df["home_form"] - df["away_form"]
    df = df.fillna(0)
    return df


def compute_time_decay_weights(
    timestamps: Sequence[datetime | None], *, halflife_days: float = 180.0
) -> list[float]:
    """Return exponential decay weights for chronological samples."""

    if not timestamps:
        return []
    valid_times = [ts for ts in timestamps if isinstance(ts, datetime)]
    if not valid_times:
        return [1.0 for _ in timestamps]
    reference = max(valid_times)
    halflife = max(halflife_days, 1e-6)
    weights: list[float] = []
    for ts in timestamps:
        if not isinstance(ts, datetime):
            weights.append(1.0)
            continue
        delta_days = (reference - ts).total_seconds() / 86400.0
        weight = 0.5 ** (delta_days / halflife)
        weights.append(float(weight))
    return weights


def make_time_series_splits(
    timestamps: Sequence[datetime | None], *, n_splits: int = 3, min_train_size: int = 30
) -> list[tuple[list[int], list[int]]]:
    """Generate chronological train/test index splits."""

    total = len(timestamps)
    if total == 0 or total <= min_train_size:
        return []
    ordered = sorted(
        enumerate(timestamps),
        key=lambda item: (
            item[1] if isinstance(item[1], datetime) else datetime.min,
            item[0],
        ),
    )
    step = max(1, (total - min_train_size) // max(n_splits, 1))
    splits: list[tuple[list[int], list[int]]] = []
    for end in range(min_train_size, total, step):
        train_indices = [idx for idx, _ in ordered[:end]]
        test_indices = [idx for idx, _ in ordered[end : end + step]]
        if not test_indices:
            continue
        splits.append((sorted(train_indices), sorted(test_indices)))
    if not splits:
        train_indices = [idx for idx, _ in ordered[: total - 1]]
        test_indices = [ordered[-1][0]]
        splits.append((sorted(train_indices), [test_indices[0]]))
    return splits
