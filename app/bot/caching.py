"""
/**
 * @file: app/bot/caching.py
 * @description: Lightweight async-friendly TTL cache with LRU eviction for bot queries.
 * @dependencies: asyncio, time, collections
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
from typing import Awaitable, Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class CacheEntry(Generic[V]):
    """Value wrapper storing expiration timestamp."""

    value: V
    expire_at: float


class TTLCache(Generic[K, V]):
    """Simple TTL cache with LRU eviction semantics."""

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 120.0) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._maxsize = maxsize
        self._default_ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._entries: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    async def get(self, key: K) -> V | None:
        async with self._lock:
            entry = self._entries.get(key)
            if not entry:
                self.misses += 1
                return None
            if entry.expire_at < monotonic():
                self._entries.pop(key, None)
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return entry.value

    async def set(self, key: K, value: V, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds or self._default_ttl
        expire_at = monotonic() + ttl
        async with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = CacheEntry(value=value, expire_at=expire_at)
            self._evict_if_needed()

    async def get_or_set(
        self,
        key: K,
        factory: Callable[[], Awaitable[V]] | Callable[[], V],
        ttl_seconds: float | None = None,
    ) -> tuple[V, bool]:
        """Return cached value or compute and store it."""

        cached = await self.get(key)
        if cached is not None:
            return cached, True
        result = factory()
        if isinstance(result, Awaitable):
            value = await result  # type: ignore[arg-type]
        else:
            value = result
        await self.set(key, value, ttl_seconds=ttl_seconds)
        return value, False

    async def invalidate(self, key: K) -> None:
        async with self._lock:
            self._entries.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, float]:
        return {
            "size": len(self._entries),
            "hits": float(self.hits),
            "misses": float(self.misses),
        }

    def _evict_if_needed(self) -> None:
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)


__all__ = ["TTLCache", "CacheEntry"]
