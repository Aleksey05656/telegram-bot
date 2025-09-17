"""
@file: tests/workers/test_task_manager_policies.py
@description: Policy checks for TaskManager enqueue operations.
@dependencies: workers.task_manager
@created: 2025-09-23
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from workers.task_manager import TaskManager


class StubQueue:
    def __init__(self, job: object | None = None, *, raise_error: Exception | None = None) -> None:
        self.job = job or SimpleNamespace(id="job-stub")
        self.raise_error = raise_error
        self.calls: list[tuple[tuple, dict]] = []

    def enqueue(self, *args, **kwargs):
        if self.raise_error:
            raise self.raise_error
        self.calls.append((args, kwargs))
        return self.job


def build_task_manager() -> TaskManager:
    manager = TaskManager()
    manager.redis_conn = object()
    manager.prediction_queue = StubQueue()
    manager.retraining_queue = StubQueue()
    return manager


def test_enqueue_prediction_propagates_priority_and_ttl(monkeypatch) -> None:
    stub_process = lambda *args, **kwargs: None  # noqa: E731 - simple stub
    monkeypatch.setitem(sys.modules, "workers.prediction_worker", SimpleNamespace(process_prediction=stub_process))
    manager = build_task_manager()
    job = manager.enqueue_prediction(1, "Home", "Away", "job-1", priority="high")
    assert job is manager.prediction_queue.job
    args, kwargs = manager.prediction_queue.calls[0]
    assert args[0] is stub_process
    assert args[1:] == (1, "Home", "Away", "job-1")
    assert kwargs["job_id"] == "job-1"
    assert kwargs["ttl"] == 86400
    assert kwargs["result_ttl"] == 86400
    assert kwargs["meta"]["priority"] == "high"
    assert kwargs["meta"]["type"] == "prediction"


def test_enqueue_prediction_returns_none_when_not_initialised() -> None:
    manager = TaskManager()
    manager.redis_conn = None
    manager.prediction_queue = None
    result = manager.enqueue_prediction(1, "A", "B", "job-x")
    assert result is None


def test_enqueue_prediction_handles_queue_errors() -> None:
    manager = TaskManager()
    manager.redis_conn = object()
    manager.prediction_queue = StubQueue(raise_error=RuntimeError("boom"))
    result = manager.enqueue_prediction(1, "A", "B", "job-x")
    assert result is None


def test_enqueue_retraining_passes_metadata(monkeypatch) -> None:
    stub_train = lambda *args, **kwargs: None  # noqa: E731 - simple stub
    monkeypatch.setitem(sys.modules, "scripts.train_model", SimpleNamespace(train_and_persist=stub_train))
    manager = build_task_manager()
    job = manager.enqueue_retraining(reason="scheduled", season_id=2024)
    assert job is manager.retraining_queue.job
    args, kwargs = manager.retraining_queue.calls[0]
    assert args[0] is stub_train
    assert args[1] == 2024
    assert kwargs["ttl"] == 86400
    assert kwargs["result_ttl"] == 86400
    assert kwargs["meta"]["reason"] == "scheduled"
    assert kwargs["meta"]["type"] == "retraining"

