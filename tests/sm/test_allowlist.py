"""
@file: test_allowlist.py
@description: Ensure Sportmonks provider enforces league allowlist filtering.
@dependencies: pytest, json, httpx, pathlib
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.data_providers.sportmonks.client import SportmonksClient, SportmonksClientConfig
from app.data_providers.sportmonks.provider import SportmonksProvider

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sm"


@pytest.mark.asyncio
async def test_allowlist_filters_payload() -> None:
    fixtures_payload = json.loads((FIXTURES_DIR / "fixtures.json").read_text(encoding="utf-8"))
    injuries_payload = json.loads((FIXTURES_DIR / "injuries.json").read_text(encoding="utf-8"))

    recorded_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_params.append(dict(request.url.params))
        if request.url.path.endswith("/fixtures"):
            return httpx.Response(200, json=fixtures_payload)
        if request.url.path.endswith("/injuries"):
            return httpx.Response(200, json=injuries_payload)
        raise AssertionError(f"unexpected path {request.url}")

    transport = httpx.MockTransport(handler)
    config = SportmonksClientConfig(
        api_token="token",
        base_url="https://example.test",
        timeout=1.0,
        retry_attempts=0,
        backoff_base=0.0,
        rps_limit=5.0,
        default_timewindow_days=1,
        leagues_allowlist=("8",),
    )
    client = SportmonksClient(config, transport=transport)
    provider = SportmonksProvider(client)

    try:
        fixtures = await provider.fetch_fixtures(
            datetime(2025, 2, 14, tzinfo=UTC),
            datetime(2025, 2, 16, tzinfo=UTC),
        )
        injuries = await provider.fetch_injuries(
            datetime(2025, 2, 14, tzinfo=UTC),
            datetime(2025, 2, 16, tzinfo=UTC),
        )
    finally:
        await client.aclose()

    assert {fixture.league_id for fixture in fixtures} == {8}
    assert all(injury.league_id == 8 for injury in injuries)
    assert recorded_params[0].get("league_ids") == "8"
    assert recorded_params[1].get("league_ids") == "8"
