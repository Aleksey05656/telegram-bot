"""
@file: test_sportmonks_client_v3.py
@description: Unit tests for the resilient SportMonks HTTP client and endpoint parsing.
@dependencies: pytest, anyio, sportmonks.client, sportmonks.endpoints
@created: 2025-09-23
"""
from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest


if "database" not in sys.modules:
    database_pkg = ModuleType("database")
    database_pkg.__path__ = []  # type: ignore[attr-defined]
    sys.modules["database"] = database_pkg

cache_module = ModuleType("database.cache_postgres")
cache_module.cache = None
cache_module.versioned_key = lambda prefix, *parts: ":".join(str(p) for p in (prefix, *parts))
sys.modules["database.cache_postgres"] = cache_module

from sportmonks.client import SportMonksClient
from sportmonks.endpoints import SportMonksEndpoints


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], headers: dict[str, str] | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = "{}"

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHTTPClient:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self._responses:
            raise AssertionError("No more fake responses configured")
        return self._responses.pop(0)

    async def aclose(self) -> None:  # pragma: no cover - compatibility stub
        return None


@pytest.mark.asyncio
async def test_paginate_follow_cursor() -> None:
    client = SportMonksClient(api_token="token", base_url="https://example.com")
    fake_http = _FakeHTTPClient(
        [
            _FakeResponse(200, {"data": [1, 2], "meta": {"pagination": {"next_page": "2"}}}),
            _FakeResponse(200, {"data": [3], "meta": {"pagination": {}}}),
        ]
    )
    client._client = fake_http  # type: ignore[assignment]
    items = []
    async for item in client.paginate("/fixtures", params={"foo": "bar"}, per_page=50):
        items.append(item)
    assert items == [1, 2, 3]
    assert len(fake_http.calls) == 2
    await client.close()


@pytest.mark.asyncio
async def test_request_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SportMonksClient(api_token="token", base_url="https://example.com", retry_attempts=2, backoff_base=0)
    fake_http = _FakeHTTPClient(
        [
            _FakeResponse(429, {"error": "rate"}, headers={"Retry-After": "0"}),
            _FakeResponse(200, {"data": {"id": 1}}),
        ]
    )
    client._client = fake_http  # type: ignore[assignment]

    async def fake_sleep(delay: float, *, base: float | None = None) -> None:  # pragma: no cover - deterministic
        return None

    monkeypatch.setattr(client, "_sleep", fake_sleep)
    data = await client.get_json("/fixtures/1")
    assert data == {"data": {"id": 1}}
    assert len(fake_http.calls) == 2
    await client.close()


@pytest.mark.asyncio
async def test_fixture_card_parses_lineups_and_xg() -> None:
    class _FakeClient:
        async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            assert path == "/fixtures/123"
            return {
                "data": {
                    "id": 123,
                    "league_id": 55,
                    "season_id": 2025,
                    "starting_at": "2025-09-26T16:30:00+00:00",
                    "status": "NS",
                    "participants": [
                        {"id": 1, "type": "team", "name": "Home FC", "meta": {"location": "home"}},
                        {"id": 2, "type": "team", "name": "Away FC", "meta": {"location": "away"}},
                    ],
                    "scores": [],
                    "statistics": [
                        {"team_id": 1, "stats": {"expected_goals": 1.8, "shots_on_target": 6}},
                        {"team_id": 2, "stats": {"expected_goals": 1.1, "shots_on_target": 3}},
                    ],
                    "lineups": [
                        {
                            "team_id": 1,
                            "details": [
                                {
                                    "player_id": 11,
                                    "position": "FW",
                                    "statistics": {"shots": {"total": 3}},
                                    "status": {"reason": "injury"},
                                }
                            ],
                        }
                    ],
                    "formations": [{"team_id": 1, "formation": "4-3-3"}],
                    "xGFixture": [
                        {"team_id": 1, "player_id": 11, "value": 0.52},
                        {"team_id": 2, "player_id": 21, "value": 0.27},
                    ],
                }
            }

    endpoints = SportMonksEndpoints(client=_FakeClient())
    fixture = await endpoints.fixture_card(123)
    assert fixture.home_team_id == 1
    assert fixture.away_team_id == 2
    assert fixture.lineups[0].xg == pytest.approx(0.52, rel=1)
    assert fixture.formations["1"] == "4-3-3"
    assert fixture.xg_fixture[0].value == 0.52
