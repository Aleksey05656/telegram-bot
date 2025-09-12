"""
@file: tests/conftest.py
@description: Pytest fixtures to enable Prometheus metrics and reset settings cache
@dependencies: app/config.py
@created: 2025-09-10
"""

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app import config as cfg


@pytest.fixture(autouse=True)
def _force_prometheus_enabled(monkeypatch):
    monkeypatch.setenv("PROMETHEUS__ENABLED", "true")
    if hasattr(cfg, "reset_settings_cache"):
        cfg.reset_settings_cache()
    yield


@pytest.fixture(autouse=True)
def _defaults_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", os.getenv("APP_NAME", "ml-service"))
    monkeypatch.setenv("DEBUG", os.getenv("DEBUG", "false"))
    yield
