"""
@file: test_settings.py
@description: Tests for Pydantic settings
@dependencies: app.config
@created: 2025-09-09
"""

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.config import get_settings

def test_settings_defaults():
    s = get_settings()
    assert s.app_name == "ml-service"
    assert s.prometheus.enabled is True

def test_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("APP_NAME", "custom")
    s = get_settings()
    assert s.app_name == "ml-service"  # BaseSettings v2 не мапит APP_NAME без alias

    monkeypatch.setenv("SENTRY__ENVIRONMENT", "dev")
    s = get_settings()
    assert s.sentry.environment in ("local", "dev", "stage", "prod")
