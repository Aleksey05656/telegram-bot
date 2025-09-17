"""
@file: db_router.py
@description: Database router for async SQLAlchemy sessions with read/write separation.
@dependencies: sqlalchemy, config
@created: 2025-09-17
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from config import Settings, get_settings
from logger import logger

_DEFAULT_POOL_SIZE = 10
_DEFAULT_MAX_OVERFLOW = 10
_DEFAULT_POOL_TIMEOUT = 30.0
_DEFAULT_CONNECT_TIMEOUT = 10.0
_DEFAULT_STATEMENT_TIMEOUT_MS = 60_000
_DEFAULT_SQLITE_TIMEOUT = 30.0


class DatabaseBackend(Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class DatabaseConfigurationError(RuntimeError):
    """Raised when DSN configuration is invalid or unsupported."""


class DatabaseStartupError(RuntimeError):
    """Raised when health checks during startup fail."""


@dataclass(frozen=True)
class EngineOptions:
    dsn: str
    backend: DatabaseBackend
    read_only: bool
    pool_size: int | None
    max_overflow: int | None
    pool_timeout: float | None
    connect_timeout: float | None
    statement_timeout_ms: int | None
    sqlite_timeout: float | None


def _mask_dsn(dsn: str) -> str:
    try:
        url = make_url(dsn)
    except Exception:
        return "***"
    password = url.password
    if password:
        url = url.set(password="***")
    if url.username:
        url = url.set(username="***")
    return str(url)


def mask_dsn(dsn: str) -> str:
    """Public helper to safely mask database connection strings."""

    return _mask_dsn(dsn)


class DBRouter:
    """Manage async engines and sessions for primary and replica databases."""

    def __init__(
        self,
        *,
        dsn: str,
        read_only_dsn: str | None = None,
        replica_dsn: str | None = None,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_timeout: float | None = None,
        connect_timeout: float | None = None,
        statement_timeout_ms: int | None = None,
        sqlite_timeout: float = _DEFAULT_SQLITE_TIMEOUT,
        echo: bool = False,
    ) -> None:
        self._writer_options = self._build_engine_options(
            dsn=dsn,
            read_only=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            connect_timeout=connect_timeout,
            statement_timeout_ms=statement_timeout_ms,
            sqlite_timeout=sqlite_timeout,
        )
        reader_dsn = read_only_dsn or replica_dsn or dsn
        self._reader_options = self._build_engine_options(
            dsn=reader_dsn,
            read_only=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            connect_timeout=connect_timeout,
            statement_timeout_ms=statement_timeout_ms,
            sqlite_timeout=sqlite_timeout,
        )
        self._echo = echo

        self._writer_engine = self._create_engine(self._writer_options, echo=echo)
        if reader_dsn == dsn:
            self._reader_engine = self._writer_engine
        else:
            self._reader_engine = self._create_engine(self._reader_options, echo=echo)

        self._writer_sessionmaker = async_sessionmaker(
            self._writer_engine, expire_on_commit=False, autoflush=False
        )
        self._reader_sessionmaker = async_sessionmaker(
            self._reader_engine, expire_on_commit=False, autoflush=False
        )

    @staticmethod
    def _build_engine_options(
        *,
        dsn: str,
        read_only: bool,
        pool_size: int | None,
        max_overflow: int | None,
        pool_timeout: float | None,
        connect_timeout: float | None,
        statement_timeout_ms: int | None,
        sqlite_timeout: float,
    ) -> EngineOptions:
        url = _normalize_url(dsn)
        backend = _detect_backend(url)
        pool_size = pool_size or _DEFAULT_POOL_SIZE
        max_overflow = max_overflow or _DEFAULT_MAX_OVERFLOW
        pool_timeout = pool_timeout or _DEFAULT_POOL_TIMEOUT
        connect_timeout = connect_timeout or _DEFAULT_CONNECT_TIMEOUT
        statement_timeout_ms = statement_timeout_ms or _DEFAULT_STATEMENT_TIMEOUT_MS
        sqlite_timeout_value: float | None = sqlite_timeout

        if backend is DatabaseBackend.SQLITE:
            pool_size = None
            max_overflow = None
            pool_timeout = None
            connect_timeout = None
            statement_timeout_ms = None
        else:
            sqlite_timeout_value = None

        return EngineOptions(
            dsn=str(url),
            backend=backend,
            read_only=read_only,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            connect_timeout=connect_timeout,
            statement_timeout_ms=statement_timeout_ms,
            sqlite_timeout=sqlite_timeout_value,
        )

    @staticmethod
    def _create_engine(options: EngineOptions, *, echo: bool) -> AsyncEngine:
        connect_args: dict[str, object] = {}
        engine_kwargs: dict[str, object] = {"echo": echo}

        if options.backend is DatabaseBackend.SQLITE:
            connect_args["timeout"] = options.sqlite_timeout or _DEFAULT_SQLITE_TIMEOUT
            engine_kwargs["poolclass"] = NullPool
        else:
            if options.connect_timeout is not None:
                connect_args["timeout"] = options.connect_timeout
            if options.statement_timeout_ms is not None:
                connect_args["command_timeout"] = options.statement_timeout_ms / 1000
                connect_args["server_settings"] = {
                    "statement_timeout": str(options.statement_timeout_ms)
                }
            engine_kwargs.update(
                {
                    "pool_pre_ping": True,
                    "pool_size": options.pool_size,
                    "max_overflow": options.max_overflow,
                    "pool_timeout": options.pool_timeout,
                }
            )
        return create_async_engine(options.dsn, connect_args=connect_args, **engine_kwargs)

    @property
    def backend(self) -> DatabaseBackend:
        return self._writer_options.backend

    @property
    def writer_options(self) -> EngineOptions:
        return self._writer_options

    @property
    def reader_options(self) -> EngineOptions:
        return self._reader_options

    async def startup(self) -> None:
        try:
            await self._check_engine(self._writer_engine, options=self._writer_options)
            if self._reader_engine is not self._writer_engine:
                await self._check_engine(self._reader_engine, options=self._reader_options)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive logging
            masked = _mask_dsn(self._writer_options.dsn)
            logger.error("Database startup failed for %s: %s", masked, exc, exc_info=True)
            raise DatabaseStartupError("Database engine startup failed") from exc

    async def shutdown(self) -> None:
        await self._writer_engine.dispose()
        if self._reader_engine is not self._writer_engine:
            await self._reader_engine.dispose()

    @asynccontextmanager
    async def session(self, *, read_only: bool = False) -> AsyncIterator[AsyncSession]:
        maker = self._reader_sessionmaker if read_only else self._writer_sessionmaker
        session = maker()
        try:
            if (
                read_only
                and self.backend is DatabaseBackend.POSTGRESQL
                and self._reader_engine is self._writer_engine
            ):
                await session.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"))
            yield session
        finally:
            if (
                read_only
                and self.backend is DatabaseBackend.POSTGRESQL
                and self._reader_engine is self._writer_engine
            ):
                await session.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE"))
            if session.in_transaction():
                await session.rollback()
            await session.close()

    async def _check_engine(self, engine: AsyncEngine, *, options: EngineOptions) -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.debug("Database connection healthy for %s", _mask_dsn(options.dsn))


def _normalize_url(dsn: str) -> URL:
    try:
        url = make_url(dsn)
    except Exception as exc:  # pragma: no cover - validated via tests
        raise DatabaseConfigurationError(f"Invalid database DSN: {dsn}") from exc

    driver = url.drivername
    if driver.startswith("sqlite"):
        if driver != "sqlite+aiosqlite":
            url = url.set(drivername="sqlite+aiosqlite")
    elif driver.startswith("postgresql"):
        if driver != "postgresql+asyncpg":
            url = url.set(drivername="postgresql+asyncpg")
    else:
        raise DatabaseConfigurationError(f"Unsupported driver in DSN: {driver}")
    return url


def _detect_backend(url: URL) -> DatabaseBackend:
    if url.drivername.startswith("sqlite"):
        return DatabaseBackend.SQLITE
    if url.drivername.startswith("postgresql"):
        return DatabaseBackend.POSTGRESQL
    raise DatabaseConfigurationError(f"Unsupported driver in DSN: {url.drivername}")


def get_db_router(settings: Settings | None = None) -> DBRouter:
    config = settings or get_settings()
    read_only_dsn = getattr(config, "DATABASE_URL_RO", None)
    replica_dsn = getattr(config, "DATABASE_URL_R", None)
    return DBRouter(
        dsn=config.DATABASE_URL,
        read_only_dsn=read_only_dsn,
        replica_dsn=replica_dsn,
        pool_size=getattr(config, "DATABASE_POOL_SIZE", _DEFAULT_POOL_SIZE),
        max_overflow=getattr(config, "DATABASE_MAX_OVERFLOW", _DEFAULT_MAX_OVERFLOW),
        pool_timeout=getattr(config, "DATABASE_POOL_TIMEOUT", _DEFAULT_POOL_TIMEOUT),
        connect_timeout=getattr(config, "DATABASE_CONNECT_TIMEOUT", _DEFAULT_CONNECT_TIMEOUT),
        statement_timeout_ms=getattr(
            config, "DATABASE_STATEMENT_TIMEOUT_MS", _DEFAULT_STATEMENT_TIMEOUT_MS
        ),
        sqlite_timeout=getattr(config, "DATABASE_SQLITE_TIMEOUT", _DEFAULT_SQLITE_TIMEOUT),
        echo=getattr(config, "DATABASE_ECHO", False),
    )


__all__ = [
    "DBRouter",
    "DatabaseBackend",
    "DatabaseConfigurationError",
    "DatabaseStartupError",
    "EngineOptions",
    "get_db_router",
    "mask_dsn",
]
