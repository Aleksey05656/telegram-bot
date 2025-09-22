"""
/**
 * @file: tests/database/test_db_router_fallbacks.py
 * @description: Regression coverage for DBRouter fallback logic and failure handling.
 * @dependencies: database.db_router, pytest
 * @created: 2025-09-24
 */
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy.exc import SQLAlchemyError

from database.db_router import DBRouter, DatabaseConfigurationError, DatabaseStartupError


class _StubSession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.closed = False
        self.rollback_called = False

    async def execute(self, statement) -> None:  # noqa: D401 - test stub compatibility
        self.statements.append(str(statement))

    def in_transaction(self) -> bool:
        return False

    async def rollback(self) -> None:  # pragma: no cover - defensive stub
        self.rollback_called = True

    async def close(self) -> None:
        self.closed = True


def _stub_sessionmaker_factory(registry: list[_StubSession]) -> Callable[[], _StubSession]:
    def _factory() -> _StubSession:
        session = _StubSession()
        registry.append(session)
        return session

    return _factory


@pytest.mark.asyncio()
async def test_read_only_session_falls_back_to_writer_when_ro_dsn_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    created_engines: list[tuple[str, object]] = []

    def _fake_create_engine(dsn: str, *args, **kwargs) -> object:  # noqa: D401 - stub factory
        engine = object()
        created_engines.append((dsn, engine))
        return engine

    monkeypatch.setattr("database.db_router.create_async_engine", _fake_create_engine)

    sessions: list[_StubSession] = []
    monkeypatch.setattr(
        "database.db_router.async_sessionmaker",
        lambda *args, **kwargs: _stub_sessionmaker_factory(sessions),
    )

    router = DBRouter(dsn="postgresql://user:pass@localhost:5432/app", read_only_dsn="")

    assert router.reader_options.dsn == router.writer_options.dsn
    assert len(created_engines) == 1

    async with router.session(read_only=True) as session:
        assert session is sessions[-1]
        assert any("READ ONLY" in stmt for stmt in session.statements)

    assert any("READ WRITE" in stmt for stmt in sessions[-1].statements)
    assert sessions[-1].closed is True


def test_invalid_read_only_dsn_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("database.db_router.create_async_engine", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "database.db_router.async_sessionmaker", lambda *args, **kwargs: _stub_sessionmaker_factory([])
    )

    with pytest.raises(DatabaseConfigurationError):
        DBRouter(
            dsn="postgresql://user:pass@localhost:5432/app",
            read_only_dsn="redis://cache.example.com:6379/0",
        )


class _TimeoutConnection:
    async def __aenter__(self) -> "_TimeoutConnection":
        raise SQLAlchemyError("connect timeout")

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # pragma: no cover - stub protocol
        return False


class _TimeoutEngine:
    disposed: bool

    def __init__(self) -> None:
        self.disposed = False

    def connect(self) -> _TimeoutConnection:
        return _TimeoutConnection()

    async def dispose(self) -> None:
        self.disposed = True


@pytest.mark.asyncio()
async def test_startup_timeout_raises_database_startup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("database.db_router.async_sessionmaker", lambda *args, **kwargs: _stub_sessionmaker_factory([]))
    monkeypatch.setattr("database.db_router.create_async_engine", lambda *args, **kwargs: _TimeoutEngine())

    router = DBRouter(dsn="postgresql://user:pass@localhost:5432/app")

    with pytest.raises(DatabaseStartupError) as excinfo:
        await router.startup()

    assert str(excinfo.value) == "Database engine startup failed"
