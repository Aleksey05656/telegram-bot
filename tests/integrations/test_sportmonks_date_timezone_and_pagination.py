"""
/**
 * @file: test_sportmonks_date_timezone_and_pagination.py
 * @description: Tests SportMonks fixtures_by_date pagination, includes and timezone handling.
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


def test_fixtures_by_date_timezone_include_pagination(monkeypatch, caplog):
    module = _reload_client(
        monkeypatch,
        SPORTMONKS_API_TOKEN="secret-token",
        SPORTMONKS_STUB="0",
        SPORTMONKS_AUTH_MODE="query",
        SPORTMONKS_INCLUDES=None,
    )

    payloads = {
        1: {
            "data": [{"id": 1001}],
            "meta": {"pagination": {"current_page": 1, "total_pages": 2}},
        },
        2: {
            "data": [{"id": 1002}],
            "meta": {"pagination": {"current_page": 2, "total_pages": 2}},
        },
    }
    captured = []

    def fake_get(url, params=None, headers=None, timeout=None):  # pragma: no cover - exercised via client
        prepared = requests.Request("GET", url, params=params).prepare()
        page = int(params["page"])
        captured.append((prepared, dict(params), headers, timeout))
        payload = payloads[page]
        return SimpleNamespace(
            status_code=200,
            url=prepared.url,
            text="{\"data\": []}",
            headers={},
            json=lambda: payload,
        )

    monkeypatch.setattr(module.requests, "get", fake_get)

    client = module.SportMonksClient()
    fixtures = client.fixtures_by_date(
        "2025-10-05",
        include="participants;scores",
        timezone="Europe/Amsterdam",
        per_page=2,
    )

    assert fixtures == [{"id": 1001}, {"id": 1002}]
    assert len(captured) == 2

    for prepared, params, headers, timeout in captured:
        assert prepared.url.startswith("https://api.sportmonks.com/v3/football/fixtures/date/2025-10-05")
        assert params["include"] == "participants;scores"
        assert params["timezone"] == "Europe/Amsterdam"
        assert params["per_page"] == "2"
        assert params["api_token"] == "secret-token"
        assert "page" in params
        assert headers is None
        assert timeout == 10

    assert "secret-token" not in caplog.text


__all__ = ["test_fixtures_by_date_timezone_include_pagination"]
