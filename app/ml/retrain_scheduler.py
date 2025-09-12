"""
@file: retrain_scheduler.py
@description: cron-based retraining task registration
@dependencies: train_base_glm
@created: 2025-09-10
"""

from __future__ import annotations

from collections.abc import Callable


def schedule_retrain(register: Callable[[str, Callable], None], cron_expr: str = "0 3 * * *"):
    """
    Регистрирует задачу переобучения по cron.
    `register` — функция вашей системы планирования (APScheduler/Celery/K8s CronBridge).
    """

    def _task():
        from .train_base_glm import train_base_glm

        # Здесь можно добавить загрузку данных/конфигов
        train_base_glm(train_df=None, cfg=None)

    register(cron_expr, _task)
