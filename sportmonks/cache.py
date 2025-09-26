"""
@file: cache.py
@description: Redis-backed cache helpers tailored for SportMonks data with TTL profiles.
@dependencies: database.cache_postgres, typing
@created: 2025-09-23
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from database.cache_postgres import cache, versioned_key
from logger import logger


class SportMonksCache:
    """Wrapper over project-wide async cache with typed helpers."""

    def __init__(self) -> None:
        self._cache = cache

    async def get_or_set(
        self,
        prefix: str,
        key_parts: tuple[Any, ...],
        ttl_name: str,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        if self._cache is None:
            return await loader()
        cache_key = versioned_key(prefix, *key_parts)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        value = await loader()
        if value is not None:
            try:
                await self._cache.set_with_ttl_config(cache_key, value, ttl_name)
            except AttributeError:
                await self._cache.set(cache_key, value)
            except Exception as exc:  # pragma: no cover - logging safety
                logger.error("sportmonks_cache_store_error", extra={"error": str(exc)})
        return value

    async def set_ttl(self, prefix: str, key_parts: tuple[Any, ...], ttl_name: str, value: Any) -> None:
        if self._cache is None:
            return
        cache_key = versioned_key(prefix, *key_parts)
        try:
            await self._cache.set_with_ttl_config(cache_key, value, ttl_name)
        except AttributeError:
            await self._cache.set(cache_key, value)
        except Exception as exc:  # pragma: no cover
            logger.error("sportmonks_cache_set_error", extra={"error": str(exc)})

    async def invalidate(self, prefix: str, key_parts: tuple[Any, ...]) -> None:
        if self._cache is None:
            return
        cache_key = versioned_key(prefix, *key_parts)
        try:
            await self._cache.delete(cache_key)
        except Exception as exc:  # pragma: no cover
            logger.error("sportmonks_cache_delete_error", extra={"error": str(exc)})


sportmonks_cache = SportMonksCache()
