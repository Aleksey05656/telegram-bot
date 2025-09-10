"""
@file: tests/conftest.py
@description: Pytest fixtures to enable Prometheus metrics and reset settings cache
@dependencies: app/config.py
@created: 2025-09-10
"""

import os

import pytest

from app import config as cfg


@pytest.fixture(autouse=True)
def _force_prometheus_enabled(monkeypatch):
    # Гарантируем доступность /metrics в тестах
    monkeypatch.setenv("PROMETHEUS__ENABLED", "true")
    # Сбрасываем кэш настроек перед каждым тестом, чтобы env подхватился
    if hasattr(cfg, "reset_settings_cache"):
        cfg.reset_settings_cache()
    yield
