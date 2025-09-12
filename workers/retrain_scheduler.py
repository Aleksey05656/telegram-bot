"""
@file: retrain_scheduler.py
@description: Minimal retrain scheduler wiring with env-based cron.
@dependencies: os, optional training task
@created: 2025-09-12
"""
from __future__ import annotations

import os
from typing import Callable, Optional


def _default_task():
    """
    Lazy import to avoid heavy deps at import time.
    Replace with actual training job body later.
    """
    try:
        # prefer project-local trainer if present
        from app.ml.train_base_glm import train_base_glm  # type: ignore

        train_base_glm(train_df=None, cfg=None)
        return
    except Exception:
        pass

    # fallback: lightweight no-op
    return None


def schedule_retrain(
    register: Callable[[str, Callable[[], None]], None],
    cron_expr: Optional[str] = None,
    task: Optional[Callable[[], None]] = None,
) -> str:
    """
    Register periodic retrain job.
    - register: function provided by your scheduler integration
    - cron_expr: optional cron string; if None, uses env RETRAIN_CRON or default
    - task: optional callable; if None, uses _default_task
    Returns the effective cron expression used (for logging/tests).
    """
    effective_cron = cron_expr or os.getenv("RETRAIN_CRON", "0 3 * * *")
    register(effective_cron, task or _default_task)
    return effective_cron
