"""
@file: workers/redis_factory.py
@description: Lazy Redis client factory with masking and graceful fallbacks.
@dependencies: redis.asyncio (optional), config.get_settings
@created: 2025-09-20
"""
from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from config import get_settings
from logger import logger

try:  # pragma: no cover - optional dependency in tests
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None  # type: ignore[assignment]


if redis is None:  # pragma: no cover - offline fallback
    Redis = Any  # type: ignore[assignment]
else:  # pragma: no cover - type alias for readability
    Redis = redis.Redis


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

    def __init__(
        self,
        *,
        url: str | None = None,
        client: Redis | None = None,
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 1.0,
        jitter: float = 0.05,
    ) -> None:
        self._configured_url = url
        self._client: Redis | None = client
        self._max_retries = max(0, int(max_retries))
        self._base_delay = max(0.0, float(base_delay))
        self._max_delay = (
            max(self._base_delay, float(max_delay))
            if max_delay is not None
            else self._base_delay
        )
        self._jitter = max(0.0, float(jitter))

    def _url(self) -> str:
        if self._configured_url is not None:
            return self._configured_url
        settings = get_settings()
        return settings.REDIS_URL

    async def _sleep_with_backoff(self, attempt: int) -> None:
        if self._base_delay <= 0:
            return
        delay = self._base_delay * (2 ** (attempt - 1))
        delay = min(delay, self._max_delay)
        if self._jitter > 0:
            delay += random.uniform(0.0, self._jitter)
        if delay > 0:
            await asyncio.sleep(delay)

    async def get_client(self) -> Redis | None:
        if self._client is not None:
            return self._client
        if redis is None:  # dependency missing
            logger.warning("redis.asyncio module unavailable; skipping Redis connection")
            return None
        url = self._url()
        masked_url = _mask(url)
        attempt = 0
        while True:
            client: Redis | None = None
            try:
                client = redis.from_url(url, encoding="utf-8", decode_responses=True)
                await client.ping()
            except Exception as exc:  # pragma: no cover - network dependency in tests
                if client is not None:
                    try:
                        await client.close()
                    except Exception as close_exc:  # pragma: no cover - defensive cleanup
                        logger.debug("Redis client close failed: %s", close_exc)
                logger.bind(event="redis.connect", url=masked_url, attempt=attempt + 1).warning(
                    "Redis connection failed for %s: %s",
                    masked_url,
                    exc,
                )
                if attempt >= self._max_retries:
                    raise RuntimeError(
                        f"Redis connection failed after max retry attempts ({self._max_retries})"
                    ) from exc
                attempt += 1
                await self._sleep_with_backoff(attempt)
                continue
            self._client = client
            logger.debug("Redis connection initialised for %s", masked_url)
            return self._client

    @asynccontextmanager
    async def client(self) -> AsyncIterator[Redis | None]:
        client = await self.get_client()
        yield client

    async def health_check(self) -> None:
        """Ensure Redis is reachable and responsive."""

        if redis is None:
            raise RuntimeError("redis.asyncio module is unavailable")
        url = self._url()
        masked_url = _mask(url)
        logger.bind(event="redis.health_check", url=masked_url).info(
            "Verifying Redis connectivity"
        )
        client = await self.get_client()
        if client is None:
            raise RuntimeError("Redis client could not be initialised")
        try:
            await client.ping()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.bind(
                event="redis.health_check", url=masked_url, error=str(exc)
            ).error("Redis ping failed")
            raise RuntimeError("Redis ping failed") from exc
        logger.bind(event="redis.health_check", url=masked_url).info(
            "Redis connection healthy"
        )

    async def close(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.close()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Redis client close failed: %s", exc)
        finally:
            self._client = None
