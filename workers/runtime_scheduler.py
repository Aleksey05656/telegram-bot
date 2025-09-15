"""
@file: workers/runtime_scheduler.py
@description: Minimal in-memory runtime scheduler adapter for wiring and smoke checks.
@dependencies: workers.retrain_scheduler
@created: 2025-09-12
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prometheus_client import Counter

from app.config import get_settings

_s = get_settings()
_LABELS = {"service": _s.app_name, "env": _s.env, "version": _s.git_sha}

_SCHEDULED: list[dict[str, Any]] = []
_JOBS_COUNTER = Counter(
    "jobs_registered_total",
    "Total jobs registered",
    ["service", "env", "version"],
)


def register(cron_expr: str, fn: Callable[[], None]) -> None:
    """Append a job into in-memory registry (no real scheduling)."""
    _SCHEDULED.append({"cron": cron_expr, "fn": fn})
    _JOBS_COUNTER.labels(**_LABELS).inc()


def list_jobs() -> list[dict[str, Any]]:
    """Return a shallow copy of registered jobs with callable flag only."""
    out: list[dict[str, Any]] = []
    for j in _SCHEDULED:
        out.append({"cron": j.get("cron"), "callable": callable(j.get("fn"))})
    return out


def jobs_registered_total() -> float:
    """Return total registered jobs counter."""
    return _JOBS_COUNTER.labels(**_LABELS)._value.get()


def clear_jobs() -> None:
    """Clear all registered jobs (useful for tests)."""
    _SCHEDULED.clear()
