"""
/**
 * @file: tests/workers/test_queue_adapter_edges.py
 * @description: Edge-case coverage for queue adapter status mapping and error sanitisation.
 * @dependencies: pytest, workers.queue_adapter
 * @created: 2025-09-24
 */
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from workers.queue_adapter import QueueError, TaskStatus, map_rq_status, safe_queue_error


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" SCHEDULED ", TaskStatus.QUEUED),
        ("DEFERRED", TaskStatus.QUEUED),
        ("running", TaskStatus.STARTED),
        (" COMPLETED", TaskStatus.FINISHED),
        ("STOPPED ", TaskStatus.FAILED),
        ("Canceled", TaskStatus.FAILED),
        (None, TaskStatus.QUEUED),
    ],
)
def test_map_rq_status_handles_case_and_whitespace(raw: str | None, expected: TaskStatus) -> None:
    """Ensure RQ edge-case statuses converge to internal literals."""

    assert map_rq_status(raw) is expected


@pytest.mark.parametrize(
    "action",
    ["enqueue", "status", "cancel"],
)
def test_safe_queue_error_masks_tracebacks(action: str) -> None:
    """Simulate RQ failures and ensure sanitised QueueError output."""

    queue = Mock()
    setattr(queue, action, Mock(side_effect=RuntimeError("redis://user:pass@host/0\nTraceback")))

    with pytest.raises(QueueError) as excinfo:
        try:
            getattr(queue, action)()
        except Exception as exc:  # pragma: no cover - defensive test harness
            raise safe_queue_error(action, "job-42", exc)

    message = str(excinfo.value)
    assert action in message
    assert "job-42" in message
    assert "\n" not in message
    assert "Traceback" not in message


def test_safe_queue_error_handles_empty_exception_message() -> None:
    """When upstream raises without message we keep the generic context only."""

    with pytest.raises(QueueError) as excinfo:
        raise safe_queue_error("status", "job-0", ValueError())

    message = str(excinfo.value)
    assert message.endswith("job 'job-0'")
    assert ":" not in message.split("job 'job-0'")[0]
