"""Модуль для получения и обработки данных о матчах."""
import asyncio
import json
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from logger import logger
from services.sportmonks_client import sportmonks_client
# Исправлено: Импорт правильного кэша
from database.cache_postgres import cache
import math
import numpy as np
import pandas as pd

# (cleanup) удалён мусорный `return None` вне функций
# (cleanup) удалён артефакт `main`
# (cleanup) удалены повторные импорты numpy/pandas внизу файла (если присутствовали)
# (cleanup) удалены глобальные дубликаты утилит:
# - parse_dt_safe
# - compute_rest_days
# - style_mismatch
# - ewma
# - add_missing_ratio
# - load_climate_norm
# - haversine_km
# Используйте одноимённые методы/утилиты внутри класса DataProcessor.

class DataProcessor:
    """Класс для обработки данных матчей."""
    def __init__(self):
        """Инициализация процессора данных."""
        self.client = sportmonks_client
        # Исправлено: Используем правильный экземпляр кэша
        self.cache = cache

    def parse_dt_safe(self, date_str: str):
        """Парсинг даты с обработкой ошибок (без print, через логер)."""
        if not date_str:
            return None
        try:
            # быстрый ISO-путь
            if "T" in date_str or "Z" in date_str:
                ds = date_str.replace("Z", "").replace("T", " ")[:19]
                return datetime.fromisoformat(ds)
            # fallback на формат "%Y-%m-%d %H:%M:%S"
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning("parse_dt_safe: failed to parse %r: %s", date_str, e)
            return None
    def compute_rest_days(self, prev_match_dt: datetime, next_match_dt: datetime) -> int:
        """
        Вычисление количества дней отдыха между матчами.
        Args:
            prev_match_dt (datetime): Дата и время предыдущего матча.
            next_match_dt (datetime): Дата и время следующего матча.
        Returns:
            int: Количество дней отдыха (не менее 0).
        """
        try:
            if prev_match_dt is None or next_match_dt is None:
                logger.warning("Одна из дат для расчета дней отдыха равна None")
                return 0
            rest_days = max(0, (next_match_dt - prev_match_dt).days)
            logger.debug(f"Вычислено дней отдыха: {rest_days} (с {prev_match_dt} по {next_match_dt})")
            return rest_days
        except Exception as e:
            logger.error(f"Ошибка при вычислении дней отдыха: {e}")
            return 0
    def compute_travel_load(self, recent_fixtures: List[Dict[str, Any]]) -> Dict[str, Union[int, float]]:
        """
        Вычисление нагрузки от поездок на основе последних матчей.
        Args:
            recent_fixtures (List[Dict]): Список последних матчей с координатами стадионов.
        Returns:
            Dict: Словарь с параметрами нагрузки от поездок.
        """
        try:
            km, trips, tz = 0.0, 0, 0
            # Проверка наличия данных
            if not recent_fixtures or len(recent_fixtures) < 2:
                logger.debug("Недостаточно данных для расчета нагрузки от поездок")
                return {"trips": 0, "km_trip": 0.0, "tz_shift": 0}
            # Расчет параметров поездок
            for a, b in zip(recent_fixtures, recent_fixtures[1:]):
                # Расчет расстояния между стадионами
                lat1 = a.get("venue_lat", 0)
                lon1 = a.get("venue_lon", 0)
                lat2 = b.get("venue_lat", 0)
                lon2 = b.get("venue_lon", 0)
                # Проверка на None перед расчетом расстояния
                if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
                    logger.warning("Одна из координат для расчета расстояния равна None, используется 0")
                    lat1 = lat1 or 0
                    lon1 = lon1 or 0
                    lat2 = lat2 or 0
                    lon2 = lon2 or 0
                km += self.haversine_km(lat1, lon1, lat2, lon2)
                # Расчет сдвигов по временным зонам
                tz_a = int(a.get("tz", 0) or 0)
                tz_b = int(b.get("tz", 0) or 0)
                tz += abs(tz_a - tz_b)
                # Подсчет выездных матчей (переходы между домашними и выездными)
                a_home = a.get("home", False)
                b_home = b.get("home", False)
                if (a_home and not b_home) or (not a_home and b_home):
                    trips += 1
            result = {"trips": trips, "km_trip": km, "tz_shift": tz}
            logger.debug(f"Рассчитана нагрузка от поездок: {result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при расчете нагрузки от поездок: {e}")
            return {"trips": 0, "km_trip": 0.0, "tz_shift": 0}
    def haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Расчет расстояния между двумя точками на сфере (в километрах) по формуле Хаверсина.
        Args:
            lat1 (float): Широта первой точки.
            lon1 (float): Долгота первой точки.
            lat2 (float): Широта второй точки.
            lon2 (float): Долгота второй точки.
        Returns:
            float: Расстояние в километрах.
        """
        try:
            # Проверка на None
            if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
                logger.warning("Одна из координат для расчета расстояния Хаверсина равна None")
                return 0.0
            R = 6371.0  # Радиус Земли в км
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlamb = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlamb/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance = R * c
            return distance
        except Exception as e:
            logger.error(f"Ошибка в расчете расстояния Хаверсина: {e}")
            return 0.0
    def calculate_rolling_intensity(self, fixtures: List[Dict], window_days: int = 14) -> float:
        """
        Расчет скользящей интенсивности матчей за указанный период.
        Args:
            fixtures (List[Dict]): Список матчей с данными о статистике.
            window_days (int): Период анализа в днях.
        Returns:
            float: Индекс интенсивности (0-10).
        """
        try:
            if not fixtures:
                return 0.0
            # Определяем начальную дату для анализа
            current_date = datetime.now()
            start_date = current_date - timedelta(days=window_days)
            # Фильтруем матчи по периоду
            recent_fixtures = [
                f for f in fixtures 
                if f.get("date") and datetime.fromisoformat(f["date"].replace('Z', '+00:00')) >= start_date
            ]
            if not recent_fixtures:
                return 0.0
            # Подсчитываем интенсивные показатели
            total_shots = 0
            total_fouls = 0
            total_sprints = 0
            for fixture in recent_fixtures:
                # Получаем статистику матча
                stats = fixture.get("stats", [])
                for stat in stats:
                    if stat.get("name") == "Shots":
                        total_shots += stat.get("value", 0) or 0
                    elif stat.get("name") == "Fouls":
                        total_fouls += stat.get("value", 0) or 0
                    # Другие показатели интенсивности могут быть добавлены здесь
            # Рассчитываем средние значения
            avg_shots = total_shots / len(recent_fixtures) if recent_fixtures else 0
            avg_fouls = total_fouls / len(recent_fixtures) if recent_fixtures else 0
            # Нормализуем значения (примерные пороги)
            shots_intensity = min(10, avg_shots / 15 * 10)  # 15 ударов ~ максимальная интенсивность
            fouls_intensity = min(10, avg_fouls / 20 * 10)   # 20 фолов ~ максимальная интенсивность
            # Комбинируем показатели
            intensity = (shots_intensity + fouls_intensity) / 2
            logger.debug(f"Рассчитана скользящая интенсивность: {intensity:.2f} за {window_days} дней")
            return intensity
        except Exception as e:
            logger.error(f"Ошибка при расчете скользящей интенсивности: {e}")
            return 0.0
    async def _calculate_team_fatigue(self, home_team_id: int, away_team_id: int, match_date: datetime) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Расчет усталости команд.
        Args:
            home_team_id (int): ID домашней команды.
            away_team_id (int): ID гостевой команды.
            match_date (datetime): Дата следующего матча.
        Returns:
            Tuple[Dict[str, Any], Dict[str, Any]]: (home_fatigue_data, away_fatigue_data).
        """
        try:
            logger.debug(f"Расчет усталости для команд {home_team_id} и {away_team_id}")
            # Получаем последние матчи команд (за последние 30 дней)
            cutoff_date = match_date - timedelta(days=30)
            date_from = cutoff_date.strftime("%Y-%m-%d")
            # Параллельно получаем последние матчи обеих команд
            tasks = [
                asyncio.create_task(self.client.get_last_team_matches(home_team_id, date_from=date_from)),
                asyncio.create_task(self.client.get_last_team_matches(away_team_id, date_from=date_from))
            ]
            home_fixtures_raw, away_fixtures_raw = await asyncio.gather(*tasks, return_exceptions=True)
            # Обработка возможных исключений
            if isinstance(home_fixtures_raw, Exception):
                logger.error(f"Ошибка при получении матчей для команды {home_team_id}: {home_fixtures_raw}")
                home_fixtures_raw = []
            if isinstance(away_fixtures_raw, Exception):
                logger.error(f"Ошибка при получении матчей для команды {away_team_id}: {away_fixtures_raw}")
                away_fixtures_raw = []
            # Сортируем матчи по дате
            home_fixtures = sorted(
                [f for f in home_fixtures_raw if f.get("date")],
                key=lambda x: datetime.fromisoformat(x["date"].replace('Z', '+00:00'))
            )
            away_fixtures = sorted(
                [f for f in away_fixtures_raw if f.get("date")],
                key=lambda x: datetime.fromisoformat(x["date"].replace('Z', '+00:00'))
            )
            # Рассчитываем дни отдыха
            home_rest_days = 0
            away_rest_days = 0
            if home_fixtures:
                last_home_match_dt = datetime.fromisoformat(home_fixtures[-1]["date"].replace('Z', '+00:00'))
                home_rest_days = self.compute_rest_days(last_home_match_dt, match_date)
            if away_fixtures:
                last_away_match_dt = datetime.fromisoformat(away_fixtures[-1]["date"].replace('Z', '+00:00'))
                away_rest_days = self.compute_rest_days(last_away_match_dt, match_date)
            # Рассчитываем нагрузку от поездок
            home_travel_load = self.compute_travel_load(home_fixtures)
            away_travel_load = self.compute_travel_load(away_fixtures)
            # Рассчитываем скользящую интенсивность
            home_intensity = self.calculate_rolling_intensity(home_fixtures)
            away_intensity = self.calculate_rolling_intensity(away_fixtures)
            # --- НОВАЯ ЛОГИКА: Расчет суммарных минут ключевых игроков ---
            # Используем последние 5 матчей для расчета доступности ядра
            home_last5_fixtures = home_fixtures[-5:] if len(home_fixtures) >= 5 else home_fixtures
            away_last5_fixtures = away_fixtures[-5:] if len(away_fixtures) >= 5 else away_fixtures
            # Агрегируем минуты для последних 5 матчей
            home_player_minutes = self.aggregate_minutes([{"players": f.get("lineups", [])} for f in home_last5_fixtures])
            away_player_minutes = self.aggregate_minutes([{"players": f.get("lineups", [])} for f in away_last5_fixtures])
            # Определяем ядро: топ-7 игроков по минутам за последние 5 матчей
            home_top_core = sorted(home_player_minutes.items(), key=lambda x: x[1], reverse=True)[:7]
            away_top_core = sorted(away_player_minutes.items(), key=lambda x: x[1], reverse=True)[:7]
            # Суммируем минуты ключевых игроков
            home_core_minutes = sum(minutes for _, minutes in home_top_core)
            away_core_minutes = sum(minutes for _, minutes in away_top_core)
            # --- КОНЕЦ НОВОЙ ЛОГИКИ ---
            # Формируем данные об усталости
            home_fatigue_data = {
                "rest_days": home_rest_days,
                "rest_days_flag": home_rest_days < 3,  # Флаг <3 дней отдыха
                "travel_load": home_travel_load,
                "rolling_intensity": home_intensity,
                "recent_matches_count": len(home_fixtures),
                "core_minutes": home_core_minutes # Добавлено: суммарные минуты ключевых
            }
            away_fatigue_data = {
                "rest_days": away_rest_days,
                "rest_days_flag": away_rest_days < 3,  # Флаг <3 дней отдыха
                "travel_load": away_travel_load,
                "rolling_intensity": away_intensity,
                "recent_matches_count": len(away_fixtures),
                "core_minutes": away_core_minutes # Добавлено: суммарные минуты ключевых
            }
            logger.debug(f"Усталость: {home_team_id} {home_fatigue_data}, {away_team_id} {away_fatigue_data}")
            return home_fatigue_data, away_fatigue_data
        except Exception as e:
            logger.error(f"Ошибка при расчете усталости команд {home_team_id} и {away_team_id}: {e}")
            return {"rest_days": 0, "rest_days_flag": False, "travel_load": {}, "rolling_intensity": 0.0, "recent_matches_count": 0, "core_minutes": 0}, \
                   {"rest_days": 0, "rest_days_flag": False, "travel_load": {}, "rolling_intensity": 0.0, "recent_matches_count": 0, "core_minutes": 0}
    def compute_match_importance(self, table_row: Dict[str, Any], rounds_left: int) -> float:
        """
        Вычисление важности матча на основе расстояния до порогов и оставшихся туров.
        Args:
            table_row: Строка из таблицы с данными команды, включая позицию, очки и расстояния до порогов.
                       Ожидаемые ключи: "pts_to_relegation_safety", "pts_to_euro_spot"
            rounds_left: Количество оставшихся туров в сезоне.
        Returns:
            float: Важность матча в диапазоне [0..1].
        """
        try:
            # Проверка на None
            if table_row is None:
                logger.warning("table_row равен None")
                return 0.0
            # Получаем расстояния до порогов из данных таблицы
            dist_releg = max(0, table_row.get("pts_to_relegation_safety", float('inf')) or float('inf'))
            dist_euro = max(0, table_row.get("pts_to_euro_spot", float('inf')) or float('inf'))
            # Чем ближе к порогу, тем важнее; нормируем
            # Используем 1/(1+x) для плавного убывания важности с увеличением расстояния
            score = 1 / (1 + dist_releg) + 1 / (1 + dist_euro)
            # Усиливаем важность под конец сезона
            # Если осталось <= 10 туров, усиливаем важность
            endgame_boost = 1 + (max(0, 10 - (rounds_left or 0)) / 10.0)
            # Нормируем итоговое значение в диапазон [0..1]
            # Коэффициент 0.5 подобран экспериментально для масштабирования
            # Исправлено: Убедимся, что score не превышает 2, чтобы корректно нормировать
            imp = min(1.0, 0.5 * score * endgame_boost)
            logger.debug(f"Вычислена важность матча: {imp:.3f} (dist_releg={dist_releg}, dist_euro={dist_euro}, rounds_left={rounds_left})")
            return imp
        except Exception as e:
            logger.error(f"Ошибка при вычислении важности матча: {e}", exc_info=True)
            # Возвращаем значение по умолчанию в случае ошибки
            return 0.0
    def aggregate_minutes(self, lineups_: List[Dict[str, Any]]) -> Dict[int, int]:
        """
        Агрегирует минуты игроков из данных о составах.
        Args:
            lineups_data (List[Dict]): Список данных о составах.
        Returns:
            Dict[int, int]: Словарь {player_id: minutes}.
        """
        try:
            player_minutes = {}
            if not lineups_:
                return player_minutes
            for lineup in lineups_:
                # Получаем состав команды
                players = lineup.get("players", [])
                for player in players:
                    player_id = player.get("player_id")
                    minutes = player.get("minutes_played", 0) or 0
                    if player_id:
                        if player_id in player_minutes:
                            player_minutes[player_id] += minutes
                        else:
                            player_minutes[player_id] = minutes
            return player_minutes
        except Exception as e:
            logger.error(f"Ошибка при агрегации минут игроков: {e}")
            return {}
    def is_probable_to_play(self, player_id: int, lineups_: List[Dict[str, Any]]) -> bool:
        """
        Определяет, вероятно ли, что игрок сыграет в следующем матче.
        Args:
            player_id (int): ID игрока.
            lineups_data (List[Dict]): Список данных о составах.
        Returns:
            bool: True, если игрок вероятно сыграет.
        """
        try:
            # Проверяем наличие игрока в последних составах
            if not lineups_:
                return False
            # Проверяем статус игрока в последнем составе
            for lineup in reversed(lineups_):  # Начинаем с последнего матча
                players = lineup.get("players", [])
                for player in players:
                    if player.get("player_id") == player_id:
                        # Проверяем статус игрока
                        status = (player.get("status", "available") or "available").lower()
                        if status in ["available", "starter", "sub"]:
                            return True
                        elif status in ["injured", "suspended", "unavailable"]:
                            return False
            # Если игрок не найден в составах, считаем, что он доступен
            return True
        except Exception as e:
            logger.error(f"Ошибка при определении вероятности игры игрока {player_id}: {e}")
            return True
    def core_availability(self, last5_lineups: List[Dict[str, Any]]) -> float:
        """
        Возвращает долю минут ядра, доступного к матчу [0..1].
        Args:
            last5_lineups (List[Dict]): Данные о составах последних 5 матчей.
        Returns:
            float: Доля доступности ядра (0-1).
        """
        try:
            # Агрегируем минуты игроков
            players = self.aggregate_minutes(last5_lineups)
            if not players:
                logger.debug("Нет данных об игроках для расчета доступности ядра")
                return 1.0  # Если нет данных, считаем ядро полностью доступным
            # Определяем ядро: топ-7 игроков по минутам
            top_core = sorted(players.items(), key=lambda x: x[1], reverse=True)[:7]
            if not top_core:
                logger.debug("Нет данных о ключевых игроках")
                return 1.0
            # Считаем доступность ядра
            available = 0
            total = 0
            for player_id, minutes in top_core:
                total += minutes
                if self.is_probable_to_play(player_id, last5_lineups):
                    available += minutes
            # Рассчитываем долю доступности
            availability = 0.0 if total == 0 else available / total
            logger.debug(f"Доступность ядра: {availability:.3f} (доступно {available}/{total} минут ключевых игроков)")
            return availability
        except Exception as e:
            logger.error(f"Ошибка при расчете доступности ядра: {e}")
            return 1.0  # В случае ошибки считаем ядро полностью доступным
    # ДОБАВЛЕНО: Обновлен метод ewma согласно инструкции
    def ewma(self, values: List[float], half_life_days: float, dates: List[datetime]) -> float:
        """
        Вычисление экспоненциально взвешенного скользящего среднего.
        Args:
            values (List[float]): Список значений.
            half_life_days (float): Период полураспада в днях.
            dates (List[datetime]): Список дат, соответствующих значениям.
        Returns:
            float: Экспоненциально взвешенное среднее.
        """
        try:
            if not values or not dates or len(values) != len(dates):
                logger.warning("Некорректные входные данные для расчета EWMA")
                return 0.0
            # ИЗМЕНЕНО: Реализация EWMA по инструкции с дополнительной проверкой
            weights = []
            for d in dates[::-1]:  # Перебираем даты в обратном порядке
                if dates[-1] is None or d is None:
                    logger.warning("Одна из дат для расчета EWMA равна None")
                    weights.append(0.0)
                    continue
                delta = (dates[-1] - d).days
                # ИЗМЕНЕНО: Избегаем деления на 0
                w = 0.5 ** (delta / max(half_life_days, 1e-6)) # Защита от деления на 0 или очень маленькое число
                weights.append(w)
            # Переворачиваем веса обратно
            weights = np.array(weights[::-1])
            # Нормализуем веса
            weights_sum = weights.sum()
            if weights_sum > 0:
                weights = weights / weights_sum
            else:
                weights = np.ones_like(weights) / len(weights)  # Равномерные веса если сумма 0
            # Вычисляем взвешенное среднее
            result = float((np.array(values) * weights).sum())
            logger.debug(f"Рассчитано EWMA: {result:.4f} (период полураспада: {half_life_days} дней)")
            return result
        except Exception as e:
            logger.error(f"Ошибка при расчете EWMA: {e}")
            return 0.0
    # ДОБАВЛЕНО: Обновлен метод opponent_adjust согласно инструкции
    def opponent_adjust(self, value: float, opp_def_rating: float) -> float:
        """
        Корректировка значения с учетом силы соперника.
        Args:
            value (float): Исходное значение.
            opp_def_rating (float): Рейтинг обороны соперника (0 - средний соперник).
        Returns:
            float: Скорректированное значение.
        """
        try:
            # Простая коррекция: чем сильнее оборона соперника, тем выше скорректированный xG
            # ИЗМЕНЕНО: Реализация opponent_adjust по инструкции
            adjusted_value = (value or 0.0) - ((opp_def_rating or 0.0) - 0.0)  # 0.0 - средний соперник
            logger.debug(f"Корректировка значения {value:.4f} с учетом силы соперника ({opp_def_rating}): {adjusted_value:.4f}")
            return adjusted_value
        except Exception as e:
            logger.error(f"Ошибка при корректировке значения с учетом соперника: {e}")
            return value or 0.0
    # ДОБАВЛЕНО: Новый метод strength_adjusted_metric для нормировки под силу оппонента
    def strength_adjusted_metric(self, raw: float, opp_strength: float) -> float:
        """
        Корректировка метрики с учетом силы соперника (Strength of Schedule).
        Args:
            raw (float): Исходное значение метрики.
            opp_strength (float): Сила соперника (0.0 - средний соперник).
        Returns:
            float: Скорректированное значение.
        """
        try:
            # Простая линейная коррекция (масштаб — подобрать)
            adjusted_value = (raw or 0.0) - 0.5 * ((opp_strength or 0.0) - 0.0)
            logger.debug(f"Корректировка метрики {raw:.4f} с учетом силы соперника ({opp_strength}): {adjusted_value:.4f}")
            return adjusted_value
        except Exception as e:
            logger.error(f"Ошибка при корректировке метрики с учетом силы соперника: {e}")
            return raw or 0.0
    # ДОБАВЛЕНО: Новый метод calculate_rolling_xg для расчета скользящих xG
    def calculate_rolling_xg(self, fixtures: List[Dict], window: int = 5) -> Dict[str, float]:
        """
        Расчет скользящего среднего xG для последних N матчей.
        Args:
            fixtures (List[Dict]): Список матчей с данными о xG.
            window (int): Размер окна (по умолчанию 5 матчей).
        Returns:
            Dict[str, float]: Словарь со значениями xG для разных окон.
        """
        try:
            if not fixtures:
                return {"xg_3": 0.0, "xg_5": 0.0, "xg_10": 0.0}
            # Сортируем матчи по дате
            sorted_fixtures = sorted(
                [f for f in fixtures if f.get("date")],
                key=lambda x: datetime.fromisoformat(x["date"].replace('Z', '+00:00'))
            )
            # Извлекаем значения xG
            xg_values = []
            dates = []
            for fixture in sorted_fixtures:
                xg = fixture.get("xg", 0) or 0
                if isinstance(xg, (int, float)):
                    xg_values.append(float(xg))
                    date_str = fixture.get("date")
                    if date_str:
                        dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')))
            if not xg_values:
                return {"xg_3": 0.0, "xg_5": 0.0, "xg_10": 0.0}
            # Рассчитываем скользящие средние для разных окон
            xg_3 = np.mean(xg_values[-3:]) if len(xg_values) >= 3 else np.mean(xg_values)
            xg_5 = np.mean(xg_values[-5:]) if len(xg_values) >= 5 else np.mean(xg_values)
            xg_10 = np.mean(xg_values[-10:]) if len(xg_values) >= 10 else np.mean(xg_values)
            result = {
                "xg_3": float(xg_3),
                "xg_5": float(xg_5),
                "xg_10": float(xg_10)
            }
            logger.debug(f"Рассчитаны скользящие xG: {result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при расчете скользящего xG: {e}")
            return {"xg_3": 0.0, "xg_5": 0.0, "xg_10": 0.0}
    def style_mismatch(self, ppda_for_team: float, build_up_opp: float) -> float:
        """
        Вычисление индекса стилевого несоответствия между командами.
        Args:
            ppda_for_team (float): PPDA команды (чем ниже, тем лучше оборона).
            build_up_opp (float): Показатель построения атаки соперника.
        Returns:
            float: Индекс стилевого несоответствия (0.0 и выше).
        """
        try:
            # Проверка на None
            if ppda_for_team is None or build_up_opp is None:
                logger.warning("Одно из значений для расчета стилевого несоответствия равно None")
                return 0.0
            # Пример прокси: чем ниже PPDA у команды и выше билд-ап соперника — тем «жарче»
            # Избегаем деления на ноль или очень маленькое значение
            if (ppda_for_team or 0.0) <= 0.1: # Исправлено: Проверка на минимальное значение для избежания деления на очень маленькое число
                ppda_for_team = 0.1  # Минимальное значение для избежания деления на ноль
            mismatch_index = max(0.0, (1.0 / (ppda_for_team or 0.1)) + (build_up_opp or 0.0))
            logger.debug(f"Рассчитан индекс стилевого несоответствия: {mismatch_index:.4f} "
                        f"(PPDA команды: {ppda_for_team}, билд-ап соперника: {build_up_opp})")
            return mismatch_index
        except Exception as e:
            logger.error(f"Ошибка при расчете индекса стилевого несоответствия: {e}")
            return 0.0
    def per90(self, value: float, minutes: float) -> float:
        """
        Нормализация значения на 90 минут.
        Args:
            value (float): Исходное значение.
            minutes (float): Количество сыгранных минут.
        Returns:
            float: Значение, нормализованное на 90 минут.
        """
        try:
            if not minutes or minutes == 0:
                return 0.0
            normalized_value = 90.0 * (value or 0.0) / minutes
            logger.debug(f"Нормализация per90: {value}/{minutes} минут = {normalized_value:.4f}")
            return normalized_value
        except Exception as e:
            logger.error(f"Ошибка при нормализации per90: {e}")
            return 0.0
    def winsorize(self, x: np.ndarray, low: float = 0.01, high: float = 0.99) -> np.ndarray:
        """
        Winsorизация массива значений (ограничение выбросов).
        Args:
            x (np.ndarray): Массив значений.
            low (float): Нижний квантиль (по умолчанию 0.01).
            high (float): Верхний квантиль (по умолчанию 0.99).
        Returns:
            np.ndarray: Winsorизованный массив.
        """
        try:
            if len(x) == 0:
                logger.warning("Пустой массив для winsorize")
                return x
            # Вычисляем квантили
            lo = np.quantile(x, low or 0.01)
            hi = np.quantile(x, high or 0.99)
            # Применяем winsorize
            winsorized_array = np.clip(x, lo, hi)
            logger.debug(f"Winsorize: квантили {low}={lo:.4f}, {high}={hi:.4f}")
            return winsorized_array
        except Exception as e:
            logger.error(f"Ошибка при winsorize: {e}")
            return x
    def league_zscore(self, x: float, league_mean: float, league_std: float) -> float:
        """
        Вычисление z-оценки значения относительно лиги.
        Args:
            x (float): Значение для нормализации.
            league_mean (float): Среднее значение по лиге.
            league_std (float): Стандартное отклонение по лиге.
        Returns:
            float: Z-оценка.
        """
        try:
            # Проверка на None
            if league_mean is None or league_std is None:
                logger.warning("Одно из значений для расчета z-оценки равно None")
                return 0.0
            if (league_std or 0.0) == 0:
                logger.debug("Стандартное отклонение лиги равно 0, возвращаем 0.0")
                return 0.0
            z_score = ((x or 0.0) - (league_mean or 0.0)) / (league_std or 1.0)
            logger.debug(f"Z-оценка: ({x} - {league_mean}) / {league_std} = {z_score:.4f}")
            return z_score
        except Exception as e:
            logger.error(f"Ошибка при вычислении z-оценки: {e}")
            return 0.0
    def impute_weather(self, venue_city: str, match_month: int) -> Dict[str, Any]:
        """
        Импутация погодных данных на основе климатических норм.
        Args:
            venue_city (str): Город проведения матча.
            match_month (int): Месяц проведения матча.
        Returns:
            Dict[str, Any]: Импутированные погодные данные.
        """
        try:
            # Заглушка - в реальной реализации нужно загружать климатические нормы из файла или БД
            # Примерная таблица климатических норм (температура, ветер, вероятность дождя)
            climate_norms = {
                "London": {
                    1: {"temp_c": 6, "wind_mps": 4.5, "rain_prob": 0.35},
                    2: {"temp_c": 7, "wind_mps": 4.7, "rain_prob": 0.33},
                    3: {"temp_c": 9, "wind_mps": 4.2, "rain_prob": 0.30},
                    4: {"temp_c": 12, "wind_mps": 3.8, "rain_prob": 0.25},
                    5: {"temp_c": 16, "wind_mps": 3.5, "rain_prob": 0.22},
                    6: {"temp_c": 19, "wind_mps": 3.2, "rain_prob": 0.20},
                    7: {"temp_c": 21, "wind_mps": 3.0, "rain_prob": 0.18},
                    8: {"temp_c": 21, "wind_mps": 3.1, "rain_prob": 0.19},
                    9: {"temp_c": 18, "wind_mps": 3.4, "rain_prob": 0.23},
                    10: {"temp_c": 14, "wind_mps": 3.9, "rain_prob": 0.28},
                    11: {"temp_c": 9, "wind_mps": 4.3, "rain_prob": 0.32},
                    12: {"temp_c": 7, "wind_mps": 4.6, "rain_prob": 0.36}
                },
                "Madrid": {
                    1: {"temp_c": 8, "wind_mps": 2.1, "rain_prob": 0.15},
                    2: {"temp_c": 10, "wind_mps": 2.3, "rain_prob": 0.14},
                    3: {"temp_c": 13, "wind_mps": 2.0, "rain_prob": 0.12},
                    4: {"temp_c": 15, "wind_mps": 1.8, "rain_prob": 0.10},
                    5: {"temp_c": 20, "wind_mps": 1.6, "rain_prob": 0.08},
                    6: {"temp_c": 26, "wind_mps": 1.4, "rain_prob": 0.05},
                    7: {"temp_c": 30, "wind_mps": 1.3, "rain_prob": 0.03},
                    8: {"temp_c": 30, "wind_mps": 1.4, "rain_prob": 0.04},
                    9: {"temp_c": 25, "wind_mps": 1.7, "rain_prob": 0.07},
                    10: {"temp_c": 20, "wind_mps": 1.9, "rain_prob": 0.10},
                    11: {"temp_c": 13, "wind_mps": 2.1, "rain_prob": 0.13},
                    12: {"temp_c": 9, "wind_mps": 2.2, "rain_prob": 0.16}
                },
                "Moscow": {
                    1: {"temp_c": -7, "wind_mps": 4.0, "rain_prob": 0.40},
                    2: {"temp_c": -5, "wind_mps": 4.2, "rain_prob": 0.38},
                    3: {"temp_c": 0, "wind_mps": 3.8, "rain_prob": 0.35},
                    4: {"temp_c": 10, "wind_mps": 3.5, "rain_prob": 0.30},
                    5: {"temp_c": 18, "wind_mps": 3.2, "rain_prob": 0.25},
                    6: {"temp_c": 21, "wind_mps": 3.0, "rain_prob": 0.22},
                    7: {"temp_c": 23, "wind_mps": 2.8, "rain_prob": 0.20},
                    8: {"temp_c": 21, "wind_mps": 2.9, "rain_prob": 0.21},
                    9: {"temp_c": 15, "wind_mps": 3.1, "rain_prob": 0.24},
                    10: {"temp_c": 7, "wind_mps": 3.4, "rain_prob": 0.28},
                    11: {"temp_c": 0, "wind_mps": 3.7, "rain_prob": 0.33},
                    12: {"temp_c": -5, "wind_mps": 3.9, "rain_prob": 0.39}
                }
            }
            # Получаем климатические нормы для города
            city_norms = climate_norms.get(venue_city or "", {})
            if not city_norms:
                # Если город не найден, используем средние значения
                logger.warning(f"Не найдены климатические нормы для города {venue_city}, используем средние значения")
                climate_data = {"temp_c": 15, "wind_mps": 3.0, "rain_prob": 0.25}
            else:
                # Получаем нормы для месяца
                climate_data = city_norms.get(match_month or 0, {"temp_c": 15, "wind_mps": 3.0, "rain_prob": 0.25})
            # Добавляем флаг импутации
            climate_data["is_imputed"] = True
            logger.debug(f"Импутированы погодные данные для {venue_city}, месяц {match_month}: {climate_data}")
            return climate_data
        except Exception as e:
            logger.error(f"Ошибка при импутации погодных данных: {e}")
            # Возвращаем значения по умолчанию в случае ошибки
            return {"temp_c": 15, "wind_mps": 3.0, "rain_prob": 0.25, "is_imputed": True}
    def travel_features(self, team_venue: Dict[str, Any], match_venue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Расчет признаков путешествия команды.
        Args:
            team_venue (Dict[str, Any]): Данные о стадионе команды (домашнем).
            match_venue (Dict[str, Any]): Данные о стадионе проведения матча.
        Returns:
            Dict[str, Any]: Признаки путешествия.
        """
        try:
            # Расчет расстояния между стадионами
            team_lat = team_venue.get("lat", 0) or 0
            team_lon = team_venue.get("lon", 0) or 0
            match_lat = match_venue.get("lat", 0) or 0
            match_lon = match_venue.get("lon", 0) or 0
            # Проверка на None перед расчетом расстояния
            if team_lat is None or team_lon is None or match_lat is None or match_lon is None:
                logger.warning("Одна из координат для расчета признаков путешествия равна None")
                team_lat = team_lat or 0
                team_lon = team_lon or 0
                match_lat = match_lat or 0
                match_lon = match_lon or 0
            km = self.haversine_km(team_lat, team_lon, match_lat, match_lon)
            # Расчет сдвига временных зон
            team_tz = int(team_venue.get("tz", 0) or 0)
            match_tz = int(match_venue.get("tz", 0) or 0)
            tz_shift = abs(team_tz - match_tz)
            # Определение "красного глаза" (длинная поездка с большим сдвигом по времени)
            red_eye = int((km or 0) > 2000 and tz_shift >= 2)
            result = {
                "km_trip": km,
                "tz_shift": tz_shift,
                "red_eye": red_eye
            }
            logger.debug(f"Рассчитаны признаки путешествия: {result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при расчете признаков путешествия: {e}")
            # Возвращаем значения по умолчанию в случае ошибки
            return {"km_trip": 0.0, "tz_shift": 0, "red_eye": 0}
    def count_consecutive(self, results: List[str], target: str) -> int:
        """
        Подсчет количества последовательных результатов.
        Args:
            results (List[str]): Список результатов ('W', 'D', 'L').
            target (str): Целевой результат для подсчета.
        Returns:
            int: Количество последовательных целевых результатов с конца списка.
        """
        try:
            count = 0
            # Перебираем результаты с конца
            for result in reversed(results or []):
                if result == (target or ""):
                    count += 1
                else:
                    break
            return count
        except Exception as e:
            logger.error(f"Ошибка при подсчете последовательных результатов: {e}")
            return 0
    def goals_scored(self, match: Dict[str, Any]) -> int:
        """
        Извлечение количества забитых голов из данных матча.
        Args:
            match (Dict[str, Any]): Данные матча.
        Returns:
            int: Количество забитых голов.
        """
        try:
            # Проверка на None
            if match is None:
                logger.warning("match равен None")
                return 0
            # Пытаемся получить голы из разных возможных полей
            goals = match.get("goals", 0)
            if isinstance(goals, int):
                return goals
            # Если goals - словарь, ищем нужные ключи
            if isinstance(goals, dict):
                return goals.get("scored", goals.get("for", 0) or 0) or 0
            # Пытаемся получить из home_goals/away_goals
            home_goals = match.get("home_goals")
            away_goals = match.get("away_goals")
            # Исправлено: Проверка на None перед преобразованием в int
            # Определяем, чьи голы мы считаем (для домашней команды)
            if match.get("home") is True and home_goals is not None:
                try:
                    return int(home_goals or 0)
                except (ValueError, TypeError):
                    logger.warning(f"Некорректное значение home_goals: {home_goals}")
                    return 0
            elif match.get("home") is False and away_goals is not None:
                try:
                    return int(away_goals or 0)
                except (ValueError, TypeError):
                    logger.warning(f"Некорректное значение away_goals: {away_goals}")
                    return 0
            return 0
        except Exception as e:
            logger.error(f"Ошибка при извлечении голов из матча: {e}")
            return 0
    def streak_features(self, last_n_results: List[Dict[str, Any]], team_season_avg: float = 1.5) -> Dict[str, Any]:
        """
        Расчет признаков стрик и "горячих/сухих" серий.
        Args:
            last_n_results (List[Dict[str, Any]]): Список последних матчей команды.
            team_season_avg (float): Среднее количество голов команды за сезон.
        Returns:
            Dict[str, Any]: Признаки стрик и серий.
        """
        try:
            # Извлекаем результаты матчей (например, 'W', 'D', 'L')
            results = []
            for match in last_n_results or []:
                # Получаем результат матча
                result = match.get("result")  # Ожидаем 'W', 'D', 'L'
                if result:
                    results.append(result)
                else:
                    # Альтернативные способы определения результата
                    home_goals = match.get("home_goals", 0)
                    away_goals = match.get("away_goals", 0)
                    if home_goals is not None and away_goals is not None:
                        # Определяем, чьи голы мы анализируем
                        if match.get("home") is True:  # Если это домашний матч для команды
                            team_goals = home_goals
                            opponent_goals = away_goals
                        else:  # Если это выездной матч для команды
                            team_goals = away_goals
                            opponent_goals = home_goals
                        # Определяем результат
                        if (team_goals or 0) > (opponent_goals or 0):
                            results.append("W")
                        elif (team_goals or 0) < (opponent_goals or 0):
                            results.append("L")
                        else:
                            results.append("D")
            # Подсчет побед подряд
            win_streak = self.count_consecutive(results, target="W")
            # Проверка на "сухую" серию (мало голов в последних 3 матчах)
            last_3_matches = (last_n_results or [])[-3:] if len(last_n_results or []) >= 3 else (last_n_results or [])
            goals_in_last_3 = sum(self.goals_scored(match) for match in last_3_matches)
            dry_spell = int(goals_in_last_3 <= 1)
            # Проверка на "взрывную" серию (много голов в последних 3 матчах)
            burst = int(goals_in_last_3 >= 2 * (team_season_avg or 0))
            result = {
                "win_streak": win_streak,
                "dry_spell": dry_spell,
                "burst": burst
            }
            logger.debug(f"Рассчитаны признаки стрик: {result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при расчете признаков стрик: {e}")
            # Возвращаем значения по умолчанию в случае ошибки
            return {"win_streak": 0, "dry_spell": 0, "burst": 0}
    def add_missing_mask(self, features: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Добавление маски пропущенных значений к признакам.
        Args:
            features (Dict[str, Any]): Словарь признаков.
        Returns:
            Tuple[Dict[str, Any], Dict[str, int]]: (обновленные признаки, маска пропусков).
        """
        try:
            # Создаем маску пропусков
            mask = {}
            missing_count = 0
            for k, v in (features or {}).items():
                # Проверяем, является ли значение None или NaN
                is_missing = v is None or (isinstance(v, float) and np.isnan(v))
                mask[k] = int(is_missing)
                if is_missing:
                    missing_count += 1
            # Рассчитываем долю пропущенных значений
            total_features = len(features or {})
            missing_ratio = missing_count / max(1, total_features)
            # Добавляем долю пропусков в признаки
            if features is not None:
                features["missing_ratio"] = missing_ratio
            logger.debug(f"Добавлена маска пропусков: {missing_count}/{total_features} пропущенных значений, "
                        f"доля: {missing_ratio:.3f}")
            return features or {}, mask
        except Exception as e:
            logger.error(f"Ошибка при добавлении маски пропусков: {e}")
            # Возвращаем исходные признаки и пустую маску в случае ошибки
            return features or {}, {}
    async def get_match_context(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение контекста матча: погода, составы, таблица, форма и т.д.
        """
        try:
            logger.info(f"Начало получения контекста для матча {fixture_id}")
            # Получаем базовую информацию о матче
            fixture = await self.client.get_fixture(fixture_id)
            if not fixture:
                logger.error(f"Не удалось получить данные матча {fixture_id}")
                return None
            # Извлекаем дату и команды
            match_date_str = fixture.get("date", "")
            if not match_date_str:
                logger.error(f"Не указана дата матча {fixture_id}")
                return None
            try:
                # Парсим дату матча
                match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00')).date()
            except ValueError as e:
                logger.error(f"Ошибка парсинга даты матча {fixture_id}: {e}")
                return None
            home_team_id = fixture.get("home_team_id")
            away_team_id = fixture.get("away_team_id")
            if not home_team_id or not away_team_id:
                logger.error(f"Не указаны команды для матча {fixture_id}")
                return None
            logger.debug(f"Матч {fixture_id}: {home_team_id} vs {away_team_id} на {match_date}")
            # Определяем диапазон дат для получения недавних матчей (последние 90 дней)
            date_to = match_date
            date_from = date_to - timedelta(days=90)
            # Создаем задачи для параллельного получения данных
            tasks = [
                asyncio.create_task(self.client.get_weather(home_team_id, match_date)),
                asyncio.create_task(self.client.get_lineups(fixture_id)),
                asyncio.create_task(self.client.get_injuries(home_team_id)),
                asyncio.create_task(self.client.get_injuries(away_team_id)),
                asyncio.create_task(self.client.get_table(fixture_id)),
                asyncio.create_task(self.client.get_last_team_matches(home_team_id, date_from=date_from)),
                asyncio.create_task(self.client.get_last_team_matches(away_team_id, date_from=date_from))
            ]
            # Дожидаемся завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Обрабатываем результаты
            weather_data = results[0] if not isinstance(results[0], Exception) else None
            lineups_data = results[1] if not isinstance(results[1], Exception) else None
            home_injuries = results[2] if not isinstance(results[2], Exception) else None
            away_injuries = results[3] if not isinstance(results[3], Exception) else None
            standings_data = results[4] if not isinstance(results[4], Exception) else None
            home_fixtures_raw = results[5] if not isinstance(results[5], Exception) else []
            away_fixtures_raw = results[6] if not isinstance(results[6], Exception) else []
            # Проверяем на ошибки получения данных
            if isinstance(results[0], Exception):
                logger.error(f"Ошибка при получении погоды для матча {fixture_id}: {results[0]}")
            if isinstance(results[1], Exception):
                logger.error(f"Ошибка при получении составов для матча {fixture_id}: {results[1]}")
            if isinstance(results[2], Exception):
                logger.error(f"Ошибка при получении травм команды {home_team_id}: {results[2]}")
            if isinstance(results[3], Exception):
                logger.error(f"Ошибка при получении травм команды {away_team_id}: {results[3]}")
            if isinstance(results[4], Exception):
                logger.error(f"Ошибка при получении таблицы для матча {fixture_id}: {results[4]}")
            if isinstance(results[5], Exception):
                logger.error(f"Ошибка при получении матчей команды {home_team_id}: {results[5]}")
                home_fixtures_raw = []
            if isinstance(results[6], Exception):
                logger.error(f"Ошибка при получении матчей команды {away_team_id}: {results[6]}")
                away_fixtures_raw = []
            # Формируем контекст матча
            match_context = {
                "fixture_id": fixture_id,
                "match_date": match_date.isoformat(),
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "weather": weather_data,
                "lineups": lineups_data,
                "home_injuries": home_injuries,
                "away_injuries": away_injuries,
                "standings": standings_data.get("standings", []) if standings_data else [],
                "rounds_left": standings_data.get("rounds_left") if standings_data else None,
                "home_last_matches": home_fixtures_raw,
                "away_last_matches": away_fixtures_raw,
                "league_id": fixture.get("league_id"), # Добавлено: league_id
                "season_id": fixture.get("season_id")  # Добавлено: season_id
            }
            # Вычисляем важность матча, если доступны необходимые данные
            match_importance = 0.0
            standings = match_context.get("standings", [])
            rounds_left = match_context.get("rounds_left")
            if standings and rounds_left is not None:
                # Найти строки таблицы для обеих команд
                home_table_row = next((s for s in standings if s.get("team_id") == home_team_id), None)
                away_table_row = next((s for s in standings if s.get("team_id") == away_team_id), None)
                if home_table_row and away_table_row:
                    # Вычисляем важность для каждой команды
                    home_importance = self.compute_match_importance(home_table_row, rounds_left)
                    away_importance = self.compute_match_importance(away_table_row, rounds_left)
                    # Берем максимальную важность из двух
                    match_importance = max(home_importance, away_importance)
                    logger.debug(f"Важность матча {fixture_id}: {match_importance:.3f}")
                else:
                    logger.warning(f"Не удалось найти строки таблицы для команд {home_team_id} и {away_team_id}")
            else:
                logger.warning("Недостаточно данных для вычисления важности матча")
            # Добавляем важность матча в контекст
            match_context["match_importance"] = match_importance
            logger.info(f"Контекст для матча {fixture_id} успешно собран")
            return match_context
        except Exception as e:
            logger.error(f"Ошибка при получении контекста матча {fixture_id}: {e}", exc_info=True)
            return None
    async def process_match(self, match_: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Обработка одного матча: извлечение статистики, формирование признаков.
        """
        try:
            fixture_id = match_.get("id")
            if not fixture_id:
                return False, None, "Отсутствует ID матча"
            logger.info(f"Начало обработки матча {fixture_id}")
            # Получаем контекст матча
            context = await self.get_match_context(fixture_id)
            if not context:
                return False, None, "Не удалось получить контекст матча"
            # Извлекаем данные из контекста
            home_team_id = context["home_team_id"]
            away_team_id = context["away_team_id"]
            match_date = context["match_date"]
            # Получаем статистику команд
            home_stats_task = asyncio.create_task(self.client.get_team_stats(home_team_id, match_date))
            away_stats_task = asyncio.create_task(self.client.get_team_stats(away_team_id, match_date))
            # Добавлено: Получаем PPDA домашней и гостевой команд
            home_ppda_task = asyncio.create_task(self.client.get_team_stats(home_team_id, match_date, stat_type="ppda"))
            away_ppda_task = asyncio.create_task(self.client.get_team_stats(away_team_id, match_date, stat_type="ppda"))
            # Добавлено: Получаем Build-up Play домашней и гостевой команд
            home_build_up_task = asyncio.create_task(self.client.get_team_stats(home_team_id, match_date, stat_type="build_up_play"))
            away_build_up_task = asyncio.create_task(self.client.get_team_stats(away_team_id, match_date, stat_type="build_up_play"))
            # Дожидаемся завершения всех задач
            home_stats, away_stats, home_ppda, away_ppda, home_build_up, away_build_up = await asyncio.gather(
                home_stats_task, away_stats_task,
                home_ppda_task, away_ppda_task,
                home_build_up_task, away_build_up_task,
                return_exceptions=True
            )
            if isinstance(home_stats, Exception):
                logger.error(f"Ошибка при получении статистики команды {home_team_id}: {home_stats}")
                home_stats = {}
            if isinstance(away_stats, Exception):
                logger.error(f"Ошибка при получении статистики команды {away_team_id}: {away_stats}")
                away_stats = {}
            # Обработка PPDA и Build-up Play
            home_ppda_for = None
            home_ppda_against = None
            away_ppda_for = None
            away_ppda_against = None
            home_build_up_play = None
            away_build_up_play = None
            # Обработка PPDA домашней команды
            if isinstance(home_ppda, Exception):
                logger.error(f"Ошибка при получении PPDA команды {home_team_id}: {home_ppda}")
            else:
                # Предполагаем, что home_ppda - это словарь с ключами 'ppda_for' и 'ppda_against'
                # Или это список/словарь, где нужно извлечь эти значения
                if isinstance(home_ppda, dict):
                    home_ppda_for = home_ppda.get('ppda_for', None)
                    home_ppda_against = home_ppda.get('ppda_against', None)
                elif isinstance(home_ppda, list) and len(home_ppda) > 0:
                    # Если это список, предположим, что первый элемент содержит нужные данные
                    ppda_dict = home_ppda[0] if isinstance(home_ppda[0], dict) else {}
                    home_ppda_for = ppda_dict.get('ppda_for', None)
                    home_ppda_against = ppda_dict.get('ppda_against', None)
            # Обработка PPDA гостевой команды
            if isinstance(away_ppda, Exception):
                logger.error(f"Ошибка при получении PPDA команды {away_team_id}: {away_ppda}")
            else:
                if isinstance(away_ppda, dict):
                    away_ppda_for = away_ppda.get('ppda_for', None)
                    away_ppda_against = away_ppda.get('ppda_against', None)
                elif isinstance(away_ppda, list) and len(away_ppda) > 0:
                    ppda_dict = away_ppda[0] if isinstance(away_ppda[0], dict) else {}
                    away_ppda_for = ppda_dict.get('ppda_for', None)
                    away_ppda_against = ppda_dict.get('ppda_against', None)
            # Обработка Build-up Play домашней команды
            if isinstance(home_build_up, Exception):
                logger.error(f"Ошибка при получении Build-up Play команды {home_team_id}: {home_build_up}")
            else:
                # Предполагаем, что это значение или словарь с ключом 'build_up_play'
                if isinstance(home_build_up, (int, float)):
                    home_build_up_play = home_build_up
                elif isinstance(home_build_up, dict):
                    home_build_up_play = home_build_up.get('build_up_play', None)
                elif isinstance(home_build_up, list) and len(home_build_up) > 0:
                    build_up_dict = home_build_up[0] if isinstance(home_build_up[0], dict) else {}
                    home_build_up_play = build_up_dict.get('build_up_play', None)
            # Обработка Build-up Play гостевой команды
            if isinstance(away_build_up, Exception):
                logger.error(f"Ошибка при получении Build-up Play команды {away_team_id}: {away_build_up}")
            else:
                if isinstance(away_build_up, (int, float)):
                    away_build_up_play = away_build_up
                elif isinstance(away_build_up, dict):
                    away_build_up_play = away_build_up.get('build_up_play', None)
                elif isinstance(away_build_up, list) and len(away_build_up) > 0:
                    build_up_dict = away_build_up[0] if isinstance(away_build_up[0], dict) else {}
                    away_build_up_play = build_up_dict.get('build_up_play', None)
            # Добавлено: Расчет стилевого несоответствия
            style_mismatch_index = None
            if home_ppda_for is not None and away_build_up_play is not None:
                # PPDA домашней команды против Build-up гостевой команды
                style_mismatch_index = self.style_mismatch(home_ppda_for, away_build_up_play)
            elif away_ppda_for is not None and home_build_up_play is not None:
                # PPDA гостевой команды против Build-up домашней команды (альтернативный вариант)
                style_mismatch_index = self.style_mismatch(away_ppda_for, home_build_up_play)
            # Формируем итоговые данные
            processed_data = {
                "fixture_id": fixture_id,
                "context": context,
                "home_stats": home_stats,
                "away_stats": away_stats,
                # Добавлено: PPDA и стилевые данные
                "home_ppda_for": home_ppda_for,
                "home_ppda_against": home_ppda_against,
                "away_ppda_for": away_ppda_for,
                "away_ppda_against": away_ppda_against,
                "home_build_up_play": home_build_up_play,
                "away_build_up_play": away_build_up_play,
                "style_mismatch_index": style_mismatch_index
            }
            logger.info(f"Матч {fixture_id} успешно обработан")
            return True, processed_data, None
        except Exception as e:
            error_msg = f"Ошибка при обработке матча: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    async def process_matches_batch(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Пакетная обработка списка матчей.
        """
        logger.info(f"Начало пакетной обработки {len(matches)} матчей")
        # Создаем задачи для параллельной обработки матчей
        tasks = [asyncio.create_task(self.process_match(match)) for match in matches]
        # Выполняем все задачи
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Обрабатываем результаты
        processed_results = []
        for i, result in enumerate(results):
            try:
                if isinstance(result, Exception):
                    logger.error(f"Ошибка при обработке матча {matches[i]}: {result}")
                    processed_results.append({
                        "match": matches[i],
                        "success": False,
                        "error": str(result)
                    })
                else:
                    success, data, error = result
                    processed_results.append({
                        "match": matches[i],
                        "success": success,
                        "data": data,
                        "error": error
                    })
            except Exception as process_error:
                logger.error(f"Ошибка при обработке результата для матча {matches[i]}: {process_error}")
                processed_results.append({
                    "match": matches[i],
                    "success": False,
                    "error": str(process_error)
                })
        logger.info(f"Получены данные для {len(processed_results)} матчей")
        return processed_results
# === НОВЫЕ УТИЛИТЫ ДЛЯ ЭТАПА 2.1 ===
# Импорты перемещены в начало файла
def build_features(fixtures: pd.DataFrame) -> pd.DataFrame:
    df = fixtures.copy()
    # Примеры безопасных фичей (дообогатите по доступным полям из SportMonks)
    if "home_xg" in df.columns and "away_xg" in df.columns:
        df["xg_diff"] = df["home_xg"] - df["away_xg"]
    if "home_form" in df.columns and "away_form" in df.columns:
        df["form_diff"] = df["home_form"] - df["away_form"]
    if "is_home" not in df.columns:
        df["is_home"] = 1
    # Добавлено: Проверка и добавление PPDA и стилевых признаков
    if "home_ppda_for" in df.columns and "away_ppda_against" in df.columns:
        df["home_ppda_net"] = df["home_ppda_for"] - df["away_ppda_against"]
    if "away_ppda_for" in df.columns and "home_ppda_against" in df.columns:
        df["away_ppda_net"] = df["away_ppda_for"] - df["home_ppda_against"]
    if "style_mismatch_index" in df.columns:
        df["style_mismatch"] = df["style_mismatch_index"]
    # Добавлено: one-hot по лигам/сезонам
    if "league_id" in df.columns:
        league_dummies = pd.get_dummies(df["league_id"], prefix="league")
        df = pd.concat([df, league_dummies], axis=1)
    if "season_id" in df.columns:
        season_dummies = pd.get_dummies(df["season_id"], prefix="season")
        df = pd.concat([df, season_dummies], axis=1)
    # Добавлено: стандартизация метрик внутри лиги (пример для xg)
    if "league_id" in df.columns and "home_xg" in df.columns and "away_xg" in df.columns:
        # Рассчитываем средние и стандартные отклонения по лигам для xg
        league_stats = df.groupby("league_id")[["home_xg", "away_xg"]].agg(['mean', 'std']).reset_index()
        league_stats.columns = ['league_id', 'home_xg_mean', 'home_xg_std', 'away_xg_mean', 'away_xg_std']
        # Объединяем с основным DataFrame
        df = df.merge(league_stats, on="league_id", how="left")
        # Применяем стандартизацию
        df["home_xg_z"] = (df["home_xg"] - df["home_xg_mean"]) / df["home_xg_std"]
        df["away_xg_z"] = (df["away_xg"] - df["away_xg_mean"]) / df["away_xg_std"]
        # Заполняем NaN, если стандартное отклонение равно 0
        df["home_xg_z"] = df["home_xg_z"].fillna(0)
        df["away_xg_z"] = df["away_xg_z"].fillna(0)
    return df
def compute_time_decay_weights(df: pd.DataFrame, *, date_col: str, half_life_days: int) -> np.ndarray:
    t = pd.to_datetime(df[date_col]); t0 = t.max()
    days = (t0 - t).dt.days.clip(lower=0)
    return (0.5 ** (days / max(half_life_days,1))).to_numpy()
def make_time_series_splits(
    df: pd.DataFrame, *, date_col: str, n_splits: int, min_train_days: int, gap_days: int = 0
) -> List[Tuple[np.ndarray, np.ndarray]]:
    t = pd.to_datetime(df[date_col])
    order = np.argsort(t.values)
    df_sorted = df.iloc[order].reset_index(drop=True)
    splits = []; N = len(df_sorted)
    for fold in range(1, n_splits+1):
        split_point = int(N * fold/(n_splits+1))
        if split_point <= 0 or split_point >= N: continue
        t_cut = df_sorted.loc[split_point, date_col]
        train_mask = df_sorted[date_col] <= (t_cut - pd.Timedelta(days=gap_days))
        if (df_sorted[date_col].max() - df_sorted[date_col].min()).days < min_train_days:
            continue
        train_idx = df_sorted.index[train_mask].to_numpy()
        valid_idx = df_sorted.index[~train_mask].to_numpy()
        splits.append((order[train_idx], order[valid_idx]))
    return splits
# === КОНЕЦ НОВЫХ УТИЛИТ ===
# Создание экземпляра процессора данных
data_processor = DataProcessor()
