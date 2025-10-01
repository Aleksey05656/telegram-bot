"""
@file: database/cache_postgres.py
@description: Minimal in-memory TTL cache emulating Redis helpers for unit tests and offline runs.
@dependencies: config.get_settings, time.monotonic
@created: 2025-09-29
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from time import monotonic
from typing import Any, Awaitable, Callable

from config import get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover - redis not installed in test env

    class Redis:  # type: ignore[no-redef]
        """Minimal shim providing ``from_url`` for offline environments."""

        @staticmethod
        def from_url(*_args: Any, **_kwargs: Any) -> "_InMemoryRedis":
            return _InMemoryRedis()


@dataclass(slots=True)
class _CacheEntry:
    value: Any
    expire_at: float | None


class _InMemoryRedis:
    """Async-friendly Redis stub storing JSON payloads in memory."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float | None]] = {}

    async def ping(self) -> None:
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        expire_at = monotonic() + ttl if ttl > 0 else None
        self._values[key] = (value, expire_at)
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        ttl = int(ex or 0)
        return await self.setex(key, ttl, value)

    async def get(self, key: str) -> str | None:
        entry = self._values.get(key)
        if not entry:
            return None
        value, expire_at = entry
        if expire_at is not None and expire_at <= monotonic():
            self._values.pop(key, None)
            return None
        return value

    async def delete(self, key: str) -> int:
        existed = key in self._values
        self._values.pop(key, None)
        return 1 if existed else 0

    async def close(self) -> None:
        self._values.clear()
        return None


def _redis_url() -> str | None:
    url = os.getenv("REDIS_URL")
    if url:
        return url
    host = os.getenv("REDIS_HOST")
    if not host:
        return None
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    password = os.getenv("REDIS_PASSWORD")
    scheme = "rediss" if os.getenv("REDIS_SSL") in {"1", "true", "True"} else "redis"
    auth = f":{password}@" if password else ""
    return f"{scheme}://{auth}{host}:{port}/{db}"


def _safe_url_repr(url: str) -> str:
    if url.startswith("rediss://"):
        return "rediss://***"
    if url.startswith("redis://"):
        return "redis://***"
    return "***"


def _sanitize_exception(exc: Exception, url: str | None) -> str:
    message = str(exc)
    if url:
        message = message.replace(url, _safe_url_repr(url))
    return message


def _json_default(value: Any) -> str:
    return str(value)


def versioned_key(prefix: str, *parts: Any) -> str:
    settings = get_settings()
    version = getattr(settings, "CACHE_VERSION", "v1")
    key_parts = [str(version), prefix]
    key_parts.extend(str(part) for part in parts if part is not None)
    return ":".join(filter(None, key_parts))


