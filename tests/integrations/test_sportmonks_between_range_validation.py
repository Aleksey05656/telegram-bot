"""
/**
 * @file: test_sportmonks_between_range_validation.py
 * @description: Validates SportMonks fixtures_between date range constraints.
 * @dependencies: app.integrations.sportmonks_client, pytest
 * @created: 2025-10-05
 */
"""
from __future__ import annotations

import importlib

import pytest


def _reload_client(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    module = importlib.import_module("app.integrations.sportmonks_client")
    return importlib.reload(module)


def test_between_invalid_formats(monkeypatch):
    module = _reload_client(monkeypatch, SPORTMONKS_STUB="0", SPORTMONKS_API_TOKEN="token")
    monkeypatch.setattr(module.requests, "get", lambda *_a, **_kw: pytest.fail("HTTP should not be called"))
    client = module.SportMonksClient()

    with pytest.raises(module.SportMonksValidationError):
        client.fixtures_between("2025-1-01", "2025-01-10")

    with pytest.raises(module.SportMonksValidationError):
        client.fixtures_between("2025-01-01", "2025/01/10")


def test_between_end_before_start(monkeypatch):
    module = _reload_client(monkeypatch, SPORTMONKS_STUB="0", SPORTMONKS_API_TOKEN="token")
    monkeypatch.setattr(module.requests, "get", lambda *_a, **_kw: pytest.fail("HTTP should not be called"))
    client = module.SportMonksClient()

    with pytest.raises(module.SportMonksValidationError):
        client.fixtures_between("2025-01-10", "2025-01-05")


def test_between_range_over_100_days(monkeypatch):
    module = _reload_client(monkeypatch, SPORTMONKS_STUB="0", SPORTMONKS_API_TOKEN="token")
    monkeypatch.setattr(module.requests, "get", lambda *_a, **_kw: pytest.fail("HTTP should not be called"))
    client = module.SportMonksClient()

    with pytest.raises(module.SportMonksValidationError):
        client.fixtures_between("2025-01-01", "2025-04-20")


__all__ = [
    "test_between_invalid_formats",
    "test_between_end_before_start",
    "test_between_range_over_100_days",
]
