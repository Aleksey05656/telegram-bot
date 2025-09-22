"""
/**
 * @file: tests/workers/test_queue_adapter_edges.py
 * @description: Edge-case coverage for queue adapter status mapping and error sanitisation.
 * @dependencies: pytest, unittest.mock, workers.queue_adapter
 * @created: 2025-09-29
 */
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from workers.queue_adapter import QueueError, TaskStatus, map_rq_status, safe_queue_error


class FakeRedisConnectionError(RuntimeError):
    """Stub exception modelling redis.exceptions.ConnectionError."""


class FakeRQNoSuchJobError(RuntimeError):
    """Stub exception modelling rq.exceptions.NoSuchJobError."""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" queued ", TaskStatus.QUEUED),
        ("SCHEDULED", TaskStatus.QUEUED),
        (" deferred ", TaskStatus.QUEUED),
        ("RUNNING", TaskStatus.STARTED),
        (" completed ", TaskStatus.FINISHED),
        ("STOPPED", TaskStatus.FAILED),
        ("Canceled", TaskStatus.FAILED),
        (None, TaskStatus.QUEUED),
    ],
)
def test_map_rq_status_normalises_sparse_variants(raw: str | None, expected: TaskStatus) -> None:
    """Ensure we align unusual RQ status variants with our literals/default."""

    assert map_rq_status(raw) is expected


@pytest.mark.parametrize(
    ("action", "exc_cls", "message"),
    [
        (
            "enqueue",
            FakeRedisConnectionError,
            "Redis connection lost\nTraceback (most recent call last)",
        ),
        (
            "status",
            FakeRQNoSuchJobError,
            "Job 42 does not exist\nTraceback (most recent call last)",
        ),
        (
            "cancel",
            FakeRedisConnectionError,
            "Connection timed out\nTraceback details",
        ),
    ],
)
def test_safe_queue_error_wraps_rq_and_redis_exceptions(
    action: str, exc_cls: type[Exception], message: str
) -> None:
    """Convert RQ/Redis exceptions into sanitised QueueError messages without touching the network."""

    queue_mock = Mock()
    setattr(queue_mock, action, Mock(side_effect=exc_cls(message)))

    with pytest.raises(QueueError) as excinfo:
        try:
            getattr(queue_mock, action)()
        except Exception as exc:  # pragma: no cover - defensive harness
            raise safe_queue_error(action, "job-42", exc)

    payload = str(excinfo.value)
    assert action in payload
    assert "job-42" in payload
    assert "\n" not in payload
    assert "Traceback" not in payload


def test_safe_queue_error_handles_missing_exception_message() -> None:
    """Gracefully handle exceptions that provide an empty string message."""

    with pytest.raises(QueueError) as excinfo:
        raise safe_queue_error("status", "job-0", ValueError())

    rendered = str(excinfo.value)
    assert rendered.endswith("job 'job-0'")
    assert ":" not in rendered.split("job 'job-0'")[0]
