"""
@file: scripts/migrations.py
@description: Lazy Alembic runner with strict/lenient modes for deployment roles.
@dependencies: alembic, config.get_settings, database.db_router.mask_dsn, logger
@created: 2025-11-05
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

from config import Settings, get_settings
from database.db_router import mask_dsn
from logger import logger


class AlembicUnavailableError(RuntimeError):
    """Raised when Alembic modules cannot be imported."""


def _load_alembic() -> tuple[ModuleType, type[Any]]:
    try:
        command_module = importlib.import_module("alembic.command")
        config_module = importlib.import_module("alembic.config")
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise AlembicUnavailableError("Alembic package is not installed") from exc

    config_type = getattr(config_module, "Config", None)
    if config_type is None:  # pragma: no cover - defensive
        raise AlembicUnavailableError("alembic.config.Config is unavailable")

    return command_module, config_type


def _make_config(settings: Settings, config_type: type[Any]) -> Any:
    config = config_type()
    config.set_main_option("script_location", "database/migrations")
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return config


def run_migrations(*, strict: bool = False) -> int:
    """Run Alembic upgrade to head with optional strict mode."""

    settings = get_settings()
    masked_dsn = mask_dsn(settings.DATABASE_URL)
    bound_logger = logger.bind(event="scripts.migrations", strict=strict, dsn=masked_dsn)

    try:
        command_module, config_type = _load_alembic()
    except AlembicUnavailableError as exc:
        if strict:
            bound_logger.bind(error=str(exc)).error(
                "Alembic is required for strict migrations; aborting"
            )
            return 1
        bound_logger.bind(error=str(exc)).warning("Alembic not available; skipping migrations")
        return 0

    config = _make_config(settings, config_type)
    bound_logger.info("Running Alembic upgrade to head")

    try:
        command_module.upgrade(config, "head")
    except Exception as exc:  # pragma: no cover - defensive logging
        bound_logger.bind(error=str(exc)).error("Alembic upgrade failed")
        return 1

    bound_logger.info("Alembic upgrade finished")
    return 0


def main() -> int:
    return run_migrations(strict=False)


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
