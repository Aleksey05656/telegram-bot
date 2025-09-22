"""
/**
 * @file: tests/workers/test_prediction_worker_errors.py
 * @description: Regression tests covering error handling branches of PredictionWorker.
 * @dependencies: pytest, workers.prediction_worker
 * @created: 2025-09-24
 */
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import pytest

from core.services.predictor import PredictorServiceError
from services.recommendation_engine import InvalidPredictionRequest
from workers.prediction_worker import (
    InvalidJobError,
    LockAcquisitionError,
    PredictionJob,
    PredictionWorker,
    PredictionWorkerError,
    _NullQueueAdapter,
)
from workers.queue_adapter import IQueueAdapter


class RecordingQueue(IQueueAdapter):
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: dict[str, dict[str, Any]] = {}
        self.failed: dict[str, dict[str, Any]] = {}

    async def mark_started(self, job_id: str, *, meta: dict[str, Any] | None = None) -> None:
        self.started.append({"job_id": job_id, "meta": meta or {}})

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


class LoggingRecordingQueue(_NullQueueAdapter):
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: dict[str, dict[str, Any]] = {}
        self.failed: dict[str, dict[str, Any]] = {}

    async def mark_started(self, job_id: str, *, meta: dict[str, Any] | None = None) -> None:
        self.started.append({"job_id": job_id, "meta": meta or {}})
        await super().mark_started(job_id, meta=meta)

    async def mark_finished(self, job_id: str, payload: dict[str, Any]) -> None:
        self.finished[job_id] = payload
        await super().mark_finished(job_id, payload)

    async def mark_failed(
        self,
        job_id: str,
        reason: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.failed[job_id] = {"reason": reason, "details": details or {}}
        await super().mark_failed(job_id, reason, details=details)


class NullRedisFactory:
    async def get_client(self) -> None:
        return None


@dataclass
class TimeoutLock:
    acquire_calls: int = 0

    async def acquire(self) -> bool:
        self.acquire_calls += 1
        return False

    async def release(self) -> None:  # pragma: no cover - never invoked in timeout path
        return None


class StaticRedisClient:
    def __init__(self, lock: TimeoutLock) -> None:
        self.lock_instance = lock
        self.lock_calls: list[dict[str, Any]] = []

    def lock(
        self,
        key: str,
        timeout: float | None,
        blocking_timeout: float | None,
    ) -> TimeoutLock:
        self.lock_calls.append(
            {
                "key": key,
                "timeout": timeout,
                "blocking_timeout": blocking_timeout,
            }
        )
        return self.lock_instance


class StaticRedisFactory:
    def __init__(self, client: StaticRedisClient) -> None:
        self._client = client

    async def get_client(self) -> StaticRedisClient:
        return self._client


class SpyPredictor:
    def __init__(
        self,
        *,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
        validator: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._result = result or {"result": "ok"}
        self._error = error
        self._validator = validator
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
            context := {
                "fixture_id": fixture_id,
                "home": home,
                "away": away,
                "seed": seed,
                "n_sims": n_sims,
            }
        )
        if self._validator is not None:
            self._validator(context)
        if self._error is not None:
            raise self._error
        return self._result


class SecretBearingError(PredictorServiceError):
    def __init__(self, public_message: str, secret: str) -> None:
        super().__init__(public_message)
        self.secret = secret
        self._public_message = public_message

    def __str__(self) -> str:  # pragma: no cover - inherited behaviour sufficient
        return self._public_message


class SpyLogger:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def _record(self, level: str, message: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.calls.append({"level": level, "message": message, "args": args, "kwargs": kwargs})

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._record("debug", message, args, kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - delegated
        self._record("info", message, args, kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - delegated
        self._record("warning", message, args, kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - delegated
        self._record("error", message, args, kwargs)


@pytest.mark.asyncio
async def test_worker_masks_core_error_details(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = LoggingRecordingQueue()
    spy_logger = SpyLogger()
    monkeypatch.setattr("workers.prediction_worker.logger", spy_logger)
    predictor = SpyPredictor(
        error=SecretBearingError("core failure", secret="token-123")
    )
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=NullRedisFactory(),
    )

    job = PredictionJob(job_id="job-core", fixture_id="42", home="Alpha", away="Beta")
    with pytest.raises(PredictionWorkerError) as excinfo:
        await worker.handle(job)

    failure = queue.failed["job-core"]
    assert failure["reason"] == "prediction_failed"
    assert failure["details"]["message"] == "core failure"
    assert "token-123" not in failure["details"]["message"]
    assert "token-123" not in str(excinfo.value)
    assert "job-core" in queue.started[0]["job_id"]
    assert "job-core" not in queue.finished
    assert spy_logger.calls, "Expected worker logger to receive debug entries"
    for entry in spy_logger.calls:
        assert "token-123" not in entry["message"]
        assert all("token-123" not in str(arg) for arg in entry["args"])


@pytest.mark.asyncio
async def test_worker_handles_lock_timeout_without_duplicates() -> None:
    queue = RecordingQueue()
    lock = TimeoutLock()
    redis_factory = StaticRedisFactory(StaticRedisClient(lock))
    predictor = SpyPredictor()
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=redis_factory,
        lock_timeout=1.0,
        lock_blocking_timeout=0.1,
    )

    job = PredictionJob(job_id="job-lock", fixture_id="1", home="Alpha", away="Beta")
    with pytest.raises(LockAcquisitionError):
        await worker.handle(job)

    assert len(queue.started) == 1
    assert queue.failed["job-lock"]["reason"] == "lock_timeout"
    assert queue.finished == {}
    assert lock.acquire_calls == 1
    assert predictor.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("invalid_value", "expected_message"),
    [
        (-5, "n_sims must be positive"),
        (float("nan"), "n_sims must be a finite integer"),
    ],
)
async def test_worker_rejects_dirty_payload(invalid_value: float, expected_message: str) -> None:
    queue = RecordingQueue()

    def _validator(params: dict[str, Any]) -> None:
        value = params["n_sims"]
        if math.isnan(value) if isinstance(value, float) else False:
            raise InvalidPredictionRequest("n_sims must be a finite integer")
        if isinstance(value, (int, float)) and value <= 0:
            raise InvalidPredictionRequest("n_sims must be positive")

    predictor = SpyPredictor(validator=_validator)
    worker = PredictionWorker(
        predictor=predictor,
        queue=queue,
        redis_factory=NullRedisFactory(),
    )

    job = PredictionJob(
        job_id="job-dirty",
        fixture_id="99",
        home="Alpha",
        away="Beta",
        n_sims=invalid_value,
    )
    with pytest.raises(PredictionWorkerError) as excinfo:
        await worker.handle(job)

    failure = queue.failed["job-dirty"]
    assert failure["reason"] == "prediction_failed"
    assert failure["details"]["message"] == expected_message
    assert queue.finished == {}

    assert expected_message in str(excinfo.value)

    with pytest.raises(InvalidJobError):
        await worker.handle(PredictionJob(job_id="invalid"))
