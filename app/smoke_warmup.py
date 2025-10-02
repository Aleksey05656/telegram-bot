"""
@file: smoke_warmup.py
@description: Smoke warmup router for QA/offline readiness
@dependencies: fastapi, database.cache_postgres (optional), ml.models.poisson_regression_model (optional)
"""

from __future__ import annotations

import inspect
import os
import time
from typing import Any, Callable

from .fastapi_compat import APIRouter, JSONResponse

try:  # pragma: no cover - optional dependency guard
    import redis.asyncio as redis
except Exception:  # pragma: no cover - offline fallback
    redis = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    from database.cache_postgres import init_cache
except Exception:  # pragma: no cover - offline fallback
    init_cache = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    from ml.models.poisson_regression_model import poisson_regression_model
except Exception:  # pragma: no cover - offline fallback
    poisson_regression_model = None  # type: ignore[assignment]

router = APIRouter()


async def _maybe_warm_redis(warmed: list[str]) -> None:
    if redis is None:
        return

    try:
        from app.config import get_settings  # local import to avoid circular dependency
    except Exception:
        return

    try:
        redis_url = get_settings().get_redis_url()
    except Exception:
        return

    if not redis_url:
        return

    client: Any | None = None
    try:
        client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        ping_result = client.ping()
        if inspect.isawaitable(ping_result):
            ping_result = await ping_result
        if ping_result:
            warmed.append("redis")
    except Exception:
        pass
    finally:
        if client is None:
            return
        close_method = getattr(client, "close", None)
        if callable(close_method):
            try:
                close_result = close_method()
                if inspect.isawaitable(close_result):
                    await close_result
            except Exception:
                pass


@router.get("/__smoke__/warmup", tags=["smoke"])
@router.get("/smoke/warmup", tags=["smoke"])
async def warmup() -> JSONResponse:
    """Best-effort warmup for lightweight dependencies."""

    started = time.monotonic()
    warmed: list[str] = []

    await _maybe_warm_redis(warmed)

    if init_cache is not None:
        try:
            await init_cache()
        except Exception:
            pass
        else:
            warmed.append("cache")

    if poisson_regression_model is not None:
        try:
            poisson_regression_model.load_ratings()
        except Exception:
            pass
        else:
            warmed.append("poisson_ratings")

    try:
        from app.ml.model_registry import LocalModelRegistry

        registry = LocalModelRegistry(os.getenv("MODEL_REGISTRY_PATH", "/data/artifacts"))
        registry.peek()
    except Exception:
        pass
    else:
        warmed.append("model_registry")

    took_ms = int((time.monotonic() - started) * 1000)
    return JSONResponse({"warmed": warmed, "took_ms": took_ms}, status_code=200)
