"""
@file: tests/scripts/test_prestart.py
@description: Prestart script failure scenarios and safety checks.
@dependencies: scripts.prestart
@created: 2025-09-23
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import scripts.prestart as prestart


def test_main_propagates_missing_env(monkeypatch) -> None:
    def _fake_run(coro):  # noqa: D401 - substitute for asyncio.run
        coro.close()
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    monkeypatch.setattr(prestart, "asyncio", SimpleNamespace(run=_fake_run))
    with pytest.raises(RuntimeError) as excinfo:
        prestart.main()
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)


def test_run_migrations_failure(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_upgrade(*args, **kwargs):  # noqa: D401 - stub alembic call
        calls.append("upgrade")
        raise RuntimeError("alembic failed")

    monkeypatch.setattr(prestart.command, "upgrade", _fake_upgrade)
    settings = SimpleNamespace(DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db")
    with pytest.raises(RuntimeError):
        prestart.run_migrations(settings)
    assert calls == ["upgrade"]


@pytest.mark.asyncio
async def test_database_health_check_failure(monkeypatch) -> None:
    class StubRouter:
        def __init__(self) -> None:
            self.shutdown_called = False

        @asynccontextmanager
        async def session(self, *, read_only=False):  # noqa: D401 - async context manager factory
            raise RuntimeError("db down")
            yield  # pragma: no cover - required for asynccontextmanager protocol

        async def shutdown(self) -> None:
            self.shutdown_called = True

        @property
        def reader_options(self):  # pragma: no cover - accessor only
            return SimpleNamespace(dsn="postgresql://user:***@host/db")

        @property
        def writer_options(self):  # pragma: no cover - accessor only
            return SimpleNamespace(dsn="postgresql://user:***@host/db")

    router = StubRouter()

    def _fake_get_router(settings):  # noqa: D401 - stub factory
        return router

    monkeypatch.setattr(prestart, "get_db_router", _fake_get_router)
    settings = SimpleNamespace(DATABASE_URL="postgresql://user:pass@host/db", DATABASE_URL_RO=None, DATABASE_URL_R=None)
    with pytest.raises(RuntimeError):
        await prestart.check_database(settings)
    assert router.shutdown_called is True


@pytest.mark.asyncio
async def test_redis_health_check_failure(monkeypatch) -> None:
    class StubFactory:
        def __init__(self) -> None:
            self.closed = False

        async def health_check(self) -> None:
            raise RuntimeError("redis timeout")

        async def close(self) -> None:
            self.closed = True

    factory = StubFactory()
    monkeypatch.setattr(prestart, "RedisFactory", lambda url: factory)
    settings = SimpleNamespace(REDIS_URL="redis://user:pass@host:6379/0")
    with pytest.raises(RuntimeError):
        await prestart.check_redis(settings)
    assert factory.closed is True

