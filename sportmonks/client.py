"""
@file: client.py
@description: Asynchronous SportMonks HTTP client with resilience helpers (retries, rate limits, singleflight).
@dependencies: asyncio, random, typing, httpx, config.get_settings
@created: 2025-09-23
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from config import get_settings
from logger import logger

_JSON = dict[str, Any]


class RequestError(RuntimeError):
    """Base exception for SportMonks client failures."""


class RateLimitError(RequestError):
    """Raised when retries are exhausted because of rate limiting."""


class ServerError(RequestError):
    """Raised when the API keeps returning server errors."""


@dataclass(frozen=True)
class _RequestKey:
    method: str
    url: str
    params: tuple[tuple[str, str], ...]


class _SingleFlight:
    """Ensure only one coroutine performs the same request at a time."""

    def __init__(self) -> None:
        self._inflight: dict[_RequestKey, asyncio.Future[_JSON]] = {}
        self._lock = asyncio.Lock()

    async def run(self, key: _RequestKey, func: Callable[[], "asyncio.Future[_JSON]"]):
        async with self._lock:
            existing = self._inflight.get(key)
            if existing is not None:
                return await asyncio.shield(existing)
            future = asyncio.ensure_future(func())
            self._inflight[key] = future
        try:
            return await asyncio.shield(future)
        finally:
            async with self._lock:
                self._inflight.pop(key, None)


class SportMonksClient:
    """HTTP client wrapper for SportMonks API."""

    def __init__(
        self,
        *,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        retry_attempts: int | None = None,
        backoff_base: float | None = None,
        jitter: float = 0.25,
        concurrency: int | None = None,
        use_header_auth: bool = False,
    ) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.SPORTMONKS_BASE_URL
        token = api_token or settings.SPORTMONKS_API_TOKEN or settings.SPORTMONKS_API_KEY
        if not token:
            raise ValueError("SportMonks API token is required")
        self._token = token
        self._timeout = timeout or settings.SPORTMONKS_TIMEOUT_SEC
        self._retry_attempts = retry_attempts or settings.SPORTMONKS_RETRY_ATTEMPTS
        self._backoff_base = backoff_base or settings.SPORTMONKS_BACKOFF_BASE
        self._jitter = jitter
        limit = concurrency or max(1, int(settings.SPORTMONKS_RPS_LIMIT))
        self._semaphore = asyncio.Semaphore(limit)
        self._use_header_auth = use_header_auth
        self._default_params = {
            "timezone": "Europe/Berlin",
            "locale": "ru",
        }
        self._singleflight = _SingleFlight()
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout, connect=self._timeout),
            headers={"Accept": "application/json"},
        )
        logger.info(
            "sportmonks_client_ready", extra={"base_url": self._base_url, "concurrency": limit}
        )

    async def close(self) -> None:
        await self._client.aclose()

    @asynccontextmanager
    async def limit(self) -> AsyncIterator[None]:
        async with self._semaphore:
            yield

    def _build_params(self, params: Mapping[str, Any] | None) -> dict[str, Any]:
        merged = dict(self._default_params)
        if params:
            for key, value in params.items():
                if value is not None:
                    merged[key] = value
        if not self._use_header_auth:
            merged.setdefault("api_token", self._token)
        return merged

    def _build_headers(self, headers: Mapping[str, str] | None) -> dict[str, str]:
        merged = {"Accept": "application/json"}
        if headers:
            merged.update(headers)
        if self._use_header_auth:
            merged.setdefault("Authorization", self._token)
        return merged

    async def _do_request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> _JSON:
        attempt = 0
        params_dict = self._build_params(params)
        headers_dict = self._build_headers(headers)
        request_key = _RequestKey(
            method=method.upper(),
            url=url,
            params=tuple(sorted((str(k), str(v)) for k, v in params_dict.items())),
        )

        async def _call() -> _JSON:
            nonlocal attempt
            while True:
                try:
                    async with self.limit():
                        response = await self._client.request(
                            method,
                            url,
                            params=params_dict,
                            headers=headers_dict,
                            **kwargs,
                        )
                except httpx.HTTPError as exc:  # pragma: no cover - transport-level errors
                    attempt += 1
                    if attempt > self._retry_attempts:
                        raise RequestError(str(exc)) from exc
                    await self._sleep(attempt)
                    continue

                if response.status_code == 429:
                    attempt += 1
                    if attempt > self._retry_attempts:
                        raise RateLimitError(f"Rate limit exceeded for {url}")
                    retry_after = self._retry_after_seconds(response)
                    await self._sleep(attempt, base=retry_after or self._backoff_base)
                    continue

                if response.status_code >= 500:
                    attempt += 1
                    if attempt > self._retry_attempts:
                        raise ServerError(f"Server error {response.status_code} for {url}")
                    await self._sleep(attempt)
                    continue

                if response.status_code >= 400:
                    detail = self._safe_json(response) or response.text
                    raise RequestError(f"HTTP {response.status_code}: {detail}")

                data = self._safe_json(response)
                if data is None:
                    raise RequestError("Unexpected empty response body")
                return data

        return await self._singleflight.run(request_key, _call)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After")
        if header is None:
            return None
        try:
            return float(header)
        except ValueError:
            return None

    @staticmethod
    def _safe_json(response: httpx.Response) -> _JSON | None:
        try:
            return response.json()
        except ValueError:  # pragma: no cover - defensive branch
            logger.error("sportmonks_json_error", extra={"body": response.text[:200]})
            return None

    async def _sleep(self, attempt: int, *, base: float | None = None) -> None:
        backoff = (base or self._backoff_base) * (2 ** (attempt - 1))
        wait = min(backoff, 30.0)
        jitter = random.random() * self._jitter
        await asyncio.sleep(wait + jitter)

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> _JSON:
        return await self._do_request("GET", path, params=params, headers=headers)

    async def paginate(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        per_page: int = 50,
        limit: int | None = None,
    ) -> AsyncIterator[_JSON]:
        page_params = dict(params or {})
        page_params["per_page"] = min(per_page, 50)
        fetched = 0
        cursor: str | None = None
        while True:
            if cursor:
                page_params["page"] = cursor
            payload = await self.get_json(path, params=page_params, headers=headers)
            data = payload.get("data")
            if data is None:
                break
            if isinstance(data, list):
                for item in data:
                    yield item
                    fetched += 1
                    if limit is not None and fetched >= limit:
                        return
            else:
                yield data
                fetched += 1
                if limit is not None and fetched >= limit:
                    return
            meta = payload.get("meta", {})
            pagination = meta.get("pagination", {}) if isinstance(meta, Mapping) else {}
            cursor = (
                pagination.get("next_page")
                or pagination.get("next")
                or pagination.get("next_cursor")
            )
            if not cursor:
                break

    async def chunked_between(
        self,
        path_template: str,
        *,
        start: str,
        end: str,
        chunk_days: int,
        params: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[_JSON]:
        from datetime import datetime, timedelta

        fmt = "%Y-%m-%d"
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        current = start_dt
        while current <= end_dt:
            chunk_end = min(current + timedelta(days=chunk_days - 1), end_dt)
            path = path_template.format(
                start=current.strftime(fmt), end=chunk_end.strftime(fmt)
            )
            async for item in self.paginate(path, params=params):
                yield item
            current = chunk_end + timedelta(days=1)

    async def healthcheck(self) -> dict[str, Any]:
        start_time = time.monotonic()
        payload = await self.get_json("/status")
        elapsed = time.monotonic() - start_time
        return {"status": payload.get("status", "unknown"), "latency": elapsed}
