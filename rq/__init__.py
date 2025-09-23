"""
/**
 * @file: rq/__init__.py
 * @description: Minimal RQ queue stubs for offline tests.
 * @dependencies: rq.job
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from typing import Any, Callable, List

from .job import Job

__all__ = ["Queue", "Job"]


class Queue:
    """Simplified queue that records enqueued jobs."""

    def __init__(self, name: str, *, connection: Any, default_timeout: int | str | None = None) -> None:
        self.name = name
        self.connection = connection
        self.default_timeout = default_timeout
        self._jobs: List[Job] = []

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Job:
        job = Job(func=func, args=args, kwargs=kwargs)
        self._jobs.append(job)
        return job

    def __len__(self) -> int:
        return len(self._jobs)

