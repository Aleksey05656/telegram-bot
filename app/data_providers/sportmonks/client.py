"""
@file: client.py
@description: Asynchronous Sportmonks HTTP client with retry, rate limiting and conditional caching support.
@dependencies: asyncio, dataclasses, httpx, random, time
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import httpx

from .metrics import sm_ratelimit_sleep_seconds_total, sm_requests_total


class SportmonksClientError(RuntimeError):
    """Base error for Sportmonks client failures."""


class SportmonksRetryError(SportmonksClientError):
    """Raised when the client exhausts retry attempts."""


@dataclass(slots=True)
class SportmonksClientConfig:
    """Runtime configuration for Sportmonks HTTP client."""

    api_token: str
    base_url: str = "https://api.sportmonks.com/v3/football"
    timeout: float = 10.0
    retry_attempts: int = 4
    backoff_base: float = 0.5
    rps_limit: float = 3.0
    default_timewindow_days: int = 7
    leagues_allowlist: tuple[str, ...] = ()
    cache_ttl_seconds: int = 900

    @classmethod
    def from_env(cls) -> "SportmonksClientConfig":
        """Build configuration from environment variables with sane defaults."""

        token = os.getenv("SPORTMONKS_API_TOKEN") or os.getenv("SPORTMONKS_API_KEY", "")
        base_url = os.getenv("SPORTMONKS_BASE_URL", cls.base_url)
        timeout = float(os.getenv("SPORTMONKS_TIMEOUT_SEC", cls.timeout) or cls.timeout)
        retry_attempts = int(os.getenv("SPORTMONKS_RETRY_ATTEMPTS", cls.retry_attempts) or cls.retry_attempts)
        backoff_base = float(os.getenv("SPORTMONKS_BACKOFF_BASE", cls.backoff_base) or cls.backoff_base)
        rps_limit = float(os.getenv("SPORTMONKS_RPS_LIMIT", cls.rps_limit) or cls.rps_limit)
        default_window = int(
            os.getenv("SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS", cls.default_timewindow_days)
            or cls.default_timewindow_days
        )
        allowlist_raw = os.getenv("SPORTMONKS_LEAGUES_ALLOWLIST", "")
        allowlist: tuple[str, ...]
        if allowlist_raw.strip():
            allowlist = tuple(
                item.strip()
                for item in allowlist_raw.split(",")
                if item.strip()
            )
        else:
            allowlist = ()
        cache_ttl = int(os.getenv("SPORTMONKS_CACHE_TTL_SEC", cls.cache_ttl_seconds) or cls.cache_ttl_seconds)
        return cls(
            api_token=token,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            retry_attempts=max(0, retry_attempts),
            backoff_base=max(backoff_base, 0.0),
            rps_limit=max(rps_limit, 0.1),
            default_timewindow_days=max(default_window, 0),
            leagues_allowlist=allowlist,
            cache_ttl_seconds=max(cache_ttl, 0),
        )


@dataclass(slots=True)
class SportmonksResponse:
    """Normalized response container carrying metadata."""

    status_code: int
    data: Any | None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


class _TokenBucket:
    """Asynchronous token bucket enforcing RPS limit for the API."""

    def __init__(self, rate: float) -> None:
        self._capacity = max(rate, 1.0)
        self._rate = max(rate, 0.1)
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        async with self._lock:
            await self._refill_locked()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            wait_time = (1.0 - self._tokens) / self._rate
        await asyncio.sleep(wait_time)
        async with self._lock:
            await self._refill_locked()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return wait_time
            # As a fallback ensure we always wait at least a tiny bit
            self._tokens = max(self._tokens - 1.0, 0.0)
            return wait_time

    async def _refill_locked(self) -> None:
        now = time.monotonic()
        delta = now - self._updated
        if delta <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + delta * self._rate)
        self._updated = now


class SportmonksClient:
    """HTTP client for Sportmonks API with built-in retry and rate limit controls."""

    def __init__(
        self,
        config: SportmonksClientConfig | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config or SportmonksClientConfig.from_env()
        self._bucket = _TokenBucket(self._config.rps_limit)
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(self._config.timeout),
            transport=transport,
        )

    @property
    def config(self) -> SportmonksClientConfig:
        """Return configuration used by the client."""

        return self._config

    async def aclose(self) -> None:
        """Close underlying HTTP client."""

        await self._client.aclose()

    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> SportmonksResponse:
        """Perform GET request with retry and conditional headers."""

        headers = {
            "Authorization": f"Bearer {self._config.api_token}",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        attempt = 0
        while True:
            slept = await self._bucket.acquire()
            if slept:
                sm_ratelimit_sleep_seconds_total.inc(slept)
            try:
                response = await self._client.get(endpoint, params=params, headers=headers)
            except httpx.TimeoutException as exc:  # pragma: no cover - network failure path
                if attempt >= self._config.retry_attempts:
                    raise SportmonksRetryError("Sportmonks request timed out") from exc
                await asyncio.sleep(self._sleep_for_retry(attempt))
                attempt += 1
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                sm_requests_total.labels(endpoint=endpoint, status=str(response.status_code)).inc()
                if attempt >= self._config.retry_attempts:
                    raise SportmonksRetryError(
                        f"Sportmonks request failed after retries: {response.status_code}"
                    )
                await asyncio.sleep(self._sleep_for_retry(attempt))
                attempt += 1
                continue

            if response.status_code == 304:
                sm_requests_total.labels(endpoint=endpoint, status="304").inc()
                return SportmonksResponse(
                    status_code=response.status_code,
                    data=None,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                    not_modified=True,
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                sm_requests_total.labels(endpoint=endpoint, status=str(response.status_code)).inc()
                raise SportmonksClientError(str(exc)) from exc

            payload: Any
            if response.headers.get("Content-Type", "").startswith("application/json"):
                payload = response.json()
            else:
                payload = response.text

            sm_requests_total.labels(endpoint=endpoint, status=str(response.status_code)).inc()
            return SportmonksResponse(
                status_code=response.status_code,
                data=payload,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                not_modified=False,
            )

    def _sleep_for_retry(self, attempt: int) -> float:
        base = max(self._config.backoff_base, 0.0)
        exponent = 2 ** attempt
        jitter = random.uniform(0.0, base)
        return base * exponent + jitter


def utc_now() -> datetime:
    """Helper for generating timezone-aware timestamps (for tests)."""

    return datetime.now(tz=timezone.utc)
