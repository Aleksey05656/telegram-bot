"""
@file: workers/runtime_scheduler.py
@description: Minimal in-memory runtime scheduler adapter for wiring and smoke checks.
@dependencies: workers.retrain_scheduler
@created: 2025-09-12
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
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
_DATA_ROOT = Path(os.getenv("DATA_ROOT", "/data"))
_STATE_ENV = os.getenv("RUNTIME_SCHEDULER_STATE")
if _STATE_ENV:
    candidate = Path(_STATE_ENV)
    if not candidate.is_absolute():
        candidate = _DATA_ROOT / candidate
    _STATE_FILE = candidate
else:
    _STATE_FILE = _DATA_ROOT / "artifacts/runtime_scheduler_state.json"


def _state_payload() -> dict[str, Any]:
    payload = {
        "jobs": [
            {"cron": job.get("cron"), "callable": bool(job.get("callable", False))}
            for job in _SCHEDULED
        ],
        "count": _JOBS_COUNTER.labels(**_LABELS)._value.get(),
    }
    return payload


def _persist_state() -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(
        json.dumps(_state_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _refresh_state() -> None:
    if not _STATE_FILE.exists():
        return
    try:
        raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    _SCHEDULED.clear()
    for job in raw.get("jobs", []):
        _SCHEDULED.append({"cron": job.get("cron"), "callable": bool(job.get("callable", False))})
    count = float(raw.get("count", 0.0))
    _JOBS_COUNTER.labels(**_LABELS)._value.set(count)


_refresh_state()


def register(cron_expr: str, fn: Callable[[], None]) -> None:
    """Append a job into in-memory registry (no real scheduling)."""
    _refresh_state()
    _SCHEDULED.append({"cron": cron_expr, "callable": callable(fn)})
    _JOBS_COUNTER.labels(**_LABELS).inc()
    _persist_state()


def list_jobs() -> list[dict[str, Any]]:
    """Return a shallow copy of registered jobs with callable flag only."""
    _refresh_state()
    out: list[dict[str, Any]] = []
    for j in _SCHEDULED:
        out.append({"cron": j.get("cron"), "callable": bool(j.get("callable", False))})
    return out


def jobs_registered_total() -> float:
    """Return total registered jobs counter."""
    _refresh_state()
    return _JOBS_COUNTER.labels(**_LABELS)._value.get()


def clear_jobs() -> None:
    """Clear all registered jobs (useful for tests)."""
    _refresh_state()
    _SCHEDULED.clear()
    _JOBS_COUNTER.labels(**_LABELS)._value.set(0.0)
    _persist_state()
