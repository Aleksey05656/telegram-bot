"""
@file: main.py
@description: FastAPI application entrypoint
@dependencies: observability, config, middlewares
@created: 2025-09-09
"""

import os

from fastapi import FastAPI

from workers.retrain_scheduler import schedule_retrain  # type: ignore
from workers.runtime_scheduler import jobs_registered_total as _rt_jobs_total  # type: ignore
from workers.runtime_scheduler import list_jobs as _rt_list_jobs
from workers.runtime_scheduler import register as _rt_register

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


# --- Retrain wiring (feature-flagged by RETRAIN_CRON) ---
_retrain_enabled = False
_effective_cron = None
_cron_env = os.getenv("RETRAIN_CRON", "").strip()
if _cron_env and _cron_env.lower() not in {"off", "disabled", "none", "false"}:
    try:
        _effective_cron = schedule_retrain(_rt_register, cron_expr=_cron_env or None)
        _retrain_enabled = True
    except Exception:
        # fail-safe: do not break app init due to scheduler issues
        _retrain_enabled = False
        _effective_cron = None


@app.get("/__smoke__/retrain")
def retrain_smoke():
    """Report retrain registration status and configured crons."""
    jobs = _rt_list_jobs()
    return {
        "enabled": _retrain_enabled,
        "count": len(jobs),
        "crons": [j["cron"] for j in jobs],
        "effective_cron": _effective_cron,
        "jobs_registered_total": _rt_jobs_total(),
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
