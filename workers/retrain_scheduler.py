"""
@file: retrain_scheduler.py
@description: Retrain scheduler with freshness guard based on Sportmonks data.
@dependencies: datetime, os
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.data_providers.sportmonks.repository import SportmonksRepository
from logger import logger


def _default_task() -> None:
    """Lazy import training routine if available; otherwise no-op."""

    try:
        from app.ml.train_base_glm import train_base_glm  # type: ignore

        train_base_glm(train_df=None, cfg=None)
        return
    except Exception:  # pragma: no cover - best effort import guard
        logger.debug("Fallback training stub used", extra={"component": "retrain"})


def schedule_retrain(
    register: Callable[[str, Callable[[], None]], None],
    cron_expr: str | None = None,
    task: Callable[[], None] | None = None,
) -> str:
    """Register retrain job guarded by Sportmonks freshness gate."""

    effective_cron = cron_expr or os.getenv("RETRAIN_CRON", "0 3 * * *")
    guarded_task = _wrap_with_freshness_guard(task or _default_task)
    register(effective_cron, guarded_task)
    return effective_cron


def _wrap_with_freshness_guard(task: Callable[[], None]) -> Callable[[], None]:
    settings = get_settings()
    max_age_hours = settings.sm_freshness_warn_hours
    repository = SportmonksRepository()

    def _runner() -> None:
        try:
            last_sync = repository.last_sync_timestamp()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Unable to read Sportmonks freshness; running retrain by default",
                extra={"error": str(exc)},
            )
            task()
            return

        if not last_sync:
            logger.warning(
                "Skipping retrain: Sportmonks sync has not completed yet",
                extra={"component": "retrain", "reason": "no-sync"},
            )
            return

        age = datetime.now(tz=timezone.utc) - last_sync
        if age > timedelta(hours=max_age_hours):
            logger.info(
                "Skipping retrain due to stale Sportmonks data",
                extra={"component": "retrain", "age_hours": age.total_seconds() / 3600},
            )
            return

        task()

    return _runner
