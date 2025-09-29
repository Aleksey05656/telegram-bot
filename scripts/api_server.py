"""
@file: scripts/api_server.py
@description: Dedicated API server bootstrap for Amvera with uvicorn lifecycle management.
@dependencies: scripts.role_dispatch, app.main, uvicorn
@created: 2025-11-08
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn


def _resolve_log_level(raw: str | None) -> int:
    if not raw:
        return logging.INFO
    if raw.isdigit():
        try:
            return max(0, min(50, int(raw)))
        except ValueError:
            return logging.INFO
    level = logging.getLevelName(raw.upper())
    return level if isinstance(level, int) else logging.INFO


def _configure_logging() -> logging.Logger:
    level = _resolve_log_level(os.getenv("LOG_LEVEL", "INFO"))
    logging.basicConfig(
        level=level,
        force=True,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logger = logging.getLogger("boot")
    logger.setLevel(level)
    return logger


def _ensure_api_flag(logger: logging.Logger) -> str:
    api_enabled = os.environ.setdefault("API_ENABLED", "true")
    if api_enabled.lower() != "true":
        logger.warning("Overriding API_ENABLED=%s to true for Amvera", api_enabled)
        api_enabled = "true"
        os.environ["API_ENABLED"] = api_enabled
    return api_enabled


def _resolve_port(logger: logging.Logger) -> int:
    raw_port = os.getenv("PORT", "80").strip()
    try:
        port = int(raw_port)
    except ValueError:
        logger.warning("Invalid PORT=%s, falling back to 80", raw_port)
        port = 80
    if port <= 0:
        logger.warning("Non-positive PORT=%s, resetting to 80", raw_port)
        port = 80
    return port


def main(argv: list[str] | None = None) -> None:  # noqa: D401 - CLI entrypoint
    _ = argv  # CLI compatibility, currently unused
    logger = _configure_logging()
    api_enabled = _ensure_api_flag(logger)
    port = _resolve_port(logger)

    logger.info(
        "boot: role=%s api=%s port=%s", os.getenv("ROLE", "api"), api_enabled, port
    )

    try:
        uvicorn.run(
            "app.api:app",
            host="0.0.0.0",
            port=port,
            workers=1,
            log_level=logging.getLevelName(logger.getEffectiveLevel()).lower(),
        )
    except Exception:  # pragma: no cover - defensive logging for prod incidents
        logger.exception("uvicorn server crashed")
        raise


if __name__ == "__main__":
    main(sys.argv[1:])
