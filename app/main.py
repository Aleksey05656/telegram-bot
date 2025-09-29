"""
@file: main.py
@description: FastAPI application entrypoint
@dependencies: config, middlewares
@created: 2025-09-09
"""

import logging
import os
from typing import Any, Callable

from .fastapi_compat import FastAPI

from api.health import router as health_router
from .config import get_settings
from .middlewares import ProcessingTimeMiddleware, RateLimitMiddleware
from .smoke_warmup import router as smoke_router

logger = logging.getLogger(__name__)


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"", "0", "false", "off", "no", "disabled"}


METRICS_ENABLED = _flag("METRICS_ENABLED", default=False)
SCHEDULES_ENABLED = _flag("SCHEDULES_ENABLED", default=False)
EXTERNAL_CLIENTS_ENABLED = _flag("EXTERNAL_CLIENTS_ENABLED", default=False)
API_ENABLED = _flag("API_ENABLED", default=False)

app = FastAPI()
settings = get_settings()

def _include_router(router: Any, *, tags: list[str]) -> None:
    if hasattr(app, "include_router"):
        app.include_router(router, tags=tags)
        return
    for route in getattr(router, "routes", []):  # pragma: no cover - shim fallback
        path = route.get("path")
        endpoint = route.get("endpoint")
        methods = route.get("methods", ["GET"])
        route_tags = route.get("tags") or tags
        if not path or endpoint is None:
            continue
        for method in methods:
            registrar = getattr(app, method.lower(), None)
            if callable(registrar):
                handler = registrar(path)
                handler(endpoint)
                if hasattr(handler, "tags"):
                    handler.tags = route_tags  # type: ignore[attr-defined]


_include_router(smoke_router, tags=["smoke"])

if API_ENABLED:
    _include_router(health_router, tags=["system"])

if settings.rate_limit.enabled:
    app.add_middleware(
        RateLimitMiddleware,
        requests=settings.rate_limit.requests,
        per_seconds=settings.rate_limit.per_seconds,
    )
app.add_middleware(ProcessingTimeMiddleware)


@app.get("/", tags=["system"])
def index() -> dict[str, Any]:
    current = get_settings()
    payload: dict[str, Any] = {
        "service": current.app_name,
        "version": current.git_sha,
    }
    if getattr(current, "canary", False):
        payload["canary"] = True
    return payload


_rt_list_jobs: Callable[[], list[dict[str, Any]]] | None = None
_rt_jobs_total: Callable[[], int] | None = None
_retrain_enabled = False
_effective_cron: str | None = None


def _init_metrics() -> None:
    if not METRICS_ENABLED:
        return
    try:
        from .observability import init_observability

        init_observability(app, settings=settings)
    except Exception as exc:  # pragma: no cover - defensive guard for legacy envs
        logger.warning("Observability init skipped: %s", exc)


def _init_schedules() -> None:
    global _rt_list_jobs, _rt_jobs_total, _retrain_enabled, _effective_cron
    if not SCHEDULES_ENABLED:
        return
    try:
        from workers.retrain_scheduler import schedule_retrain  # type: ignore
        from workers.runtime_scheduler import (  # type: ignore
            jobs_registered_total as rt_jobs_total,
            list_jobs as rt_list_jobs,
            register as rt_register,
        )
    except Exception as exc:  # pragma: no cover - missing optional deps
        logger.warning("Scheduler wiring skipped: %s", exc)
        return

    _rt_list_jobs = rt_list_jobs
    _rt_jobs_total = rt_jobs_total

    cron_env = os.getenv("RETRAIN_CRON", "").strip()
    if not cron_env or cron_env.lower() in {"off", "disabled", "none", "false"}:
        return

    try:
        _effective_cron = schedule_retrain(rt_register, cron_expr=cron_env or None)
        _retrain_enabled = True
    except Exception as exc:  # pragma: no cover - scheduler failures should not crash app
        _retrain_enabled = False
        _effective_cron = None
        logger.warning("Retrain scheduler init failed: %s", exc)


def _init_external_clients() -> None:
    if not EXTERNAL_CLIENTS_ENABLED:
        return
    try:
        import sportmonks  # noqa: F401  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("External clients unavailable: %s", exc)


def main() -> None:
    _init_metrics()
    _init_schedules()
    _init_external_clients()


@app.get("/__smoke__/retrain")
def retrain_smoke():
    """Report retrain registration status and configured crons."""
    jobs: list[dict[str, Any]]
    if _rt_list_jobs is None:
        jobs = []
    else:
        try:
            jobs = list(_rt_list_jobs())
        except Exception as exc:  # pragma: no cover - runtime scheduler optional
            logger.warning("Failed to list retrain jobs: %s", exc)
            jobs = []
    total_jobs = 0
    if _rt_jobs_total is not None:
        try:
            total_jobs = int(_rt_jobs_total())
        except Exception as exc:  # pragma: no cover - optional metric
            logger.warning("Failed to fetch retrain job total: %s", exc)
            total_jobs = 0
    return {
        "enabled": _retrain_enabled,
        "count": len(jobs),
        "crons": [j["cron"] for j in jobs],
        "effective_cron": _effective_cron,
        "jobs_registered_total": total_jobs,
    }


@app.get("/__smoke__/sentry")
def sentry_smoke():
    # отправим тестовое событие, если настроен DSN
    import sentry_sdk

    from .config import get_settings

    s = get_settings()
    if s.sentry.dsn:
        sentry_sdk.capture_message("smoke-test")
        return {"sent": True}
    return {"sent": False, "reason": "dsn not configured"}


main()
