"""
@file: test_cache_postgres.py
@description: Unit tests for Redis cache helpers in database/cache_postgres.py.
@dependencies: database/cache_postgres.py, pytest
@created: 2025-09-16
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from database import cache_postgres


class _DummySettings:
    CACHE_VERSION = "vtest"
    TTL = {"lineups_fast": 123, "custom": 42}
    REDIS_URL = "redis://example:6379/5"


class _FakeRedisClient:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.ping_called = False
        self.set_calls: list[tuple[str, int | None, str]] = []
        self.setex_calls: list[tuple[str, int, str]] = []
        self.delete_calls: list[str] = []

    async def ping(self) -> None:
        self.ping_called = True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self.storage[key] = value
        self.setex_calls.append((key, ttl, value))
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.storage[key] = value
        self.set_calls.append((key, ex, value))
        return True

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def delete(self, key: str) -> int:
        existed = key in self.storage
        if existed:
            del self.storage[key]
        self.delete_calls.append(key)
        return 1 if existed else 0

    async def close(self) -> None:  # pragma: no cover - compatibility stub
        return None


@pytest.mark.asyncio
async def test_versioned_key_uses_cache_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_postgres, "get_settings", lambda: _DummySettings())
    result = cache_postgres.versioned_key("lineup", 10)
    assert result == "vtest:lineup:10"


@pytest.mark.asyncio
async def test_set_with_ttl_serializes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(cache_postgres, "get_settings", lambda: _DummySettings())

    payload = {"foo": "bar"}
    ok = await cache_postgres.set_with_ttl(fake_redis, "cache:key", payload, "lineups_fast")

    assert ok is True
    assert fake_redis.setex_calls[0][0] == "cache:key"
    assert fake_redis.setex_calls[0][1] == _DummySettings.TTL["lineups_fast"]
    assert json.loads(fake_redis.setex_calls[0][2]) == payload


@pytest.mark.asyncio
async def test_connect_to_redis_initializes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedisClient()

    def _fake_from_url(url: str, *, encoding: str, decode_responses: bool) -> _FakeRedisClient:
        assert url == _DummySettings.REDIS_URL
        assert encoding == "utf-8"
        assert decode_responses is True
        return fake_redis

    monkeypatch.setattr(cache_postgres, "get_settings", lambda: _DummySettings())
    monkeypatch.setattr(cache_postgres, "from_url", _fake_from_url)

    manager = cache_postgres.CacheManager()
    await manager.connect_to_redis()

    assert manager.redis_client is fake_redis
    assert fake_redis.ping_called is True


@pytest.mark.asyncio
async def test_get_lineup_cached_returns_cached_value(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(cache_postgres, "get_settings", lambda: _DummySettings())
    key = cache_postgres.versioned_key("lineup", 55)
    fake_redis.storage[key] = json.dumps({"lineup": [1, 2, 3]})

    manager = cache_postgres.CacheManager()
    manager.redis_client = fake_redis

    result = await manager.get_lineup_cached(55)
    assert result == {"lineup": [1, 2, 3]}


@pytest.mark.asyncio
async def test_get_lineup_cached_fetches_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(cache_postgres, "get_settings", lambda: _DummySettings())

    cached_args: dict[str, Any] = {}

    async def _fake_fetch(match_id: int) -> dict[str, Any] | None:
        return {"match_id": match_id, "players": []}

    async def _fake_set_with_ttl(client: Any, key: str, value: Any, ttl_name: str) -> bool:
        cached_args["key"] = key
        cached_args["value"] = value
        cached_args["ttl_name"] = ttl_name
        return True

    monkeypatch.setattr(cache_postgres, "fetch_lineup_api", _fake_fetch)
    monkeypatch.setattr(cache_postgres, "set_with_ttl", _fake_set_with_ttl)

    manager = cache_postgres.CacheManager()
    manager.redis_client = fake_redis

    result = await manager.get_lineup_cached(77)

    assert result == {"match_id": 77, "players": []}
    assert cached_args["ttl_name"] == "lineups_fast"
    assert cached_args["key"] == cache_postgres.versioned_key("lineup", 77)
    assert cached_args["value"] == {"match_id": 77, "players": []}


@pytest.mark.asyncio
async def test_invalidate_lineups_handles_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(cache_postgres, "get_settings", lambda: _DummySettings())

    manager = cache_postgres.CacheManager()
    manager.redis_client = fake_redis

    removed = await manager.invalidate_lineups(101)
    assert removed is False
    assert fake_redis.delete_calls == [cache_postgres.versioned_key("lineup", 101)]
