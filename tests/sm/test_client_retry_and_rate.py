"""
@file: test_client_retry_and_rate.py
@description: Validate Sportmonks client retry logic and rate limiter behaviour.
@dependencies: pytest, httpx, asyncio
"""

from __future__ import annotations

import asyncio
import httpx
import pytest

from app.data_providers.sportmonks.client import SportmonksClient, SportmonksClientConfig


@pytest.mark.asyncio
async def test_client_retries_on_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def fake_sleep(duration: float) -> None:  # pragma: no cover - timing hook
        calls.append(int(round(duration * 1000)))

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        if len(calls) == 0:
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(200, json={"data": ["ok"]})

    transport = httpx.MockTransport(handler)
    config = SportmonksClientConfig(
        api_token="token",
        base_url="https://example.test",
        timeout=1.0,
        retry_attempts=2,
        backoff_base=0.01,
        rps_limit=10.0,
    )
    client = SportmonksClient(config, transport=transport)
    try:
        response = await client.get("/fixtures")
    finally:
        await client.aclose()
    assert response.status_code == 200
    assert calls, "sleep should be called for retry backoff"


@pytest.mark.asyncio
async def test_rate_limiter_waits_between_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(duration: float) -> None:  # pragma: no cover - timing hook
        sleeps.append(duration)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    responses = iter(
        [
            httpx.Response(200, json={"data": []}),
            httpx.Response(200, json={"data": []}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

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
    assert sleeps, "rate limiter should sleep between calls"
