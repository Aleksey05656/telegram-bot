"""
@file: test_etag_cache.py
@description: Validate Sportmonks ETag caching behaviour.
@dependencies: pytest, httpx, sqlite3, json, datetime
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
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
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 2, tzinfo=UTC)
        fixtures = await provider.fetch_fixtures(start, end)
        assert fixtures == []
        params = {
            "include": "league;season;participants",
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
        }
        cached_entry = cache.load("/fixtures", params)
        assert cached_entry is not None
        assert cached_entry.etag == '"abc"'

        fixtures_second = await provider.fetch_fixtures(start, end)
        assert fixtures_second == []
        assert cache.load("/fixtures", params) is not None
    finally:
        await client.aclose()

    assert len(recorded_headers) == 2
    first_headers, second_headers = recorded_headers
    first_lower = {k.lower(): v for k, v in first_headers.items()}
    second_lower = {k.lower(): v for k, v in second_headers.items()}
    assert "if-none-match" not in first_lower
    assert second_lower.get("if-none-match") == '"abc"'


def test_etag_cache_key_canonicalization(tmp_path: Path) -> None:
    repo = _prepare_meta_db(tmp_path / "sm.sqlite")
    cache = SportmonksETagCache(repo, ttl_seconds=3600)

    cache.store(
        "/fixtures",
        {"from": "2025-01-01", "noise": "x"},
        etag='"abc"',
        last_modified=None,
    )

    same_key_entry = cache.load("/fixtures", {"from": "2025-01-01", "noise": "y"})
    assert same_key_entry is not None

    missing_allowed_entry = cache.load("/fixtures", None)
    assert missing_allowed_entry is None

    different_param_entry = cache.load("/fixtures", {"from": "2025-01-02"})
    assert different_param_entry is None

    cache.store(
        "/fixtures",
        None,
        etag='"post"',
        last_modified=None,
        method="POST",
    )

    assert cache.load("/fixtures", None, method="POST") is not None
    assert cache.load("/fixtures", None, method="DELETE") is None


def test_etag_cache_touch_keeps_original_timestamp(tmp_path: Path) -> None:
    repo = _prepare_meta_db(tmp_path / "sm.sqlite")
    cache = SportmonksETagCache(repo, ttl_seconds=60)

    cache.store(
        "/injuries",
        {"from": "2025-01-01"},
        etag='"inj"',
        last_modified="Wed, 01 Jan 2025 00:00:00 GMT",
    )

    entry = cache.load("/injuries", {"from": "2025-01-01"})
    assert entry is not None

    entry.stored_at = entry.stored_at - timedelta(minutes=10)

    cache.touch(
        "/injuries",
        {"from": "2025-01-01"},
        entry,
        etag='"inj"',
        last_modified="Wed, 01 Jan 2025 00:00:00 GMT",
    )

    assert cache.load("/injuries", {"from": "2025-01-01"}) is None
