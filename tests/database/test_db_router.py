"""
@file: test_db_router.py
@description: Unit tests for the async DB router covering backend detection and session behavior.
@dependencies: database.db_router, pytest
@created: 2025-09-17
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from database.db_router import DatabaseBackend, DatabaseConfigurationError, DBRouter

AIOSQLITE_INSTALLED = importlib.util.find_spec("aiosqlite") is not None


class _DummyConnection:
    async def __aenter__(self) -> _DummyConnection:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # pragma: no cover - stub
        return False

    async def execute(self, *_args, **_kwargs) -> None:  # pragma: no cover - stub
        return None


class _DummyEngine:
    async def connect(self) -> _DummyConnection:
        return _DummyConnection()

    async def dispose(self) -> None:  # pragma: no cover - stub
        return None


@pytest.fixture()
def stub_sqlite_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    def _factory(*_args, **_kwargs) -> _DummyEngine:
        return _DummyEngine()

    monkeypatch.setattr("database.db_router.create_async_engine", _factory)
    return None


@pytest.mark.asyncio()
async def test_detects_sqlite_backend(tmp_path: Path, stub_sqlite_engine: None) -> None:
    db_path = tmp_path / "router.sqlite"
    router = DBRouter(dsn=f"sqlite:///{db_path}")

    assert router.backend is DatabaseBackend.SQLITE
    assert router.writer_options.dsn.startswith("sqlite+aiosqlite")
    await router.shutdown()


@pytest.mark.asyncio()
async def test_detects_postgres_backend() -> None:
    router = DBRouter(dsn="postgresql://user:pass@localhost:5432/testdb", statement_timeout_ms=1234)

    assert router.backend is DatabaseBackend.POSTGRESQL
    assert router.writer_options.dsn.startswith("postgresql+asyncpg")
    assert router.writer_options.statement_timeout_ms == 1234
    assert router.reader_options.dsn == router.writer_options.dsn
    await router.shutdown()


@pytest.mark.asyncio()
@pytest.mark.skipif(not AIOSQLITE_INSTALLED, reason="aiosqlite driver is required")
async def test_sqlite_read_write_sessions(tmp_path: Path) -> None:
    db_path = tmp_path / "session.sqlite"
    router = DBRouter(dsn=f"sqlite+aiosqlite:///{db_path}")
    await router.startup()

    async with router.session() as session:
        await session.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)"))
        await session.execute(text("INSERT INTO items (value) VALUES ('alpha')"))
        await session.commit()

    async with router.session(read_only=True) as session:
        result = await session.execute(text("SELECT value FROM items"))
        values = result.scalars().all()
        assert values == ["alpha"]

    await router.shutdown()


@pytest.mark.asyncio()
async def test_invalid_dsn_raises_configuration_error() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DBRouter(dsn="mysql://user:pass@localhost/db")
