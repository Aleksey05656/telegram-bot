# services/sportmonks_client.py
"""Клиент для взаимодействия с API SportMonks."""
import hashlib
import json
import os
from datetime import date
from functools import wraps
from typing import Any

import aiohttp

from config import get_settings

# Исправлено: правильный импорт кэша
from database.cache_postgres import (  # Импортируем необходимые функции
    cache,
    set_with_ttl,
    versioned_key,
)
from logger import logger

# Глобальная сессия для повторного использования соединений
_session = None


# --- Добавлено: Функция инвалидации кэша лайнапов ---
async def invalidate_fixture_lineups(match_id: int):
    """Инвалидация (удаление) кэша лайнапа для конкретного матча."""
    if cache:
        try:
            await cache.invalidate_lineups(match_id)
            logger.info(f"Кэш лайнапа для матча {match_id} инвалидирован.")
        except Exception as e:
            logger.error(f"Ошибка при инвалидации кэша лайнапа для матча {match_id}: {e}")


# --- Конец добавления ---
# --- Добавлено: Заглушка для fetch_lineup_api ---
# Предполагается, что основная логика получения лайнапа уже реализована в get_lineups
async def fetch_lineup_api(fixture_id: int) -> dict[str, Any] | None:
    """Заглушка для получения составов команд на матч напрямую из API."""
    # В реальной реализации это будет вызов существующей логики из get_lineups
    # без использования кэша или с принудительным обновлением кэша.
    # Например, можно создать временную копию get_lineups без декоратора @cached
    # или вызвать внутреннюю часть get_lineups напрямую.
    # Для демонстрации возвращаем результат из существующего метода.
    # ВАЖНО: Эта функция не должна использовать кэш внутри себя напрямую.
    # Заглушка: вместо прямого запроса к API возвращаем None.
    logger.debug(f"Заглушка fetch_lineup_api вызвана для матча {fixture_id}")
    return None  # Реализация зависит от внутренней структуры get_lineups


# --- Конец добавления ---
def cached(ttl: int = 300):
    """Декоратор для кеширования результатов функций через Redis кэш"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерируем ключ кэша из имени функции и аргументов
            cache_string = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
            cache_key = f"{func.__name__}:{hashlib.md5(cache_string.encode()).hexdigest()}"
            # Пытаемся получить данные из кэша
            try:
                cached_result = await cache.get(cache_key)
                if cached_result:
                    logger.debug(f"Данные для {func.__name__} получены из кэша")
                    return cached_result
            except Exception as e:
                logger.error(f"Ошибка при получении данных из кэша: {e}")
            # Если в кэше нет данных, вызываем функцию
            try:
                result = await func(*args, **kwargs)
                # Сохраняем результат в кэш
                try:
                    await cache.set(cache_key, result, ttl=ttl)
                    logger.debug(f"Результат {func.__name__} сохранен в кэш на {ttl} секунд")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении данных в кэш: {e}")
                return result
            except Exception as e:
                logger.error(f"Ошибка в функции {func.__name__}: {e}")
                raise

        return wrapper

    return decorator


async def get_session() -> aiohttp.ClientSession:
    """Получение или создание глобальной сессии aiohttp."""
    global _session
    if _session is None or _session.closed:
        # Создаем новую сессию с таймаутами
        timeout = aiohttp.ClientTimeout(total=30)
        _session = aiohttp.ClientSession(timeout=timeout)
        logger.debug("Создана новая aiohttp сессия")
    return _session


async def close_session():
    """Закрытие глобальной сессии aiohttp."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        logger.debug("aiohttp сессия закрыта")


