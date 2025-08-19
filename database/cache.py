# database/cache.py
"""Модуль для работы с кэшем Redis с поддержкой версионирования и TTL."""
import json
import pickle
from typing import Any, Optional, Union
from logger import logger
from config import get_settings

# Получаем настройки
settings = get_settings()

class Cache:
    """Класс для работы с Redis кэшем."""

    def __init__(self):
        """Инициализация кэша Redis."""
        try:
            import redis
            # Используем URL из settings или fallback на localhost
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            # Простая проверка подключения
            self.redis_client.ping()
            logger.info(f"✅ Подключение к Redis установлено по адресу {redis_url}")
        except Exception as e:
            logger.error(f"❌ Не удалось подключиться к Redis: {e}")
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
            cache_version = getattr(settings, 'CACHE_VERSION', 'v1')
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
            ttl_config = getattr(settings, 'TTL', {})
            ttl = ttl_config.get(ttl_name, 3600)  # Значение по умолчанию 1 час
            
            # Сериализация значения
            if isinstance(value, (dict, list)):
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

    def get(self, key: str) -> Optional[Any]:
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
            if isinstance(value, (dict, list)):
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