"""
@file: observability.py
@description: Sentry and Prometheus integration
@dependencies: config, fastapi
@created: 2025-09-09
"""

import sentry_sdk
from fastapi import FastAPI, Response
from prometheus_client import Counter, generate_latest

from .config import Settings

REQUESTS_TOTAL = Counter("requests_total", "Total requests")


def init_observability(app: FastAPI, settings: Settings):
    if settings.sentry.dsn:
        sentry_sdk.init(dsn=settings.sentry.dsn, environment=settings.sentry.environment)

    @app.middleware("http")
    async def _count_requests(request, call_next):
        resp = await call_next(request)
        REQUESTS_TOTAL.inc()
        return resp

    if settings.prometheus.enabled:

        @app.get(settings.prometheus.endpoint)
        def metrics() -> Response:
            return Response(generate_latest(), media_type="text/plain")
