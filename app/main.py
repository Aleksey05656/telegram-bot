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
