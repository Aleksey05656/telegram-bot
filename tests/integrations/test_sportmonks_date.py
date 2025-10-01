"""
/**
 * @file: tests/integrations/test_sportmonks_date.py
 * @description: Integration checks for SportMonks client date handling and error surfacing.
 * @dependencies: app.integrations.sportmonks_client, pytest, requests
 * @created: 2025-10-01
 */
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
import requests


def _fresh_client(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    module = importlib.import_module("app.integrations.sportmonks_client")
    return importlib.reload(module)


def test_fixtures_by_date_uses_token_and_strict_date(monkeypatch):
    module = _fresh_client(
        monkeypatch,
        SPORTMONKS_API_TOKEN="secret-token",
        SPORTMONKS_STUB="0",
        SPORTMONKS_API_KEY=None,
        SPORTMONKS_INCLUDES=None,
    )

    captured: dict[str, object] = {}

    def fake_get(url, params, timeout):  # pragma: no cover - invoked via _get
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        prepared = requests.Request("GET", url, params=params).prepare()
        return SimpleNamespace(
            status_code=200,
            text="{\"data\": []}",
            url=prepared.url,
            json=lambda: {"data": [{"id": 1}]},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(module.requests, "get", fake_get)

    client = module.SportMonksClient()
    fixtures = client.fixtures_by_date("2025-10-01")

    assert captured["url"].endswith("/fixtures/date/2025-10-01")
    assert captured["params"] == {"api_token": "secret-token"}
    assert captured["timeout"] == 10
    assert fixtures == [{"id": 1}]


def test_invalid_date_short_circuits_request(monkeypatch):
    module = _fresh_client(
        monkeypatch,
        SPORTMONKS_API_TOKEN="valid-token",
        SPORTMONKS_STUB="0",
        SPORTMONKS_API_KEY=None,
    )

    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: pytest.fail("HTTP called"))

    client = module.SportMonksClient()

    with pytest.raises(ValueError):
        client.fixtures_by_date("2025-13-40")


def test_http_error_logs_body_and_masks_token(monkeypatch):
    module = _fresh_client(
        monkeypatch,
        SPORTMONKS_API_TOKEN="super-secret",
        SPORTMONKS_STUB="0",
        SPORTMONKS_API_KEY=None,
    )

    def failing_get(url, params, timeout):  # pragma: no cover - invoked via _get
        prepared = requests.Request("GET", url, params=params).prepare()

        class _Response:
            status_code = 400
            text = "boom"
            url = prepared.url

            def json(self):
                return {}

            def raise_for_status(self):
                raise requests.HTTPError("boom")

        return _Response()

    monkeypatch.setattr(module.requests, "get", failing_get)

    captured: list[str] = []

    class _StubLogger:
        def error(self, msg: str, *args, **kwargs) -> None:  # pragma: no cover - test hook
            formatted = msg % args if args else msg
            captured.append(str(formatted))

    monkeypatch.setattr(module, "logger", _StubLogger())

    client = module.SportMonksClient()

    with pytest.raises(requests.HTTPError):
        client.fixtures_by_date("2025-10-01")

    assert captured, "Expected logger.error to be invoked"
    payload = " ".join(captured)
    assert "***" in payload
    assert "super-secret" not in payload
    assert "boom" in payload


__all__ = [
    "test_fixtures_by_date_uses_token_and_strict_date",
    "test_invalid_date_short_circuits_request",
    "test_http_error_logs_body_and_masks_token",
]
