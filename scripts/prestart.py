"""
@file: scripts/prestart.py
@description: Prestart routine for running migrations and service health checks.
@dependencies: alembic, database.db_router, workers.redis_factory
@created: 2025-09-21
"""

from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from config import Settings, get_settings
from database.db_router import DBRouter, get_db_router, mask_dsn
from logger import logger
from workers.redis_factory import RedisFactory


def _configure_alembic(settings: Settings) -> Config:
    config = Config()
    config.set_main_option("script_location", "database/migrations")
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return config


def run_migrations(settings: Settings) -> None:
    masked_dsn = mask_dsn(settings.DATABASE_URL)
    bound_logger = logger.bind(event="prestart.migrations", dsn=masked_dsn)
    bound_logger.info("Running Alembic upgrade to head")
    try:
        command.upgrade(_configure_alembic(settings), "head")
    except Exception as exc:  # pragma: no cover - defensive logging
        bound_logger.bind(error=str(exc)).error("Alembic upgrade failed")
        raise
    else:
        bound_logger.info("Alembic upgrade finished")


async def _probe_session(router: DBRouter, *, read_only: bool) -> None:
    options = router.reader_options if read_only else router.writer_options
    target = "reader" if read_only else "writer"
    masked_dsn = mask_dsn(options.dsn)
    probe_logger = logger.bind(event="prestart.healthcheck.db", target=target, dsn=masked_dsn)
    probe_logger.info("Checking database connectivity")
    try:
        async with router.session(read_only=read_only) as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive logging
        probe_logger.bind(error=str(exc)).error("Database connectivity check failed")
        raise
    else:
        probe_logger.info("Database connection healthy")


async def check_database(settings: Settings) -> None:
    router = get_db_router(settings)
    try:
        await _probe_session(router, read_only=False)
        if (
            settings.DATABASE_URL_RO
            or settings.DATABASE_URL_R
            or router.reader_options.dsn != router.writer_options.dsn
        ):
            await _probe_session(router, read_only=True)
    finally:
        await router.shutdown()


async def check_redis(settings: Settings) -> None:
    factory = RedisFactory(url=settings.REDIS_URL)
    try:
        await factory.health_check()
    finally:
        await factory.close()


async def run_health_checks(settings: Settings) -> None:
    await check_database(settings)
    await check_redis(settings)


async def _async_main() -> None:
    settings = get_settings()
    run_migrations(settings)
    await run_health_checks(settings)


def main() -> None:
    try:
        asyncio.run(_async_main())
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.bind(event="prestart.failure", error=str(exc)).error("Prestart routine failed")
        raise


if __name__ == "__main__":
    main()
