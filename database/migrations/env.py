"""
@file: env.py
@description: Alembic environment configuration with async engine support.
@dependencies: alembic, sqlalchemy, config
@created: 2025-09-17
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

_DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./local.db"


def _resolve_database_url() -> str:
    settings = get_settings()
    dsn = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    if not dsn:
        return _DEFAULT_SQLITE_URL
    url = make_url(dsn)
    if url.drivername == "sqlite":
        url = url.set(drivername="sqlite+aiosqlite")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")
    return str(url)


def run_migrations_offline() -> None:
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations(connectable: AsyncEngine) -> None:
    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
    await connectable.dispose()


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_database_url()
    url_obj = make_url(url)
    connectable: AsyncEngine
    if url_obj.drivername.startswith("sqlite"):
        connectable = create_async_engine(url, poolclass=pool.NullPool)
    else:
        connectable = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
            pool_timeout=float(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
        )

    asyncio.run(_run_async_migrations(connectable))


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
