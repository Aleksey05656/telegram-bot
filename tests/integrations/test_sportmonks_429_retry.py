"""
/**
 * @file: test_sportmonks_429_retry.py
 * @description: Ensures SportMonks client respects Retry-After and raises after repeated 429s.
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


def test_rate_limit_retry_and_failure(monkeypatch):
    module = _reload_client(
        monkeypatch,
        SPORTMONKS_API_TOKEN="secret-token",
        SPORTMONKS_STUB="0",
        SPORTMONKS_AUTH_MODE="query",
    )

    calls = []
    sleep_calls: list[float] = []

    def fake_sleep(duration):  # pragma: no cover - patched for determinism
        sleep_calls.append(duration)

    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    def make_response(status_code, *, retry_after=None, data=None):
        headers = {"Retry-After": retry_after} if retry_after else {}
        payload = data or {"data": [{"id": 1}], "meta": {"pagination": {"total_pages": 1}}}
        prepared = requests.Request("GET", "https://api.test", params={}).prepare()
        return SimpleNamespace(
            status_code=status_code,
            url=prepared.url,
            text="{}",
            headers=headers,
            json=lambda: payload,
        )

    sequence = [
        make_response(429, retry_after="2"),
        make_response(200),
    ]

    def fake_get(url, params=None, headers=None, timeout=None):  # pragma: no cover - exercised via client
        calls.append((url, params, headers, timeout))
        return sequence[len(calls) - 1]

    monkeypatch.setattr(module.requests, "get", fake_get)

    client = module.SportMonksClient()
    fixtures = client.fixtures_by_date("2025-10-05")

    assert fixtures == [{"id": 1}]
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(2.0)
    assert len(calls) == 2

    # Exhaust retries
    sequence_fail = [make_response(429, retry_after="1") for _ in range(3)]
    calls.clear()
    sleep_calls.clear()

    def fake_get_fail(url, params=None, headers=None, timeout=None):  # pragma: no cover - exercised via client
        calls.append((url, params, headers, timeout))
        return sequence_fail[len(calls) - 1]

    monkeypatch.setattr(module.requests, "get", fake_get_fail)

    with pytest.raises(module.SportMonksRateLimitError):
        client.fixtures_by_date("2025-10-06")

    assert len(calls) == 3
    assert sleep_calls[0] == pytest.approx(1.0)
    assert sleep_calls[1] == pytest.approx(1.0)


__all__ = ["test_rate_limit_retry_and_failure"]
