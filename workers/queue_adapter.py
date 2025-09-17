"""
@file: workers/queue_adapter.py
@description: Protocol and helpers for prediction queue status reporting.
@dependencies: enum, typing
@created: 2025-09-20
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Protocol


class TaskStatus(str, Enum):
    """Standardised task status compatible with RQ semantics."""

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"


class QueueAdapterError(RuntimeError):
    """Raised when queue adapter encounters unrecoverable state."""


class QueueError(QueueAdapterError):
    """Alias maintained for backwards compatibility with legacy naming."""


_RQ_STATUS_ALIASES: dict[str, TaskStatus] = {
    TaskStatus.QUEUED.value: TaskStatus.QUEUED,
    "scheduled": TaskStatus.QUEUED,
    "deferred": TaskStatus.QUEUED,
    TaskStatus.STARTED.value: TaskStatus.STARTED,
    "running": TaskStatus.STARTED,
    TaskStatus.FINISHED.value: TaskStatus.FINISHED,
    "completed": TaskStatus.FINISHED,
    TaskStatus.FAILED.value: TaskStatus.FAILED,
    "stopped": TaskStatus.FAILED,
    "canceled": TaskStatus.FAILED,
}


def map_rq_status(status: str | None) -> TaskStatus:
    """Normalise raw RQ status strings to :class:`TaskStatus` values."""

    if status is None:
        return TaskStatus.QUEUED
    key = status.lower().strip()
    try:
        return _RQ_STATUS_ALIASES[key]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise QueueAdapterError(f"Unknown queue status: {status}") from exc


def safe_queue_error(action: str, job_id: str, error: Exception | str) -> QueueError:
    """Create a :class:`QueueError` with a sanitised message."""

    message = f"Queue operation '{action}' failed for job '{job_id}'"
    err_text = str(error)
    if err_text:
        message = f"{message}: {err_text.splitlines()[0]}"
    return QueueError(message)


class IQueueAdapter(Protocol):
    """Protocol describing queue adapter interactions used by the worker."""

    async def mark_started(self, job_id: str, *, meta: dict[str, Any] | None = None) -> None:
        """Mark job as started and optionally persist metadata."""

    async def mark_finished(self, job_id: str, payload: dict[str, Any]) -> None:
        """Persist successful result and final status."""

    async def mark_failed(
        self,
        job_id: str,
        reason: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Persist failure status with structured details."""
