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
