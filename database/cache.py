# database/cache.py
"""Модуль для работы с кэшем Redis с поддержкой версионирования и TTL."""
import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from config import get_settings
from logger import logger

# Получаем настройки
settings = get_settings()


def _redis_url() -> str | None:
    url = getattr(settings, "REDIS_URL", None)
    if url:
        return url
    host = getattr(settings, "REDIS_HOST", None)
    if not host:
        return None
    port = getattr(settings, "REDIS_PORT", "6379")
    db = getattr(settings, "REDIS_DB", "0")
    password = getattr(settings, "REDIS_PASSWORD", None)
    ssl_flag = getattr(settings, "REDIS_SSL", None)
    scheme = "rediss" if str(ssl_flag).lower() in {"1", "true"} else "redis"
    auth = f":{password}@" if password else ""
    return f"{scheme}://{auth}{host}:{port}/{db}"


def _mask_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    netloc = parts.netloc
    if "@" in netloc:
        creds, host_part = netloc.split("@", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            creds = f"{user}:***"
        elif creds:
            creds = "***"
        else:
            creds = ":***"
        netloc = f"{creds}@{host_part}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class Cache:
    """Класс для работы с Redis кэшем."""

    def __init__(self):
        """Инициализация кэша Redis."""
        try:
            import redis

            redis_url = _redis_url()
            if not redis_url:
                logger.info("Redis URL не задан, кэш переключён в режим памяти")
                self.redis_client = None
                return
            self.redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            self.redis_client.ping()
            logger.info(
                "✅ Подключение к Redis установлено (url=%s)",
                _mask_url(redis_url),
            )
        except Exception as e:
            masked_url = _mask_url(redis_url) if "redis_url" in locals() and redis_url else None
            message = str(e)
            if masked_url and "redis_url" in locals() and redis_url:
                message = message.replace(redis_url, masked_url)
            logger.warning(
                "❌ Не удалось подключиться к Redis (url=%s): %s",
                masked_url,
                message,
            )
            self.redis_client = None

    def versioned_key(self, prefix: str, *parts) -> str:
        """
        Создание версионированного ключа для кэша.

        Args:
            prefix (str): Префикс ключа
            *parts: Части ключа

        Returns:
            str: Версионированный ключ
        """
        try:
            # Получаем версию кэша из настроек или используем значение по умолчанию
            cache_version = getattr(settings, "CACHE_VERSION", "v1")
            key_parts = [str(cache_version), prefix] + [str(part) for part in parts]
            return ":".join(key_parts)
        except Exception as e:
            logger.error(f"Ошибка при создании версионированного ключа: {e}")
            # Возвращаем ключ без версии в случае ошибки
            return f"{prefix}:" + ":".join(map(str, parts))

    def set_with_ttl(self, key: str, value: Any, ttl_name: str) -> bool:
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
            if not self.redis_client:
                logger.debug("Redis клиент не инициализирован, пропуск set_with_ttl")
                return False

            # Получаем TTL из конфигурации
            ttl_config = getattr(settings, "TTL", {})
            ttl = ttl_config.get(ttl_name, 3600)  # Значение по умолчанию 1 час

            # Сериализация значения
            if isinstance(value, dict | list):
                serialized_value = json.dumps(value, ensure_ascii=False)
            else:
                serialized_value = str(value)

            # Сохранение в Redis
            result = self.redis_client.setex(key, ttl, serialized_value)
            logger.debug(f"Значение сохранено в кэш с ключом {key}, TTL: {ttl} секунд")
            return result
        except Exception as e:
            logger.error(f"Ошибка при сохранении значения в кэш с TTL: {e}")
            return False

    def get(self, key: str) -> Any | None:
        """
        Получение значения из кэша.

        Args:
            key (str): Ключ для поиска

        Returns:
            Optional[Any]: Значение из кэша или None
        """
        try:
            if not self.redis_client:
                logger.debug("Redis клиент не инициализирован, пропуск get")
                return None

            value = self.redis_client.get(key)
            if value is not None:
                try:
                    # Пытаемся десериализовать как JSON
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Если не JSON, возвращаем как строку
                    return value
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении значения из кэша по ключу {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Сохранение значения в кэш.

        Args:
            key (str): Ключ
            value (Any): Значение для сохранения
            ttl (int): Время жизни в секундах

        Returns:
            bool: Успешность операции
        """
        try:
            if not self.redis_client:
                logger.debug("Redis клиент не инициализирован, пропуск set")
                return False

            # Сериализация значения
            if isinstance(value, dict | list):
                serialized_value = json.dumps(value, ensure_ascii=False)
            else:
                serialized_value = str(value)

            result = self.redis_client.setex(key, ttl, serialized_value)
            return result
        except Exception as e:
            logger.error(f"Ошибка при записи в кэш по ключу {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Удаление значения из кэша.

        Args:
            key (str): Ключ для удаления

        Returns:
            bool: Успешность операции
        """
        try:
            if not self.redis_client:
                logger.debug("Redis клиент не инициализирован, пропуск delete")
                return False

            result = self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Ошибка при удалении из кэша по ключу {key}: {e}")
            return False


# Создание экземпляра кэша
cache = Cache()
