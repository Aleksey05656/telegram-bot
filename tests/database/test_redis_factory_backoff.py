"""
@file: tests/database/test_redis_factory_backoff.py
@description: Retry and masking behaviour for RedisFactory connections.
@dependencies: workers.redis_factory, pytest
@created: 2025-10-01
"""

from __future__ import annotations

import asyncio
import random
from itertools import chain, repeat

import pytest

import workers.redis_factory as redis_factory


class _StubLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def bind(self, **kwargs):
        self.records.append({"type": "bind", "kwargs": kwargs})
        return self

    def debug(self, message, *args) -> None:  # pragma: no cover - helper for completeness
        self.records.append({"level": "debug", "message": message, "args": args})

    def info(self, message, *args) -> None:  # pragma: no cover - helper for completeness
        self.records.append({"level": "info", "message": message, "args": args})

    def warning(self, message, *args) -> None:
        self.records.append({"level": "warning", "message": message, "args": args})

    def error(self, message, *args) -> None:  # pragma: no cover - helper for completeness
        self.records.append({"level": "error", "message": message, "args": args})


class _AsyncioProxy:
    def __init__(self, sleep_func):
        self._sleep = sleep_func

    async def sleep(self, delay: float) -> None:
        await self._sleep(delay)

    def __getattr__(self, name: str):  # pragma: no cover - defensive fallback
        return getattr(asyncio, name)


class _RandomProxy:
    def __init__(self, uniform_func):
        self._uniform = uniform_func

    def uniform(self, start: float, end: float) -> float:
        return self._uniform(start, end)

    def __getattr__(self, name: str):  # pragma: no cover - defensive fallback
        return getattr(random, name)


@pytest.mark.asyncio
async def test_ping_eventually_succeeds_with_backoff_and_jitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"count": 0}
    sleep_calls: list[float] = []
    jitter_values = chain([0.001, 0.002], repeat(0.0))

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    def fake_uniform(start: float, end: float) -> float:
        return next(jitter_values)

    monkeypatch.setattr(
        redis_factory,
        "asyncio",
        _AsyncioProxy(fake_sleep),
        raising=False,
    )
    monkeypatch.setattr(
        redis_factory,
        "random",
        _RandomProxy(fake_uniform),
        raising=False,
    )

    class FlakyRedis:
        def __init__(self) -> None:
            self.ping_calls = 0

        async def ping(self) -> None:
            self.ping_calls += 1
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError(f"ping failed {attempts['count']}")

        async def close(self) -> None:  # pragma: no cover - cleanup hook
            return None

    clients: list[FlakyRedis] = []

    def fake_from_url(*_args, **_kwargs) -> FlakyRedis:
        client = FlakyRedis()
        clients.append(client)
        return client

    monkeypatch.setattr(redis_factory, "from_url", fake_from_url)

    factory = redis_factory.RedisFactory(
        url="redis://:secret@test-redis:6379/0",
        max_retries=5,
        base_delay=0.05,
        max_delay=0.2,
        jitter=0.01,
    )

    client = await factory.get_client()

    assert client is clients[-1]
    assert attempts["count"] == 3
    assert sleep_calls == pytest.approx([0.051, 0.102])


@pytest.mark.asyncio
async def test_ping_failure_masks_dsn_and_raises_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    def fake_uniform(start: float, end: float) -> float:
        return 0.0

    monkeypatch.setattr(
        redis_factory,
        "asyncio",
        _AsyncioProxy(fake_sleep),
        raising=False,
    )
    monkeypatch.setattr(
        redis_factory,
        "random",
        _RandomProxy(fake_uniform),
        raising=False,
    )

    class FailingRedis:
        def __init__(self) -> None:
            self.ping_calls = 0

        async def ping(self) -> None:
            self.ping_calls += 1
            raise RuntimeError("redis down")

        async def close(self) -> None:  # pragma: no cover - cleanup hook
            return None

    def fake_from_url(*_args, **_kwargs) -> FailingRedis:
        return FailingRedis()

    stub_logger = _StubLogger()
    monkeypatch.setattr(redis_factory, "from_url", fake_from_url)
    monkeypatch.setattr(redis_factory, "logger", stub_logger)

    factory = redis_factory.RedisFactory(
        url="redis://user:secret@test-redis:6379/1",
        max_retries=2,
        base_delay=0.1,
        max_delay=0.5,
        jitter=0.0,
    )

    with pytest.raises(RuntimeError) as excinfo:
        await factory.get_client()

    message = str(excinfo.value).lower()
    assert "max" in message and "retry" in message
    assert len(sleep_calls) == 2

    for record in stub_logger.records:
        if record.get("type") == "bind" and "url" in record["kwargs"]:
            masked_url = str(record["kwargs"]["url"])
            assert "***" in masked_url
            assert "secret" not in masked_url
        if record.get("level") == "warning":
            formatted = record["message"]
            if record["args"]:
                formatted = formatted % record["args"]
            assert "***" in formatted
            assert "secret" not in formatted
