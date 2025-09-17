"""
@file: cache_postgres.py
@description: Async Redis cache helpers backed by configuration defaults.
@dependencies: redis.asyncio, config.get_settings
@created: 2025-09-15
"""

from __future__ import annotations

import json
from typing import Any, Optional

import asyncpg
from redis.asyncio import Redis, from_url
from redis.exceptions import ConnectionError as RedisConnectionError

# Импортируем только get_settings, не используем глобальный settings
from config import get_settings
from logger import logger

# Глобальные переменные для подключения
pool: asyncpg.Pool | None = None
cache: Optional["CacheManager"] = None


def versioned_key(prefix: str, *parts: Any) -> str:
    """Создать версионированный ключ кэша, используя CACHE_VERSION."""
    try:
        config = get_settings()
        key_parts = [config.CACHE_VERSION, prefix, *(str(part) for part in parts)]
        return ":".join(key_parts)
    except Exception as exc:  # pragma: no cover - защитный сценарий
        logger.error("Ошибка при создании версионированного ключа: %s", exc)
        suffix = ":".join(str(part) for part in parts)
        return f"{prefix}:{suffix}" if suffix else prefix


async def set_with_ttl(
    redis_client: Redis, key: str, value: Any, ttl_name: str
) -> bool:
    """
    Сохранение значения в кэш с TTL из конфигурации.
    Args:
        redis_client (Redis): Клиент Redis
        key (str): Ключ
        value (Any): Значение для сохранения
        ttl_name (str): Имя TTL в конфигурации
    Returns:
        bool: Успешность операции
    """
    try:
        config = get_settings()
        ttl = config.TTL.get(ttl_name)
        if ttl is None:
            logger.warning(f"Неизвестный TTL ключ: {ttl_name}, используем 3600 секунд")
            ttl = 3600
        serialized_value = json.dumps(value, ensure_ascii=False)
        await redis_client.setex(key, ttl, serialized_value)
        logger.debug(f"Значение сохранено в кэш с ключом {key}, TTL: {ttl} секунд")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении значения в кэш с TTL: {e}")
        return False


