"""
@file: tests/conftest.py
@description: Pytest fixtures to enable Prometheus metrics and reset settings cache
@dependencies: app/config.py
@created: 2025-09-10
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import pytest

from app import config as cfg


@pytest.fixture(autouse=True)
def _force_prometheus_enabled(monkeypatch):
    # Гарантируем доступность /metrics в тестах
    monkeypatch.setenv("PROMETHEUS__ENABLED", "true")
    # Сбрасываем кэш настроек перед каждым тестом, чтобы env подхватился
    if hasattr(cfg, "reset_settings_cache"):
        cfg.reset_settings_cache()
    return
