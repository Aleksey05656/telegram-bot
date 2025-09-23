"""
@file: test_provider_normalization.py
@description: Ensure Sportmonks provider normalizes payloads into DTOs.
@dependencies: pytest, httpx, json, pathlib
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.data_providers.sportmonks.client import SportmonksClient, SportmonksClientConfig
from app.data_providers.sportmonks.provider import SportmonksProvider

FIXTURES_PATH = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.asyncio
async def test_provider_fetches_and_normalizes(tmp_path: Path) -> None:
    fixtures_payload = json.loads((FIXTURES_PATH / "sm_fixtures_sample.json").read_text())
    teams_payload = json.loads((FIXTURES_PATH / "sm_teams_sample.json").read_text())
    standings_payload = json.loads((FIXTURES_PATH / "sm_standings_sample.json").read_text())
    injuries_payload = json.loads((FIXTURES_PATH / "sm_injuries_sample.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fixtures"):
            return httpx.Response(200, json=fixtures_payload)
        if request.url.path.endswith("/teams"):
            return httpx.Response(200, json=teams_payload)
        if "standings" in request.url.path:
            return httpx.Response(200, json=standings_payload)
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
        rps_limit=10.0,
    )
    client = SportmonksClient(config, transport=transport)
    provider = SportmonksProvider(client)
    try:
        fixtures = await provider.fetch_fixtures(
            datetime(2024, 5, 1, tzinfo=UTC),
            datetime(2024, 5, 2, tzinfo=UTC),
        )
        assert fixtures and fixtures[0].fixture_id == 101
        assert fixtures[0].home_team_id == 501

        teams = await provider.fetch_teams("8")
        assert {team.team_id for team in teams} == {501, 502}

        standings = await provider.fetch_standings("8", "2024")
        assert len(standings) == 2
        assert standings[0].points == 78

        injuries = await provider.fetch_injuries(
            datetime(2024, 5, 1, tzinfo=UTC),
            datetime(2024, 5, 2, tzinfo=UTC),
        )
        assert injuries and injuries[0].player_name == "John Doe"
    finally:
        await client.aclose()
