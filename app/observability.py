"""
@file: observability.py
@description: Sentry and Prometheus integration
@dependencies: config, fastapi
@created: 2025-09-09
"""

import sentry_sdk

from .fastapi_compat import FastAPI, PlainTextResponse
from prometheus_client import Counter, Gauge, generate_latest

from .config import Settings

REQUESTS_TOTAL = Counter("requests_total", "Total requests", ["service", "env", "version"])
BUILD_INFO = Gauge("build_info", "Build info", ["service", "env", "version"])


def init_observability(app: FastAPI, settings: Settings):
    labels = {
        "service": settings.app_name,
        "env": getattr(settings, "deployment_env", settings.env),
        "version": settings.git_sha,
    }

    BUILD_INFO.labels(**labels).set(1)

    if settings.sentry.enabled and settings.sentry.dsn:
        sentry_sdk.init(dsn=settings.sentry.dsn, environment=settings.sentry.environment)

    @app.middleware("http")
    async def _count_requests(request, call_next):
        resp = await call_next(request)
        REQUESTS_TOTAL.labels(**labels).inc()
        return resp

    if settings.prometheus.enabled:

        @app.get(settings.prometheus.endpoint)
        def metrics() -> PlainTextResponse:
            return PlainTextResponse(generate_latest(), media_type="text/plain; version=0.0.4")
