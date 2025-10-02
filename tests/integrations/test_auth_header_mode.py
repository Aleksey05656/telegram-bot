"""
/**
 * @file: test_auth_header_mode.py
 * @description: Verifies SportMonks client sends Authorization header when configured.
 * @dependencies: app.integrations.sportmonks_client, pytest, requests
 * @created: 2025-10-05
 */
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
import requests


def _reload_client(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    module = importlib.import_module("app.integrations.sportmonks_client")
    return importlib.reload(module)


def test_header_auth_mode(monkeypatch):
    module = _reload_client(
        monkeypatch,
        SPORTMONKS_API_TOKEN="secret-token",
        SPORTMONKS_AUTH_MODE="header",
        SPORTMONKS_STUB="0",
    )

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):  # pragma: no cover - exercised via client
        prepared = requests.Request("GET", url, params=params).prepare()
        captured["params"] = dict(params)
        captured["headers"] = headers
        captured["url"] = prepared.url
        captured["timeout"] = timeout
        return SimpleNamespace(
            status_code=200,
            url=prepared.url,
            text="{}",
            headers={},
            json=lambda: {"data": [], "meta": {"pagination": {"total_pages": 1}}},
        )

    monkeypatch.setattr(module.requests, "get", fake_get)

    client = module.SportMonksClient()
    fixtures = client.fixtures_by_date("2025-10-05")

    assert fixtures == []
    assert captured["headers"] == {"Authorization": "secret-token"}
    assert "api_token" not in captured["params"]
    assert captured["timeout"] == 10
    assert captured["url"].endswith("/fixtures/date/2025-10-05?page=1")


__all__ = ["test_header_auth_mode"]
