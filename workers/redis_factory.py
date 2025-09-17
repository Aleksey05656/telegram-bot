"""
@file: workers/redis_factory.py
@description: Lazy Redis client factory with masking and graceful fallbacks.
@dependencies: redis.asyncio (optional), config.get_settings
@created: 2025-09-20
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from config import get_settings
from logger import logger

try:  # pragma: no cover - optional dependency in tests
    from redis.asyncio import Redis, from_url
except Exception:  # pragma: no cover
    Redis = Any  # type: ignore[assignment]
    from_url = None  # type: ignore[assignment]


def _mask(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    netloc = parts.netloc
    if "@" in netloc:
        _, host = netloc.rsplit("@", 1)
        netloc = f"***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class RedisFactory:
    """Factory providing shared Redis client instances for workers."""

    def __init__(self, *, url: str | None = None, client: Redis | None = None) -> None:
        self._configured_url = url
        self._client: Redis | None = client

    def _url(self) -> str:
        if self._configured_url is not None:
            return self._configured_url
        settings = get_settings()
        return settings.REDIS_URL

    async def get_client(self) -> Redis | None:
        if self._client is not None:
            return self._client
        if from_url is None:  # dependency missing
            logger.warning("redis.asyncio module unavailable; skipping Redis connection")
            return None
        url = self._url()
        try:
            client = from_url(url, encoding="utf-8", decode_responses=True)
            await client.ping()
        except Exception as exc:
            logger.warning("Redis connection failed for %s: %s", _mask(url), exc)
            return None
        logger.debug("Redis connection initialised for %s", _mask(url))
        self._client = client
        return self._client

    @asynccontextmanager
    async def client(self) -> AsyncIterator[Redis | None]:
        client = await self.get_client()
        yield client

    async def close(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.close()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Redis client close failed: %s", exc)
        finally:
            self._client = None
