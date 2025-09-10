"""
@file: main.py
@description: FastAPI application entrypoint
@dependencies: observability, config, middlewares
@created: 2025-09-09
"""

from fastapi import FastAPI

from .config import get_settings
from .middlewares import ProcessingTimeMiddleware, RateLimitMiddleware
from .observability import init_observability

app = FastAPI()
settings = get_settings()
init_observability(app, settings=settings)

if settings.rate_limit.enabled:
    app.add_middleware(
        RateLimitMiddleware,
        requests=settings.rate_limit.requests,
        per_seconds=settings.rate_limit.per_seconds,
    )
app.add_middleware(ProcessingTimeMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/__smoke__/sentry")
def sentry_smoke():
    # отправим тестовое событие, если настроен DSN
    from .config import get_settings
    import sentry_sdk

    s = get_settings()
    if s.sentry.dsn:
        sentry_sdk.capture_message("smoke-test")
        return {"sent": True}
    return {"sent": False, "reason": "dsn not configured"}
