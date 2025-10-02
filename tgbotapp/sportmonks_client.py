"""
/**
 * @file: sportmonks_client.py
 * @description: Asynchronous SportMonks football API client with strict date validation and rate-limit handling.
 * @dependencies: httpx, asyncio, logging
 * @created: 2025-09-07
 */
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Sequence, Union

import httpx

logger = logging.getLogger(__name__)


class SportMonksClient:
    """Asynchronous client for the SportMonks v3 Football API."""

    DEFAULT_BASE_URL = httpx.URL("https://api.sportmonks.com/v3/football")

    def __init__(
        self,
        api_token: str,
        *,
        base_url: str | httpx.URL | None = None,
        timeout: httpx.Timeout | float | None = None,
        max_retries: int = 3,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not api_token:
            raise ValueError("API token must be provided")
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")

        self._api_token = api_token
        self._masked_token = self._mask_token(api_token)
        self._max_retries = max_retries
        self._owns_client = client is None
        self._base_url = httpx.URL(str(base_url) if base_url else str(self.DEFAULT_BASE_URL))
        timeout_config = self._normalize_timeout(timeout)

        if self._owns_client:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_config)
        else:
            if client is None:
                raise ValueError("client must be provided when owns_client is False")
            self._client = client
            if timeout is not None:
                self._client.timeout = timeout_config
        logger.debug("Initialized SportMonksClient with base_url=%s, retries=%s", self._base_url, max_retries)

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> "SportMonksClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def fixtures_between(
        self,
        start: Union[str, date, datetime],
        end: Union[str, date, datetime],
        *,
        includes: Optional[Sequence[str]] = None,
        timezone: Optional[str] = None,
        per_page: int = 50,
    ) -> dict:
        """Fetch fixtures between two dates (inclusive).

        Args:
            start: Start date in YYYY-MM-DD format or date/datetime object.
            end: End date in YYYY-MM-DD format or date/datetime object.
            includes: Optional sequence of include strings.
            timezone: Optional timezone identifier accepted by SportMonks.
            per_page: Pagination size, defaults to 50.

        Returns:
            Parsed JSON payload from the SportMonks API.

        Raises:
            ValueError: If dates are invalid or range exceeds 100 days.
            httpx.HTTPError: For network-related issues.
            httpx.HTTPStatusError: If the API returns an error status other than 429 retries.
        """

        start_date = self._parse_date(start, "start")
        end_date = self._parse_date(end, "end")

        if end_date < start_date:
            raise ValueError("end date must not be earlier than start date")

        if (end_date - start_date).days > 100:
            raise ValueError("date range must not exceed 100 days")

        if per_page <= 0:
            raise ValueError("per_page must be positive")

        path = f"/fixtures/between/{start_date.isoformat()}/{end_date.isoformat()}"
        params = {
            "api_token": self._api_token,
            "per_page": per_page,
        }

        if includes:
            params["include"] = self._format_includes(includes)
        if timezone:
            params["timezone"] = timezone

        logger.debug(
            "Requesting fixtures between %s and %s with includes=%s timezone=%s per_page=%s using token=%s",
            start_date,
            end_date,
            params.get("include"),
            timezone,
            per_page,
            self._masked_token,
        )

        response = await self._request("GET", path, params=params)
        return response.json()

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None) -> httpx.Response:
        assert self._client is not None

        for attempt in range(1, self._max_retries + 1):
            url = self._prepare_url(path)
            response = await self._client.request(method, url, params=params)

            if response.status_code != 429:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    logger.exception("SportMonks API error: %s", response.text)
                    raise
                return response

            retry_delay = self._parse_retry_after(response)
            if attempt == self._max_retries:
                logger.error(
                    "Exceeded max retries for SportMonks API after HTTP 429. token=%s", self._masked_token
                )
                response.raise_for_status()

            logger.warning(
                "Received HTTP 429 from SportMonks. Waiting %s seconds before retry %s/%s. token=%s",
                retry_delay,
                attempt,
                self._max_retries,
                self._masked_token,
            )
            await asyncio.sleep(retry_delay)

        raise RuntimeError("Unreachable code path in SportMonksClient._request")

    def _prepare_url(self, path: str) -> httpx.URL:
        url = httpx.URL(path)
        if url.is_relative_url:
            return self._base_url.join(url)
        return url

    @staticmethod
    def _normalize_timeout(timeout: httpx.Timeout | float | None) -> httpx.Timeout:
        if timeout is None:
            return httpx.Timeout(10.0, connect=5.0)
        if isinstance(timeout, httpx.Timeout):
            return timeout
        return httpx.Timeout(timeout)

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        header_value = response.headers.get("Retry-After")
        if not header_value:
            return 1.0

        try:
            return float(header_value)
        except ValueError:
            try:
                parsed_date = parsedate_to_datetime(header_value)
            except (TypeError, ValueError):
                return 1.0
            if parsed_date is None:
                return 1.0
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            current = datetime.now(timezone.utc)
            retry_after = (parsed_date - current).total_seconds()
            return max(retry_after, 0.0)

    @staticmethod
    def _parse_date(value: Union[str, date, datetime], field_name: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{field_name} must be in YYYY-MM-DD format") from exc
            return parsed
        raise TypeError(f"{field_name} must be a date, datetime, or YYYY-MM-DD string")

    @staticmethod
    def _format_includes(includes: Sequence[str]) -> str:
        filtered = [item.strip() for item in includes if item and item.strip()]
        if not filtered:
            raise ValueError("includes must contain at least one non-empty string when provided")
        return ",".join(dict.fromkeys(filtered))

    @staticmethod
    def _mask_token(token: str) -> str:
        if len(token) <= 6:
            return token[0] + "***"
        return f"{token[:3]}***{token[-2:]}"
