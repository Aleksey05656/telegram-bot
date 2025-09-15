"""
@file: tests/conftest.py
@description: Pytest fixtures with numpy/pandas guard
@dependencies: app/config.py, tests/conftest_np_guard.py
@created: 2025-09-10
"""

import os
import pathlib
import sys

import pytest

pytest_plugins = ["conftest_np_guard"]


# Автоматически включаем STUB-режим SportMonks для тестов,
# если ключ отсутствует или равен "dummy".
@pytest.fixture(autouse=True, scope="session")
def _force_sportmonks_stub():
    key = os.getenv("SPORTMONKS_API_KEY", "")
    if (not key) or (key.lower() == "dummy"):
        os.environ["SPORTMONKS_STUB"] = "1"
    return


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config as cfg  # noqa: E402


@pytest.fixture(autouse=True)
def _force_prometheus_enabled(monkeypatch):
    monkeypatch.setenv("PROMETHEUS__ENABLED", "true")
    if hasattr(cfg, "reset_settings_cache"):
        cfg.reset_settings_cache()
    return


@pytest.fixture(autouse=True)
def _defaults_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", os.getenv("APP_NAME", "ml-service"))
    monkeypatch.setenv("DEBUG", os.getenv("DEBUG", "false"))
    return