class SportMonksClient:
    """Клиент для работы с API SportMonks."""

    def __init__(self, api_token: str = None):
        """Инициализация клиента API SportMonks."""
        self.api_token = api_token or get_settings().sportmonks_api_key
        self.base_url = "https://api.sportmonks.com/v3/football"
        if (not self.api_token) or (self.api_token.lower() == "dummy"):
            os.environ.setdefault("SPORTMONKS_STUB", "1")
            self.api_token = ""
        if not os.getenv("SPORTMONKS_STUB") and not self.api_token:
            raise ValueError("API token for SportMonks is required.")
        logger.info("SportMonksClient инициализирован")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение активной сессии HTTP."""
        return await get_session()

    @cached(ttl=3600)  # Кэшируем на 1 час
    async def get_fixture(self, fixture_id: int) -> dict[str, Any] | None:
        """Получение информации о конкретном матче.
        Args:
            fixture_id (int): ID матча в SportMonks
        Returns:
            Optional[Dict]: Данные о матче или None в случае ошибки
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/fixtures/{fixture_id}"
            params = {
                "api_token": self.api_token,
                "include": "localTeam,visitorTeam,venue",
            }
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data")
                else:
                    logger.error(
                        f"Ошибка получения данных матча {fixture_id}: статус {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Ошибка при получении данных матча {fixture_id}: {e}", exc_info=True)
            return None

    @cached(ttl=900)  # Кэшируем на 15 минут
    async def get_weather(self, team_id: int, match_date: date) -> dict[str, Any] | None:
        """Получение прогноза погоды для матча.
        Args:
            team_id (int): ID команды (для определения локации)
            match_date (date): Дата матча
        Returns:
            Optional[Dict]: Данные о погоде или None
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/weather/forecast"
            params = {
                "api_token": self.api_token,
                "team_id": team_id,
                "date": match_date.isoformat(),
            }
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data")
                else:
                    logger.warning(
                        f"Прогноз погоды для команды {team_id} на {match_date} недоступен: статус {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Ошибка при получении прогноза погоды для команды {team_id}: {e}",
                exc_info=True,
            )
            return None

    # --- Изменено: Использование специфичного TTL и инвалидации для лайнапов ---
    # @cached(ttl=120)  # Кэшируем на 2 минуты - Удалено
    async def get_lineups(self, fixture_id: int) -> dict[str, Any] | None:
        """Получение составов команд на матч.
        Args:
            fixture_id (int): ID матча
        Returns:
            Optional[Dict]: Составы команд или None
        """
        # Используем специализированную функцию кэширования с TTL["lineups_fast"]
        if cache:
            try:
                cached_lineups = await cache.get_lineup_cached(fixture_id)
                if cached_lineups is not None:
                    logger.debug(
                        f"Составы для матча {fixture_id} получены из кэша (специальный TTL)"
                    )
                    return cached_lineups
            except Exception as e:
                logger.error(f"Ошибка при получении составов из кэша для матча {fixture_id}: {e}")
        # Если в кэше нет данных, получаем их напрямую
        try:
            session = await self._get_session()
            url = f"{self.base_url}/fixtures/{fixture_id}"
            params = {"api_token": self.api_token, "include": "lineups.player"}
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    lineups_data = data.get("data", {}).get("lineups")
                    # Сохраняем в кэш с TTL["lineups_fast"]
                    if cache and lineups_data is not None:
                        try:
                            # Генерируем ключ с использованием versioned_key
                            key = versioned_key("lineup", fixture_id)
                            # Сохраняем с TTL["lineups_fast"]
                            await set_with_ttl(
                                cache.redis_client, key, lineups_data, "lineups_fast"
                            )
                            logger.debug(
                                f"Составы для матча {fixture_id} сохранены в кэш с TTL=lineups_fast"
                            )
                        except Exception as e:
                            logger.error(
                                f"Ошибка при сохранении составов в кэш для матча {fixture_id}: {e}"
                            )
                    return lineups_data
                else:
                    logger.warning(
                        f"Составы для матча {fixture_id} недоступны: статус {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Ошибка при получении составов для матча {fixture_id}: {e}",
                exc_info=True,
            )
            return None

    # --- Конец изменения ---
    @cached(ttl=120)  # Кэшируем на 2 минуты
    async def get_injuries(self, team_id: int) -> list[dict[str, Any]] | None:
        """Получение списка травмированных игроков команды.
        Args:
            team_id (int): ID команды
        Returns:
            Optional[List]: Список травм или None
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/teams/{team_id}"
            params = {"api_token": self.api_token, "include": "squad.player"}
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    squad_data = data.get("data", {}).get("squad", [])
                    # Фильтруем только травмированных игроков
                    injuries = [
                        player for player in squad_data if player.get("player", {}).get("injured")
                    ]
                    return injuries
                else:
                    logger.warning(
                        f"Информация о травмах команды {team_id} недоступна: статус {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Ошибка при получении информации о травмах команды {team_id}: {e}",
                exc_info=True,
            )
            return None

    @cached(ttl=3600)  # Кэшируем на 1 час
    async def get_table(self, fixture_id: int) -> dict[str, Any] | None:
        """Получение таблицы лиги.
        Args:
            fixture_id (int): ID матча (для определения лиги и сезона)
        Returns:
            Optional[Dict]: Таблица лиги или None
        """
        try:
            # Сначала получаем информацию о матче для определения лиги
            fixture = await self.get_fixture(fixture_id)
            if not fixture:
                return None
            league_id = fixture.get("league_id")
            season_id = fixture.get("season_id")
            if not league_id or not season_id:
                logger.error(f"Не удалось определить лигу или сезон для матча {fixture_id}")
                return None
            session = await self._get_session()
            url = f"{self.base_url}/tables/seasons/{season_id}"
            params = {"api_token": self.api_token, "include": "standings.team"}
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tables = data.get("data", [])
                    # Ищем таблицу для нужной лиги
                    for table in tables:
                        if table.get("league_id") == league_id:
                            # Получаем количество оставшихся туров (примерная логика)
                            # В реальной реализации это может потребовать дополнительного API вызова
                            rounds_left = 10  # Заглушка, в реальности нужно получить из API
                            return {
                                "standings": table.get("standings", []),
                                "rounds_left": rounds_left,
                            }
                    logger.warning(f"Таблица для лиги {league_id} не найдена")
                    return None
                else:
                    logger.error(
                        f"Ошибка получения таблицы для матча {fixture_id}: статус {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Ошибка при получении таблицы для матча {fixture_id}: {e}",
                exc_info=True,
            )
            return None

    @cached(ttl=3600)  # Кэшируем на 1 час
    async def get_last_team_matches(
        self,
        team_id: int,
        limit: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Получение последних матчей команды.
        Args:
            team_id (int): ID команды
            limit (int): Количество матчей
            date_from (Optional[str]): Начальная дата в формате YYYY-MM-DD
            date_to (Optional[str]): Конечная дата в формате YYYY-MM-DD
        Returns:
            List[Dict]: Список последних матчей
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/fixtures"
            params = {
                "api_token": self.api_token,
                "filter[participants]": team_id,
                "sort": "-starts_at",  # Сортировка по дате, последние первыми
                "per_page": limit,
            }
            # Добавляем фильтрацию по датам, если указана начальная дата
            if date_from:
                params["filter[from]"] = date_from
            if date_to:
                params["filter[to]"] = date_to
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("data", [])
                    # Обогащаем данные о матчах информацией о стадионах
                    for fixture in fixtures:
                        # Получаем информацию о стадионе (если доступна)
                        venue_data = fixture.get("venue", {})
                        if venue_data:
                            fixture["venue_lat"] = venue_data.get("latitude", 0)
                            fixture["venue_lon"] = venue_data.get("longitude", 0)
                            # Временная зона стадиона (если доступна)
                            fixture["tz"] = venue_data.get("timezone", 0)
                        # Определяем, является ли матч домашним для команды
                        home_team_id = fixture.get("localteam_id")
                        fixture["home"] = home_team_id == team_id
                        # Добавлено: Получаем составы для этого матча, если они есть
                        # Это необходимо для расчета суммарных минут ключевых игроков
                        # Предполагается, что get_lineups возвращает данные о составах для конкретного матча
                        # Запрос составов может замедлить ответ; пока пропускаем.
                    return fixtures
                else:
                    logger.error(
                        f"Ошибка получения последних матчей команды {team_id}: статус {response.status}"
                    )
                    return []
        except Exception as e:
            logger.error(
                f"Ошибка при получении последних матчей команды {team_id}: {e}",
                exc_info=True,
            )
            return []

    @cached(ttl=3600)  # Кэшируем на 1 час
    async def get_team_stats(self, team_id: int, date: str) -> dict[str, Any]:
        """Получение статистики команды.
        Args:
            team_id (int): ID команды
            date (str): Дата для получения актуальной статистики
        Returns:
            Dict: Статистика команды
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/teams/{team_id}"
            params = {"api_token": self.api_token, "include": "stats"}
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    stats_data = data.get("data", {}).get("stats", {})
                    # Обрабатываем статистику
                    result_stats = {
                        "team_id": team_id,
                        "team_name": data.get("data", {}).get("name", "Unknown"),
                    }
                    # Извлекаем нужные метрики
                    for stat in stats_data:
                        stat_name = stat.get("name", "")
                        stat_value = stat.get("value")
                        if stat_name == "PPDA":
                            result_stats["ppda"] = float(stat_value) if stat_value else 10.0
                        elif stat_name == "Shots":
                            result_stats["shots"] = stat_value
                        elif stat_name == "Shots On Target":
                            result_stats["shots_on_target"] = stat_value
                        elif stat_name == "Passes":
                            result_stats["passes"] = stat_value
                        elif stat_name == "Pass Accuracy":
                            result_stats["pass_accuracy"] = stat_value
                        elif stat_name == "Fouls":
                            result_stats["fouls"] = stat_value
                        elif stat_name == "Yellow Cards":
                            result_stats["yellow_cards"] = stat_value
                        elif stat_name == "Red Cards":
                            result_stats["red_cards"] = stat_value
                        elif stat_name == "Assists":
                            result_stats["assists"] = stat_value
                        elif stat_name == "Rating":
                            if isinstance(stat_value, int | float):
                                result_stats["rating"] = stat_value
                            elif isinstance(stat_value, str):
                                try:
                                    result_stats["rating"] = float(stat_value)
                                except ValueError:
                                    pass  # Игнорируем, если не удалось преобразовать
                        # Добавлено: обработка xG метрик
                        elif stat_name == "xG":
                            result_stats["xg_for"] = float(stat_value) if stat_value else None
                        elif stat_name == "xG Against":
                            result_stats["xg_against"] = float(stat_value) if stat_value else None
                    logger.debug(f"Получена статистика для команды ID {team_id}")
                    return result_stats
                else:
                    logger.error(
                        f"Ошибка получения статистики команды ID {team_id}: статус {response.status}"
                    )
                    # Возвращаем минимальную статистику в случае ошибки
                    return {
                        "team_id": team_id,
                        "team_name": "Unknown",
                        "ppda": 10.0,
                        "xg_for": None,
                        "xg_against": None,
                        "passes": None,
                        "pass_accuracy": None,
                        "tackles": None,
                        "interceptions": None,
                        "shots": None,
                        "shots_on_target": None,
                        "possession": None,
                        "fouls": None,
                        "yellow_cards": None,
                        "red_cards": None,
                        "goals_scored": None,
                        "goals_conceded": None,
                        "clean_sheets": None,
                        "btts": None,
                        "rating": None,
                        "assists": None,
                    }
        except Exception as e:
            logger.error(
                f"Ошибка при обработке статистики команды ID {team_id}: {e}",
                exc_info=True,
            )
            # Возвращаем минимальную статистику в случае ошибки
            return {
                "team_id": team_id,
                "team_name": "Unknown",
                "ppda": 10.0,
                "xg_for": None,
                "xg_against": None,
                "passes": None,
                "pass_accuracy": None,
                "tackles": None,
                "interceptions": None,
                "shots": None,
                "shots_on_target": None,
                "possession": None,
                "fouls": None,
                "yellow_cards": None,
                "red_cards": None,
                "goals_scored": None,
                "goals_conceded": None,
                "clean_sheets": None,
                "btts": None,
                "rating": None,
                "assists": None,
            }

    @cached(ttl=86400)  # Кэшируем на 24 часа
    async def get_team_by_name(self, team_name: str) -> dict[str, Any] | None:
        """Получение информации о команде по названию.
        Args:
            team_name (str): Название команды
        Returns:
            Optional[Dict]: Информация о команде или None
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/teams/search/{team_name}"
            params = {"api_token": self.api_token}
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    teams = data.get("data", [])
                    if teams:
                        return teams[0]  # Возвращаем первую найденную команду
                    else:
                        logger.warning(f"Команда с названием '{team_name}' не найдена")
                        return None
                else:
                    logger.error(f"Ошибка поиска команды '{team_name}': статус {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при поиске команды '{team_name}': {e}", exc_info=True)
            return None

    @cached(ttl=300)  # Кэшируем на 5 минут
    async def get_upcoming_fixture(
        self, home_team_id: int, away_team_id: int
    ) -> dict[str, Any] | None:
        """Получение информации о предстоящем матче между двумя командами.
        Args:
            home_team_id (int): ID домашней команды
            away_team_id (int): ID гостевой команды
        Returns:
            Optional[Dict]: Информация о матче или None
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/fixtures/between/{home_team_id}/{away_team_id}"
            params = {"api_token": self.api_token, "include": "league,season"}
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("data", [])
                    if fixtures:
                        # Возвращаем ближайший предстоящий матч
                        for fixture in fixtures:
                            if fixture.get("status") == "NS":  # Not Started
                                return fixture
                        # Если нет предстоящих матчей, возвращаем первый из списка
                        return fixtures[0] if fixtures else None
                    else:
                        logger.warning(
                            f"Матч между командами {home_team_id} и {away_team_id} не найден"
                        )
                        return None
                else:
                    logger.error(
                        f"Ошибка поиска матча между {home_team_id} и {away_team_id}: статус {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Ошибка при поиске матча между {home_team_id} и {away_team_id}: {e}",
                exc_info=True,
            )
            return None

    @cached(ttl=900)  # Используйте TTL из settings, если нужно
    async def get_fixtures(
        self,
        league_id: int,
        season_id: int,
        date_from: str | None = None,
        date_to: str | None = None,
        next_fixtures: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Получение матчей по лиге и сезону.
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/fixtures"
            params = {
                "api_token": self.api_token,
                "filter[league_id]": league_id,
                "filter[season_id]": season_id,
                "per_page": 100,  # Максимальное количество на странице
                "sort": "starts_at",  # Сортировка по дате начала
            }

            # Добавляем фильтрацию по датам
            if date_from:
                params["filter[from]"] = date_from
            if date_to:
                params["filter[to]"] = date_to

            # Если нужны только предстоящие матчи
            if next_fixtures:
                params["filter[status]"] = "NS"  # Not Started

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("data", [])
                    logger.debug(
                        f"Получено {len(fixtures)} матчей для лиги {league_id}, сезона {season_id}"
                    )
                    return fixtures
                else:
                    logger.error(
                        f"Ошибка получения матчей для лиги {league_id}, сезона {season_id}: статус {response.status}"
                    )
                    return []
        except Exception as e:
            logger.error(
                f"Ошибка при получении матчей для лиги {league_id}, сезона {season_id}: {e}",
                exc_info=True,
            )
            return []


# Создание экземпляра клиента
sportmonks_client = SportMonksClient()
