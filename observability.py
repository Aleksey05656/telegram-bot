"""
@file: observability.py
@description: Initialize Sentry and Prometheus metrics server.
@dependencies: config.py, sentry_sdk, prometheus_client
@created: 2025-08-24
"""

import sentry_sdk
from prometheus_client import start_http_server

from config import settings
from logger import logger

_prometheus_started = False


def init_observability() -> None:
    """Initialize Sentry and start Prometheus HTTP server."""
    global _prometheus_started

    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)
        logger.info("Sentry initialized")

    if not _prometheus_started:
        start_http_server(settings.PROMETHEUS_PORT)
        _prometheus_started = True
        logger.info(
            "Prometheus metrics server started on port %d", settings.PROMETHEUS_PORT
        )
