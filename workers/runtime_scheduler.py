"""
@file: workers/runtime_scheduler.py
@description: Minimal in-memory runtime scheduler adapter for wiring and smoke checks.
@dependencies: workers.retrain_scheduler
@created: 2025-09-12
"""

from __future__ import annotations
from typing import Callable, Any, Dict, List

_SCHEDULED: List[Dict[str, Any]] = []

def register(cron_expr: str, fn: Callable[[], None]) -> None:
    """Append a job into in-memory registry (no real scheduling)."""
    _SCHEDULED.append({"cron": cron_expr, "fn": fn})


def list_jobs() -> List[Dict[str, Any]]:
    """Return a shallow copy of registered jobs with callable flag only."""
    out: List[Dict[str, Any]] = []
    for j in _SCHEDULED:
        out.append({"cron": j.get("cron"), "callable": callable(j.get("fn"))})
    return out


def clear_jobs() -> None:
    """Clear all registered jobs (useful for tests)."""
    _SCHEDULED.clear()
