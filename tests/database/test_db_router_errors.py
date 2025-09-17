"""
@file: tests/database/test_db_router_errors.py
@description: Tests for DBRouter configuration and health-check error paths.
@dependencies: database.db_router
@created: 2025-09-23
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from database.db_router import (
    DBRouter,
    DatabaseConfigurationError,
    DatabaseStartupError,
    get_db_router,
)


class DummyConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401 - interface requirement
        return False

    async def execute(self, statement):  # noqa: D401 - interface requirement
        return None


class HealthyEngine:
    def __init__(self):
        self.disposed = False

    def connect(self):
        return DummyConnection()

    async def dispose(self):
        self.disposed = True


class FailingConnection(DummyConnection):
    async def __aenter__(self):
        raise SQLAlchemyError("connect timeout")


class FailingEngine(HealthyEngine):
    def connect(self):
        return FailingConnection()


def test_invalid_dsn_raises_configuration_error() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DBRouter(dsn="not-a-dsn")


def test_get_db_router_falls_back_to_writer_when_read_only_missing(monkeypatch) -> None:
    engines: list[HealthyEngine] = []

    def _fake_create_engine(*args, **kwargs):  # noqa: D401 - monkeypatched factory
        engine = HealthyEngine()
        engines.append(engine)
        return engine

    monkeypatch.setattr("database.db_router.create_async_engine", _fake_create_engine)

    settings = SimpleNamespace(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_URL_RO="",
        DATABASE_URL_R=None,
        DATABASE_POOL_SIZE=5,
        DATABASE_MAX_OVERFLOW=5,
        DATABASE_POOL_TIMEOUT=5.0,
        DATABASE_CONNECT_TIMEOUT=5.0,
        DATABASE_STATEMENT_TIMEOUT_MS=1000,
        DATABASE_SQLITE_TIMEOUT=10.0,
        DATABASE_ECHO=False,
    )

    router = get_db_router(settings)
    assert router.reader_options.dsn == router.writer_options.dsn
    assert engines, "engine factory should be called"


@pytest.mark.asyncio
async def test_startup_failure_raises_database_startup_error(monkeypatch) -> None:
    monkeypatch.setattr("database.db_router.create_async_engine", lambda *args, **kwargs: FailingEngine())
    router = DBRouter(dsn="sqlite+aiosqlite:///:memory:")
    with pytest.raises(DatabaseStartupError):
        await router.startup()