class CacheManager:
    """In-memory TTL cache with optional Redis shim for fixtures."""

    def __init__(self) -> None:
        self._entries: dict[str, _CacheEntry] = {}
        self.redis_client: Any | None = None

    # Generic TTL cache helpers -------------------------------------------------
    def _resolve_ttl(self, ttl_name: str) -> float | None:
        ttl_map = getattr(get_settings(), "TTL", {})
        raw_ttl = ttl_map.get(ttl_name)
        try:
            ttl_value = float(raw_ttl)
        except (TypeError, ValueError):
            return None
        if ttl_value <= 0:
            return None
        return ttl_value

    def _store(self, key: str, value: Any, ttl_seconds: float | None) -> None:
        expire_at = monotonic() + ttl_seconds if ttl_seconds and ttl_seconds > 0 else None
        self._entries[key] = _CacheEntry(value=value, expire_at=expire_at)

    def _get_entry(self, key: str) -> _CacheEntry | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expire_at is not None and entry.expire_at <= monotonic():
            self._entries.pop(key, None)
            return None
        return entry

    async def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        self._store(key, value, ttl)
        return True

    async def set_with_ttl_config(self, key: str, value: Any, ttl_name: str) -> bool:
        ttl = self._resolve_ttl(ttl_name)
        return await self.set(key, value, ttl)

    async def get(self, key: str) -> Any | None:
        entry = self._get_entry(key)
        return entry.value if entry else None

    async def delete(self, key: str) -> bool:
        existed = key in self._entries
        self._entries.pop(key, None)
        return existed

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[Any]] | Callable[[], Any],
        ttl_name: str | None = None,
        *,
        ttl: float | None = None,
    ) -> tuple[Any, bool]:
        cached = await self.get(key)
        if cached is not None:
            return cached, True
        result = factory()
        value = await result if isinstance(result, Awaitable) else result
        effective_ttl = ttl
        if effective_ttl is None and ttl_name is not None:
            effective_ttl = self._resolve_ttl(ttl_name)
        await self.set(key, value, effective_ttl)
        return value, False

    async def clear(self) -> None:
        self._entries.clear()

    # Redis-specific helpers ----------------------------------------------------
    async def use_memory(self) -> None:
        await self._close_redis_client()
        self.redis_client = _InMemoryRedis()

    async def use_redis(self, client: Any) -> None:
        await self._close_redis_client()
        self.redis_client = client

    async def connect_to_redis(self) -> None:
        url = _redis_url()
        if not url:
            logger.info("cache: Redis disabled, using in-memory backend")
            await self.use_memory()
            return None

        try:
            client = Redis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            if isinstance(client, Awaitable):
                client = await client  # type: ignore[assignment]
            pong = await client.ping()
            logger.info(
                "cache: connected to Redis (pong=%s, url=%s)",
                pong,
                _safe_url_repr(url),
            )
            await self.use_redis(client)
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning(
                "cache: Redis unavailable, falling back to memory: %s",
                _sanitize_exception(exc, url),
            )
            await self.use_memory()
        return None

    async def _close_redis_client(self) -> None:
        client = self.redis_client
        self.redis_client = None
        if client is not None:
            closer = getattr(client, "close", None)
            if callable(closer):
                result = closer()
                if isinstance(result, Awaitable):
                    await result

    async def get_lineup_cached(self, match_id: int) -> Any | None:
        key = versioned_key("lineup", match_id)
        client = self.redis_client
        if client is None:
            return None
        getter = getattr(client, "get", None)
        if not callable(getter):
            return None
        cached = getter(key)
        if isinstance(cached, Awaitable):
            cached = await cached
        if cached is not None:
            try:
                return json.loads(cached)
            except (TypeError, json.JSONDecodeError):
                return cached
        lineup = await fetch_lineup_api(match_id)
        if lineup is not None:
            await set_with_ttl(client, key, lineup, "lineups_fast")
        return lineup

    async def invalidate_lineups(self, match_id: int) -> bool:
        key = versioned_key("lineup", match_id)
        client = self.redis_client
        if client is None:
            return False
        deleter = getattr(client, "delete", None)
        if not callable(deleter):
            return False
        result = deleter(key)
        if isinstance(result, Awaitable):
            result = await result
        return bool(result)

    async def close(self) -> None:
        await self._close_redis_client()
        await self.clear()


cache = CacheManager()


async def set_with_ttl(redis_client: Any, key: str, value: Any, ttl_name: str) -> bool:
    ttl_map = getattr(get_settings(), "TTL", {})
    raw_ttl = ttl_map.get(ttl_name)
    try:
        ttl_seconds = int(raw_ttl)
    except (TypeError, ValueError):
        ttl_seconds = 0
    payload = json.dumps(value, default=_json_default)
    setter = getattr(redis_client, "setex", None)
    if callable(setter):
        result = setter(key, ttl_seconds, payload)
        if isinstance(result, Awaitable):
            await result
        return True
    fallback = getattr(redis_client, "set", None)
    if callable(fallback):
        kwargs: dict[str, Any] = {"ex": ttl_seconds} if ttl_seconds > 0 else {}
        result = fallback(key, payload, **kwargs)
        if isinstance(result, Awaitable):
            await result
        return True
    if isinstance(redis_client, CacheManager):
        await redis_client.set(key, value, float(ttl_seconds) if ttl_seconds > 0 else None)
        return True
    return False


async def init_cache() -> None:
    await cache.connect_to_redis()


async def shutdown_cache() -> None:
    await cache.close()


async def fetch_lineup_api(match_id: int) -> Any | None:  # pragma: no cover - override in tests
    return None


__all__ = [
    "cache",
    "set_with_ttl",
    "versioned_key",
    "init_cache",
    "shutdown_cache",
    "fetch_lineup_api",
]
