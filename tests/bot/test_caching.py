"""
/**
 * @file: tests/bot/test_caching.py
 * @description: Validate TTL cache hit/miss behaviour and expiration.
 * @dependencies: app.bot.caching
 * @created: 2025-09-23
 */
"""

import asyncio

import pytest

from app.bot.caching import TTLCache


@pytest.mark.asyncio
async def test_ttl_cache_hit_and_miss() -> None:
    cache: TTLCache[str, int] = TTLCache(maxsize=2, ttl_seconds=0.2)
    value, hit = await cache.get_or_set("key", lambda: 1)
    assert value == 1
    assert hit is False
    value, hit = await cache.get_or_set("key", lambda: 2)
    assert hit is True
    assert value == 1
    await asyncio.sleep(0.25)
    assert await cache.get("key") is None
    stats = cache.stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
