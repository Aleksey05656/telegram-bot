"""
@file: tests/workers/test_prediction_worker.py
@description: Tests for the dependency-injected prediction worker and queue interactions.
@dependencies: pytest
@created: 2025-09-20
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from core.services.predictor import PredictorServiceError
from workers.prediction_worker import (
    InvalidJobError,
    LockAcquisitionError,
    PredictionJob,
    PredictionWorker,
    PredictionWorkerError,
)
from workers.queue_adapter import IQueueAdapter, TaskStatus


class InMemoryQueueAdapter(IQueueAdapter):
    def __init__(self) -> None:
        self.started: list[tuple[str, dict[str, Any] | None]] = []
        self.finished: dict[str, dict[str, Any]] = {}
        self.failed: dict[str, dict[str, Any]] = {}

    async def mark_started(self, job_id: str, *, meta: dict[str, Any] | None = None) -> None:
        self.started.append((job_id, meta))

    async def mark_finished(self, job_id: str, payload: dict[str, Any]) -> None:
        self.finished[job_id] = payload

    async def mark_failed(
        self,
        job_id: str,
        reason: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.failed[job_id] = {"reason": reason, "details": details or {}}


@dataclass
class FakeLock:
    should_acquire: bool = True
    released: bool = False
    raise_on_release: bool = False

    async def acquire(self) -> bool:
        return self.should_acquire

    async def release(self) -> None:
        if self.raise_on_release:
            raise RuntimeError("release failed")
        self.released = True


class FakeRedisClient:
    def __init__(self, lock: FakeLock) -> None:
        self.lock_calls: list[tuple[str, float | None, float | None]] = []
        self._lock = lock

    def lock(self, key: str, timeout: float | None, blocking_timeout: float | None) -> FakeLock:
        self.lock_calls.append((key, timeout, blocking_timeout))
        return self._lock


class DummyRedisFactory:
    def __init__(self, client: FakeRedisClient | None) -> None:
        self._client = client

    async def get_client(self) -> FakeRedisClient | None:
        return self._client


class StubPredictor:
    def __init__(self, *, result: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self._result = result or {
            "probs": {"H": 0.4, "D": 0.3, "A": 0.3},
            "totals": {
                "over_2_5": 0.55,
                "under_2_5": 0.45,
                "btts_yes": 0.6,
                "btts_no": 0.4,
            },
            "scoreline_topk": [{"score": "1:0", "probability": 0.18}],
        }
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def generate_prediction(
        self,
        fixture_id: str | None = None,
        *,
        home: str | None = None,
        away: str | None = None,
        seed: int,
        n_sims: int,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "fixture_id": fixture_id,
                "home": home,
                "away": away,
                "seed": seed,
                "n_sims": n_sims,
            }
        )
        if self._error is not None:
            raise self._error
        return self._result


@pytest.mark.asyncio
async def test_worker_happy_path_marks_statuses() -> None:
    queue = InMemoryQueueAdapter()
    lock = FakeLock()
    redis_factory = DummyRedisFactory(FakeRedisClient(lock))
    predictor = StubPredictor()
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=redis_factory,
        lock_timeout=3.0,
        lock_blocking_timeout=0.1,
    )

    job = PredictionJob(job_id="job-1", fixture_id="1", home="Alpha", away="Beta")
    result = await worker.handle(job)

    assert queue.started[0][0] == "job-1"
    assert queue.started[0][1]["status"] == TaskStatus.STARTED.value
    assert queue.finished["job-1"]["status"] == TaskStatus.FINISHED.value
    assert "result" in queue.finished["job-1"]
    assert lock.released is True
    assert predictor.calls and predictor.calls[0]["seed"] > 0
    assert result["probs"]["H"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_worker_propagates_engine_failure() -> None:
    queue = InMemoryQueueAdapter()
    redis_factory = DummyRedisFactory(None)
    predictor = StubPredictor(error=PredictorServiceError("boom"))
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=redis_factory,
    )

    job = PredictionJob(job_id="job-err", fixture_id="1", home="Alpha", away="Beta")
    with pytest.raises(PredictionWorkerError):
        await worker.handle(job)

    assert queue.failed["job-err"]["reason"] == "prediction_failed"


@pytest.mark.asyncio
async def test_worker_handles_lock_timeout() -> None:
    queue = InMemoryQueueAdapter()
    lock = FakeLock(should_acquire=False)
    redis_factory = DummyRedisFactory(FakeRedisClient(lock))
    predictor = StubPredictor()
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=redis_factory,
    )

    job = PredictionJob(job_id="job-lock", fixture_id="1", home="Alpha", away="Beta")
    with pytest.raises(LockAcquisitionError):
        await worker.handle(job)

    assert queue.failed["job-lock"]["reason"] == "lock_timeout"
    assert "prediction already in progress" in queue.failed["job-lock"]["details"]["message"]


@pytest.mark.asyncio
async def test_worker_validates_job_payload() -> None:
    queue = InMemoryQueueAdapter()
    redis_factory = DummyRedisFactory(None)
    predictor = StubPredictor()
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=redis_factory,
    )

    job = PredictionJob(job_id="invalid")
    with pytest.raises(InvalidJobError):
        await worker.handle(job)

    assert queue.failed["invalid"]["reason"] == "invalid_job"
