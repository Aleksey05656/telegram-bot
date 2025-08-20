# data_processor.py

import numpy as np
from typing import List, Optional
from datetime import datetime

def parse_dt_safe(date_str: str) -> Optional[datetime]:
    """Парсинг даты с обработкой ошибок."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Ошибка парсинга даты: {e}")
        return None

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками на Земле по формуле Хаверсина."""
    R = 6371  # Радиус Земли в километрах
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)

    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

def compute_rest_days(match_date: datetime, player_last_match: datetime) -> int:
    """Вычисление числа дней отдыха между матчами игрока."""
    return (match_date - player_last_match).days

def style_mismatch(team_style: str, opponent_style: str) -> float:
    """Расчёт коэффициента различия стилей команд."""
    if team_style == opponent_style:
        return 0
    return 1

def ewma(values: List[float], alpha: float) -> float:
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
        "humidity": 60      # Средняя влажность
    }

