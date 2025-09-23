"""
@file: test_retry_rps.py
@description: Ensure Sportmonks client retries with backoff and respects rate limits.
@dependencies: pytest, httpx, asyncio
"""

from __future__ import annotations

import asyncio
from collections import deque

import httpx
import pytest

from app.data_providers.sportmonks.client import SportmonksClient, SportmonksClientConfig
from app.data_providers.sportmonks.metrics import sm_ratelimit_sleep_seconds_total, sm_requests_total


@pytest.mark.asyncio
async def test_retry_backoff_records_status_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(duration: float) -> None:  # pragma: no cover - patched in tests
        sleeps.append(duration)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr("app.data_providers.sportmonks.client.random.uniform", lambda _a, _b: 0.05)

    responses = deque([
        httpx.Response(429, json={"error": "rate"}),
        httpx.Response(500, json={"error": "server"}),
        httpx.Response(200, json={"data": []}),
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.popleft()

    sm_requests_total.clear()
    sm_ratelimit_sleep_seconds_total._value.set(0)

    transport = httpx.MockTransport(handler)
    config = SportmonksClientConfig(
        api_token="token",
        base_url="https://example.test",
        timeout=1.0,
        retry_attempts=3,
        backoff_base=0.1,
        rps_limit=10.0,
    )
    client = SportmonksClient(config, transport=transport)
    try:
        response = await client.get("/fixtures")
    finally:
        await client.aclose()

    assert response.status_code == 200
    assert sleeps == pytest.approx([0.15000000000000002, 0.25], rel=1e-6)

    ok_metric = sm_requests_total.labels(endpoint="/fixtures", status="200")._value.get()
    rate_metric = sm_requests_total.labels(endpoint="/fixtures", status="429")._value.get()
    err_metric = sm_requests_total.labels(endpoint="/fixtures", status="500")._value.get()
    assert ok_metric == 1
    assert rate_metric == 1
    assert err_metric == 1
    assert sm_ratelimit_sleep_seconds_total._value.get() == 0


@pytest.mark.asyncio
async def test_rate_limiter_updates_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(duration: float) -> None:  # pragma: no cover - patched in tests
        sleeps.append(duration)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    sm_ratelimit_sleep_seconds_total._value.set(0)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    config = SportmonksClientConfig(
        api_token="token",
        base_url="https://example.test",
        timeout=1.0,
        retry_attempts=0,
        backoff_base=0.0,
        rps_limit=1.0,
    )
    client = SportmonksClient(config, transport=transport)
    try:
        await client.get("/fixtures")
        await client.get("/fixtures")
    finally:
        await client.aclose()

    assert sleeps, "rate limiter should invoke sleep"
    assert sm_ratelimit_sleep_seconds_total._value.get() == pytest.approx(sum(sleeps))
