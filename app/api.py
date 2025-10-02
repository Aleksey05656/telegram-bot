"""
@file: app/api.py
@description: Unified ASGI application with health/readiness probes and metrics
@dependencies: app.main, fastapi, asyncpg, redis.asyncio, prometheus_client
@created: 2025-10-27
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import Any

logging.basicConfig(
    level=logging.getLevelName(os.getenv("LOG_LEVEL", "INFO").upper()),
    force=True,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


from .fastapi_compat import FastAPI, HTTPException, JSONResponse, Response, status

from .config import get_settings
from .main import app as _main_app
from .runtime_state import STATE

try:  # pragma: no cover - optional dependency guard
    import asyncpg
except Exception:  # pragma: no cover - handled in readiness probe
    asyncpg = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    import redis.asyncio as redis
except Exception:  # pragma: no cover - handled in readiness probe
    redis = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except Exception:  # pragma: no cover - metrics will be disabled
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

    def generate_latest(*_args: Any, **_kwargs: Any) -> bytes:  # type: ignore[override]
        raise RuntimeError("prometheus_client is not installed")


logger = logging.getLogger(__name__)
logger.info(
    "boot: role=%s api_enabled=%s port=%s",
    os.getenv("ROLE", "api"),
    os.getenv("API_ENABLED", "false"),
    os.getenv("PORT", "80"),
)
READINESS_TIMEOUT = float(os.getenv("READINESS_TIMEOUT_SEC", "1.5"))

# Reuse FastAPI app from app.main to keep routers/middleware intact.
app: FastAPI = _main_app


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "off", "no"}


def _is_canary(settings_obj: Any | None = None) -> bool:
    if settings_obj is None:
        settings_obj = get_settings()
    return bool(getattr(settings_obj, "canary", False))


async def _check_postgres(dsn: str, timeout: float) -> tuple[str, str | None]:
    """Run a lightweight PostgreSQL probe (SELECT 1)."""

    if not dsn:
        if _is_truthy(os.getenv("FAILSAFE_MODE")) or _is_truthy(os.getenv("USE_OFFLINE_STUBS")):
            return "skipped", "database DSN is not configured"
        return "fail", "database DSN is not configured"
    if asyncpg is None:  # pragma: no cover - dependency missing scenario
        if _is_truthy(os.getenv("FAILSAFE_MODE")) or _is_truthy(os.getenv("USE_OFFLINE_STUBS")):
            return "skipped", "asyncpg module is unavailable"
        return "fail", "asyncpg module is unavailable"

    conn: Any | None = None
    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=timeout)
        await asyncio.wait_for(conn.execute("SELECT 1"), timeout=timeout)
    except Exception as exc:  # pragma: no cover - network/connectivity issues
        detail = f"{type(exc).__name__}: {exc}"
        logger.warning("PostgreSQL readiness probe failed: %s", detail)
        if _is_truthy(os.getenv("FAILSAFE_MODE")):
            return "degraded", detail
        return "fail", detail
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                await conn.close()
    return "ok", None


async def _check_redis(url: str, timeout: float) -> tuple[str, str | None]:
    """Ping Redis if URL configured; otherwise mark as skipped."""

    if not url:
        return "skipped", "redis url not configured"
    if redis is None:  # pragma: no cover - dependency missing scenario
        if _is_truthy(os.getenv("FAILSAFE_MODE")) or _is_truthy(os.getenv("USE_OFFLINE_STUBS")):
            return "skipped", "redis.asyncio module is unavailable"
        return "degraded", "redis.asyncio module is unavailable"

    client = redis.from_url(url, encoding="utf-8", decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=timeout)
    except Exception as exc:  # pragma: no cover - network/connectivity issues
        detail = f"{type(exc).__name__}: {exc}"
        logger.warning("Redis readiness probe failed: %s", detail)
        if _is_truthy(os.getenv("FAILSAFE_MODE")):
            return "skipped", detail
        return "degraded", detail
    finally:
        with contextlib.suppress(Exception):
            await client.close()
    return "ok", None


def _check_runtime_flags() -> tuple[str, str | None]:
    """Check optional runtime components (polling, scheduler)."""

    required_components: dict[str, bool] = {}
    if _is_truthy(os.getenv("ENABLE_POLLING", "1")):
        required_components["polling"] = STATE.polling_ready
    if _is_truthy(os.getenv("ENABLE_SCHEDULER", "1")) and not _is_truthy(
        os.getenv("FAILSAFE_MODE")
    ):
        required_components["scheduler"] = STATE.scheduler_ready

    if not required_components:
        return "skipped", "no runtime components to verify"

    missing = [name for name, ready in required_components.items() if not ready]
    if missing:
        return "degraded", f"not ready: {', '.join(sorted(missing))}"
    return "ok", None


@app.get("/healthz", tags=["system"])
@app.get("/health", include_in_schema=False)
async def healthz() -> dict[str, Any]:
    """Lightweight liveness probe."""

    payload: dict[str, Any] = {"status": "ok"}
    if _is_canary():
        payload["canary"] = True
    return payload


@app.get("/readyz", tags=["system"])
@app.get("/ready", include_in_schema=False)
async def readyz() -> JSONResponse:
    """Readiness probe covering database, Redis and runtime components."""

    settings = get_settings()
    postgres_status, postgres_detail = await _check_postgres(
        settings.get_database_url("rw"), READINESS_TIMEOUT
    )
    redis_status, redis_detail = await _check_redis(
        settings.get_redis_url(), READINESS_TIMEOUT
    )
    runtime_status, runtime_detail = _check_runtime_flags()

    checks = {
        "postgres": {"status": postgres_status, "detail": postgres_detail},
        "redis": {"status": redis_status, "detail": redis_detail},
    }
    if runtime_status != "skipped":
        checks["runtime"] = {"status": runtime_status, "detail": runtime_detail}

    overall = "ok"
    if postgres_status == "fail":
        overall = "fail"
    elif any(result["status"] == "degraded" for result in checks.values()):
        overall = "degraded"

    status_code = status.HTTP_200_OK
    if overall == "fail":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    payload: dict[str, Any] = {
        "status": overall,
        "checks": {
            name: {k: v for k, v in data.items() if v is not None}
            for name, data in checks.items()
        },
    }
    if _is_canary(settings):
        payload["canary"] = True
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/metrics", tags=["system"])
async def metrics() -> Response:
    """Expose Prometheus metrics when ENABLE_METRICS=1."""

    settings = get_settings()
    if not settings.enable_metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="metrics disabled")

    try:
        payload = generate_latest()  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - metrics disabled scenario
        logger.warning("Prometheus client is unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="prometheus client is unavailable",
        ) from exc

    response = Response(content=payload, media_type=CONTENT_TYPE_LATEST)
    response.headers["Cache-Control"] = "no-cache"
    return response


__all__ = ["app", "healthz", "readyz", "metrics"]
