"""
@file: tests/workers/test_queue_adapter_errors.py
@description: Tests for queue adapter status mapping and safe error handling.
@dependencies: workers.queue_adapter
@created: 2025-09-23
"""

from __future__ import annotations

import pytest

from workers.queue_adapter import (
    QueueAdapterError,
    QueueError,
    TaskStatus,
    map_rq_status,
    safe_queue_error,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("queued", TaskStatus.QUEUED),
        ("scheduled", TaskStatus.QUEUED),
        ("deferred", TaskStatus.QUEUED),
        ("started", TaskStatus.STARTED),
        ("running", TaskStatus.STARTED),
        ("finished", TaskStatus.FINISHED),
        ("completed", TaskStatus.FINISHED),
        ("failed", TaskStatus.FAILED),
        ("canceled", TaskStatus.FAILED),
        (None, TaskStatus.QUEUED),
    ],
)
def test_map_rq_status_normalises_values(raw: str | None, expected: TaskStatus) -> None:
    assert map_rq_status(raw) is expected


def test_map_rq_status_unknown_raises() -> None:
    with pytest.raises(QueueAdapterError):
        map_rq_status("mystery")


def test_safe_queue_error_sanitises_message() -> None:
    err = safe_queue_error("mark_failed", "job-7", "Boom\nTraceback")
    assert isinstance(err, QueueError)
    assert "job-7" in str(err)
    assert "Traceback" not in str(err)
    assert "Boom" in str(err)

