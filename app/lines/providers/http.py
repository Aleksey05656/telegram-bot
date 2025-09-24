"""
@file: app/lines/providers/http.py
@description: Async HTTP odds provider with retries, token bucket throttling and ETag support.
@dependencies: asyncio, httpx, app.lines.mapper
@created: 2025-09-24
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Mapping, Sequence

import httpx

from app.lines.mapper import LinesMapper

from .base import OddsSnapshot


@dataclass(slots=True)
class HTTPLinesProvider:
    """Fetch odds snapshots from an HTTP API with resilience primitives."""

    base_url: str
    token: str | None = None
    headers: Mapping[str, str] | None = None
    timeout: float = 8.0
    retry_attempts: int = 4
    backoff_base: float = 0.4
    rps_limit: float = 3.0
    mapper: LinesMapper = field(default_factory=LinesMapper)
    _client: httpx.AsyncClient | None = field(default=None, init=False)
    _last_request_ts: float = field(default=0.0, init=False)
    _etag_cache: dict[str, tuple[str, list[dict[str, Any]]]] = field(
        default_factory=dict, init=False
    )

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[OddsSnapshot]:
        params = {
            "date_from": date_from.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "date_to": date_to.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }
        if leagues:
            params["leagues"] = ",".join(leagues)
        raw_rows = await self._request(self.base_url, params=params)
        snapshots: list[OddsSnapshot] = []
        for row in raw_rows:
            normalized = self.mapper.normalize_row(row)
            price = float(normalized.get("price_decimal"))
            market = str(normalized.get("market") or "").strip()
            selection = str(normalized.get("selection") or "").strip()
            if not market or not selection:
                continue
            snapshots.append(
                OddsSnapshot(
                    provider=str(normalized.get("provider") or "http"),
                    pulled_at=_parse_dt(normalized.get("pulled_at")),
                    match_key=str(normalized.get("match_key")),
                    league=str(normalized.get("league")) if normalized.get("league") else None,
                    kickoff_utc=_parse_dt(normalized.get("kickoff_utc")),
                    market=market,
                    selection=selection,
                    price_decimal=price,
                    extra={"source": "http"},
                )
            )
        snapshots.sort(key=lambda item: (item.match_key, item.market, item.selection))
        return snapshots

    async def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        etag_header: dict[str, str] = {}
        cache_entry = self._etag_cache.get(url)
        if cache_entry:
            etag_header["If-None-Match"] = cache_entry[0]
        headers = dict(self.headers or {})
        headers.update(etag_header)
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        attempt = 0
        while True:
            await self._respect_rate_limit()
            try:
                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                if attempt >= self.retry_attempts:
                    raise
                await asyncio.sleep(self.backoff_base * (2**attempt))
                attempt += 1
                continue
            if response.status_code == httpx.codes.NOT_MODIFIED and cache_entry:
                return cache_entry[1]
            if response.status_code >= 500 and attempt < self.retry_attempts:
                await asyncio.sleep(self.backoff_base * (2**attempt))
                attempt += 1
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("HTTP odds provider must return list of dicts")
            etag = response.headers.get("ETag")
            if etag:
                self._etag_cache[url] = (etag, data)
            return data

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "HTTPLinesProvider":
        await self._ensure_client()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def _respect_rate_limit(self) -> None:
        if self.rps_limit <= 0:
            return
        interval = 1.0 / self.rps_limit
        now = monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)
        self._last_request_ts = monotonic()


def _parse_dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if raw is None:
        raise ValueError("Timestamp is required")
    text = str(raw).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


__all__ = ["HTTPLinesProvider"]