class CacheManager:
    """Менеджер для работы с Redis кэшем."""

    def __init__(self):
        """Инициализация менеджера кэша."""
        self.redis_client: Redis | None = None
        logger.info("Инициализация CacheManager")

    async def connect_to_redis(self):
        """Подключение к Redis."""
        try:
            config = get_settings()
            redis_url = config.REDIS_URL or "redis://localhost:6379/0"
            self.redis_client = from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
            # Простая проверка подключения
            await self.redis_client.ping()
            logger.info("✅ Подключение к Redis установлено")
        except RedisConnectionError as e:
            logger.error(f"❌ Не удалось подключиться к Redis: {e}")
            # Не останавливаем приложение, просто работаем без кэша
            self.redis_client = None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при подключении к Redis: {e}")
            self.redis_client = None

    async def get(self, key: str) -> Any | None:
        """Получение значения из Redis кэша.
        Args:
            key (str): Ключ для поиска
        Returns:
            Optional[Any]: Значение из кэша или None
        """
        if not self.redis_client:
            logger.debug("Redis клиент не инициализирован, пропуск get")
            return None
        try:
            value = await self.redis_client.get(key)
            if value is not None:
                # Десериализация из JSON
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении из Redis по ключу {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Сохранение значения в Redis кэш.
        Args:
            key (str): Ключ
            value (Any): Значение для сохранения
            ttl (int): Время жизни в секундах
        Returns:
            bool: Успешность операции
        """
        if not self.redis_client:
            logger.debug("Redis клиент не инициализирован, пропуск set")
            return False
        try:
            # Сериализация в JSON
            serialized_value = json.dumps(value, ensure_ascii=False)
            result = await self.redis_client.set(key, serialized_value, ex=ttl)
            return result
        except Exception as e:
            logger.error(f"Ошибка при записи в Redis по ключу {key}: {e}")
            return False

    async def set_with_ttl_config(self, key: str, value: Any, ttl_name: str) -> bool:
        """
        Сохранение значения в кэш с TTL из конфигурации.
        Args:
            key (str): Ключ
            value (Any): Значение для сохранения
            ttl_name (str): Имя TTL в конфигурации
        Returns:
            bool: Успешность операции
        """
        try:
            config = get_settings()
            ttl = config.TTL.get(ttl_name)
            if ttl is None:
                logger.warning(
                    f"Неизвестный TTL ключ: {ttl_name}, используем 3600 секунд"
                )
                ttl = 3600
            return await self.set(key, value, ttl)
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении значения в кэш с TTL из конфигурации: {e}"
            )
            return False

    async def delete(self, key: str) -> bool:
        """Удаление значения из Redis кэша.
        Args:
            key (str): Ключ для удаления
        Returns:
            bool: Успешность операции
        """
        if not self.redis_client:
            logger.debug("Redis клиент не инициализирован, пропуск delete")
            return False
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Ошибка при удалении из Redis по ключу {key}: {e}")
            return False

    async def close(self):
        """Закрытие подключения к Redis."""
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Подключение к Redis закрыто")
            except Exception as e:
                logger.error(f"Ошибка при закрытии подключения к Redis: {e}")

    # --- Добавлено: Методы для работы с лайнапами ---
    async def get_lineup_cached(self, match_id: int) -> Any | None:
        """Получение лайнапа из кэша с использованием специфичного TTL."""
        if not self.redis_client:
            logger.debug("Redis клиент не инициализирован, пропуск get_lineup_cached")
            return None
        try:
            key = versioned_key("lineup", match_id)
            value = await self.redis_client.get(key)
            if value is not None:
                return json.loads(value)
            # Если в кэше нет, получаем данные напрямую (через заглушку)
            lineup = await fetch_lineup_api(match_id)
            if lineup is not None:
                await set_with_ttl(self.redis_client, key, lineup, "lineups_fast")
            return lineup
        except Exception as e:
            logger.error(
                f"Ошибка при получении лайнапа из кэша для матча {match_id}: {e}"
            )
            return None

    async def invalidate_lineups(self, match_id: int) -> bool:
        """Инвалидация (удаление) кэша лайнапа для конкретного матча."""
        if not self.redis_client:
            logger.debug("Redis клиент не инициализирован, пропуск invalidate_lineups")
            return False
        try:
            key = versioned_key("lineup", match_id)
            result = await self.redis_client.delete(key)
            success = result > 0
            if success:
                logger.info(f"Кэш лайнапа для матча {match_id} успешно удален.")
            else:
                logger.debug(
                    f"Кэш лайнапа для матча {match_id} не найден для удаления."
                )
            return success
        except Exception as e:
            logger.error(
                f"Ошибка при инвалидации кэша лайнапа для матча {match_id}: {e}"
            )
            return False

    # --- Конец добавления ---


# --- Добавлено: Заглушка для fetch_lineup_api ---
# Предполагается, что реальная логика получения лайнапа будет реализована отдельно.
# Это может быть вызов API напрямую или другая функция.
async def fetch_lineup_api(match_id: int) -> Any | None:
    """Заглушка для получения составов команд на матч напрямую из API."""
    # Реализация зависит от архитектуры проекта.
    # Может быть вызов к SportMonksClient без использования кэша внутри.
    # Например, можно создать временную копию get_lineups без декоратора @cached
    # или вызвать внутреннюю часть get_lineups напрямую.
    # Пока используем заглушку.
    logger.debug(
        f"Заглушка fetch_lineup_api (cache_postgres) вызвана для матча {match_id}"
    )
    return None  # Реализация зависит от внутренней структуры получения данных


# --- Конец добавления ---


async def init_cache():
    """Инициализация кэша Redis."""
    global pool, cache
    # Инициализация Redis кэша
    cache = CacheManager()
    await cache.connect_to_redis()
    # Примечание: Инициализация asyncpg.Pool для PostgreSQL
    # (если она была бы нужна отдельно) должна быть здесь.
    # В текущем коде основной кэш - это Redis.
    logger.info("Кэш (Redis) инициализирован")
