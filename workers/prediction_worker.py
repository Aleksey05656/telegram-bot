"""
@file: workers/prediction_worker.py
@description: Dependency-injected prediction worker handling queue statuses and locks.
@dependencies: core.services.predictor, services.recommendation_engine, workers.queue_adapter
@created: 2025-09-20
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from config import get_settings
from core.services import PredictorService
from core.services.predictor import PredictorServiceError
from database import DBRouter, get_db_router
from logger import logger
from services.recommendation_engine import (
    InvalidPredictionRequest,
    PredictionEngineError,
    RecommendationEngine,
)
from workers.queue_adapter import IQueueAdapter, TaskStatus
from workers.redis_factory import RedisFactory


class PredictionWorkerError(RuntimeError):
    """Base worker error."""


class InvalidJobError(PredictionWorkerError):
    """Raised when incoming job does not contain the required identifiers."""


class LockAcquisitionError(PredictionWorkerError):
    """Raised when Redis lock could not be acquired in a timely manner."""


@dataclass(slots=True)
class PredictionJob:
    """Job description passed to :class:`PredictionWorker`."""

    job_id: str
    fixture_id: str | None = None
    home: str | None = None
    away: str | None = None
    chat_id: int | None = None
    n_sims: int | None = None
    seed: int | None = None


class _NullQueueAdapter(IQueueAdapter):
    """Fallback queue adapter used when no persistence is supplied."""

    async def mark_started(self, job_id: str, *, meta: dict[str, Any] | None = None) -> None:
        logger.debug("queue[%s] started meta=%s", job_id, meta or {})

    async def mark_finished(self, job_id: str, payload: dict[str, Any]) -> None:
        logger.debug("queue[%s] finished payload=%s", job_id, json.dumps(payload)[:256])

    async def mark_failed(
        self,
        job_id: str,
        reason: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        logger.debug(
            "queue[%s] failed reason=%s details=%s", job_id, reason, json.dumps(details or {})[:256]
        )


class PredictionWorker:
    """Handle prediction jobs using injected services."""

    def __init__(
        self,
        *,
        predictor: PredictorService,
        queue: IQueueAdapter,
        redis_factory: RedisFactory,
        lock_timeout: float | None = None,
        lock_blocking_timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self._predictor = predictor
        self._queue = queue
        self._redis_factory = redis_factory
        self._default_seed = getattr(settings, "SIM_SEED", 7)
        self._default_sims = getattr(settings, "SIM_N", 10_000)
        self._lock_timeout = (
            lock_timeout if lock_timeout is not None else getattr(settings, "PREDICTION_LOCK_TIMEOUT", 60.0)
        )
        self._lock_blocking_timeout = (
            lock_blocking_timeout
            if lock_blocking_timeout is not None
            else getattr(settings, "PREDICTION_LOCK_BLOCKING_TIMEOUT", 5.0)
        )

    async def handle(self, job: PredictionJob) -> dict[str, Any]:
        if job.fixture_id is None and (job.home is None or job.away is None):
            await self._queue.mark_failed(
                job.job_id,
                "invalid_job",
                details={"message": "fixture_id or both teams must be provided"},
            )
            raise InvalidJobError("Prediction job missing fixture information")

        seed = job.seed if job.seed is not None else self._default_seed
        n_sims = job.n_sims if job.n_sims is not None else self._default_sims

        await self._queue.mark_started(
            job.job_id,
            meta={"status": TaskStatus.STARTED.value, "seed": seed, "n_sims": n_sims},
        )

        lock = None
        lock_key = self._lock_key(job)
        redis = await self._redis_factory.get_client()
        if redis is not None:
            try:
                lock = redis.lock(
                    lock_key,
                    timeout=self._lock_timeout,
                    blocking_timeout=self._lock_blocking_timeout,
                )
                acquired = await lock.acquire()
            except Exception as exc:  # pragma: no cover - defensive logging
                await self._queue.mark_failed(
                    job.job_id,
                    "lock_error",
                    details={"message": str(exc)},
                )
                raise LockAcquisitionError("Failed to acquire redis lock") from exc
            if not acquired:
                await self._queue.mark_failed(
                    job.job_id,
                    "lock_timeout",
                    details={"message": "prediction already in progress"},
                )
                raise LockAcquisitionError("Lock acquisition timed out")

        try:
            payload = await self._predictor.generate_prediction(
                job.fixture_id,
                home=job.home,
                away=job.away,
                seed=seed,
                n_sims=n_sims,
            )
        except (PredictorServiceError, PredictionEngineError, InvalidPredictionRequest) as exc:
            await self._queue.mark_failed(
                job.job_id,
                "prediction_failed",
                details={"message": str(exc)},
            )
            raise PredictionWorkerError(str(exc)) from exc
        finally:
            if lock is not None:
                try:
                    await lock.release()
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.debug("redis lock release failed for %s: %s", lock_key, exc)

        await self._queue.mark_finished(
            job.job_id,
            {
                "status": TaskStatus.FINISHED.value,
                "result": payload,
            },
        )
        return payload

    @staticmethod
    def _lock_key(job: PredictionJob) -> str:
        parts = [
            "prediction",
            job.fixture_id or "none",
            (job.home or "home").lower().replace(" ", "-"),
            (job.away or "away").lower().replace(" ", "-"),
        ]
        return ":".join(parts)


def build_prediction_worker(
    *,
    queue: IQueueAdapter | None = None,
    redis_factory: RedisFactory | None = None,
    db_router: DBRouter | None = None,
) -> PredictionWorker:
    router = db_router or get_db_router()
    engine = RecommendationEngine(router)
    predictor = PredictorService(engine)
    queue_adapter = queue or _NullQueueAdapter()
    redis_factory_instance = redis_factory or RedisFactory()
    return PredictionWorker(
        predictor=predictor,
        queue=queue_adapter,
        redis_factory=redis_factory_instance,
    )


async def run_prediction_job(worker: PredictionWorker, job: PredictionJob) -> dict[str, Any]:
    """Convenience helper for tests and orchestration layers."""
    return await worker.handle(job)
