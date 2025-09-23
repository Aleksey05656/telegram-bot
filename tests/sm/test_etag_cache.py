"""
@file: test_etag_cache.py
@description: Validate Sportmonks ETag caching behaviour.
@dependencies: pytest, httpx, sqlite3, json
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.data_providers.sportmonks.cache import SportmonksETagCache
from app.data_providers.sportmonks.client import SportmonksClient, SportmonksClientConfig
from app.data_providers.sportmonks.provider import SportmonksProvider
from app.data_providers.sportmonks.repository import SportmonksRepository


def _prepare_meta_db(db_path: Path) -> SportmonksRepository:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE sm_meta(
                key TEXT PRIMARY KEY,
                value_text TEXT
            )
            """
        )
    finally:
        conn.close()
    return SportmonksRepository(str(db_path))


@pytest.mark.asyncio
async def test_etag_cache_reuses_headers(tmp_path: Path) -> None:
    repo = _prepare_meta_db(tmp_path / "sm.sqlite")
    cache = SportmonksETagCache(repo, ttl_seconds=3600)

    recorded_headers: list[dict[str, str]] = []
    responses = [
        httpx.Response(
            200,
            json={"data": [json.loads(json.dumps({"id": 1}))]},
            headers={"ETag": "\"abc\"", "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"},
        ),
        httpx.Response(304, headers={"ETag": "\"abc\"", "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_headers.append(dict(request.headers))
        return responses.pop(0)

    transport = httpx.MockTransport(handler)
    config = SportmonksClientConfig(
        api_token="token",
        base_url="https://example.test",
        timeout=1.0,
        retry_attempts=0,
        backoff_base=0.0,
        rps_limit=5.0,
    )
    client = SportmonksClient(config, transport=transport)
    provider = SportmonksProvider(client, etag_cache=cache)

    try:
        fixtures = await provider.fetch_fixtures(
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert fixtures == []
        cached_entry = cache.load("/fixtures", {})
        assert cached_entry is not None
        assert cached_entry.etag == '"abc"'

        fixtures_second = await provider.fetch_fixtures(
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert fixtures_second == []
        assert cache.load("/fixtures", {}) is not None
    finally:
        await client.aclose()

    assert len(recorded_headers) == 2
    first_headers, second_headers = recorded_headers
    first_lower = {k.lower(): v for k, v in first_headers.items()}
    second_lower = {k.lower(): v for k, v in second_headers.items()}
    assert "if-none-match" not in first_lower
    assert second_lower.get("if-none-match") == '"abc"'
