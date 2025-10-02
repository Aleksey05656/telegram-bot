"""
/**
 * @file: sportmonks_client.py
 * @description: SportMonks football client with strict date handling and diagnostics.
 * @dependencies: requests, logger
 * @created: 2025-09-15
 */
"""
from __future__ import annotations

import datetime as _dt
import os
import time
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from logger import logger

BASE_URL = "https://api.sportmonks.com/v3/football"
TOKEN_ENV = "SPORTMONKS_API_TOKEN"
LEGACY_ENV = "SPORTMONKS_API_KEY"
INCLUDES_ENV = "SPORTMONKS_INCLUDES"
STUB_ENV = "SPORTMONKS_STUB"
AUTH_MODE_ENV = "SPORTMONKS_AUTH_MODE"
PER_PAGE_ENV = "SPORTMONKS_PER_PAGE"
TIMEZONE_ENV = "SPORTMONKS_TIMEZONE"

AUTH_MODE_QUERY = "query"
AUTH_MODE_HEADER = "header"

MAX_BETWEEN_RANGE_DAYS = 100
DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0
PER_PAGE_MIN = 1
PER_PAGE_MAX = 50


class SportMonksError(RuntimeError):
    """Base error for SportMonks integration issues."""


class SportMonksValidationError(SportMonksError, ValueError):
    """Raised when provided parameters do not satisfy API requirements."""


class SportMonksRateLimitError(SportMonksError):
    """Raised when SportMonks keeps returning HTTP 429 despite retries."""


def _bootstrap_token() -> None:
    if TOKEN_ENV in os.environ:
        return
    legacy = os.environ.get(LEGACY_ENV)
    if not legacy:
        return
    logger.warning(
        "SPORTMONKS_API_KEY is deprecated; please migrate to SPORTMONKS_API_TOKEN",
    )
    os.environ[TOKEN_ENV] = legacy


_bootstrap_token()


def _mask_secret(value: str) -> str:
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        return value
    return value.replace(token, "***")


def _should_stub() -> bool:
    if os.getenv(STUB_ENV, "0") == "1":
        return True
    token = os.environ.get(TOKEN_ENV, "").strip()
    return not token or token.lower() == "dummy"


def _coerce_date(value: _dt.date | str, *, field: str) -> str:
    if isinstance(value, _dt.date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        try:
            _dt.date.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - defensive branch
            raise SportMonksValidationError(
                f"{field} must be in YYYY-MM-DD format"
            ) from exc
        return value
    raise SportMonksValidationError(f"{field} must be a date or YYYY-MM-DD string")


def _parse_per_page(value: int | str | None) -> int | None:
    if value in (None, "", "0"):
        return None
    try:
        per_page = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise SportMonksValidationError("per_page must be an integer between 1 and 50") from exc
    if per_page < PER_PAGE_MIN or per_page > PER_PAGE_MAX:
        raise SportMonksValidationError("per_page must be between 1 and 50")
    return per_page


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.isdigit():
        return max(0.0, float(int(value)))
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):  # pragma: no cover - header parsing fallback
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    delta = (dt - now).total_seconds()
    return max(0.0, delta)


def _mask_url(url: str) -> str:
    return _mask_secret(url)


class SportMonksClient:
    """HTTP client for SportMonks football API with optional stub responses."""

    def __init__(
        self,
        *,
        stub: bool | None = None,
        includes: str | None = None,
        auth_mode: str | None = None,
        timezone: str | None = None,
        per_page: int | None = None,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._stub = _should_stub() if stub is None else bool(stub)
        self._includes = includes if includes is not None else os.getenv(INCLUDES_ENV)
        self._auth_mode = (auth_mode or os.getenv(AUTH_MODE_ENV, AUTH_MODE_QUERY)).strip().lower()
        if self._auth_mode not in {AUTH_MODE_QUERY, AUTH_MODE_HEADER}:
            raise SportMonksValidationError(
                "SPORTMONKS_AUTH_MODE must be either 'query' or 'header'"
            )
        self._timezone = timezone if timezone is not None else os.getenv(TIMEZONE_ENV)
        env_per_page = _parse_per_page(os.getenv(PER_PAGE_ENV)) if per_page is None else per_page
        self._per_page = _parse_per_page(env_per_page) if per_page is not None else env_per_page
        self._timeout = DEFAULT_TIMEOUT
        self._max_retries = max(1, max_retries)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def leagues(self) -> list[dict[str, Any]]:
        if self._stub:
            return [
                {"id": 1, "name": "Stub Premier League", "country": "GB"},
                {"id": 2, "name": "Stub La Liga", "country": "ES"},
            ]

        payload = self._request("/leagues", params=None)
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []

    def fixtures_by_date(
        self,
        date: _dt.date | str,
        include: str | None = None,
        *,
        timezone: str | None = None,
        per_page: int | None = None,
    ) -> list[dict[str, Any]]:
        date_iso = _coerce_date(date, field="date")
        if self._stub:
            return [
                {"id": 101, "home": "Stub FC", "away": "Mock United", "date": date_iso},
                {"id": 102, "home": "Sample City", "away": "Example Town", "date": date_iso},
            ]

        params: dict[str, str] = {}
        include_value = include or self._includes
        if include_value:
            params["include"] = include_value

        timezone_value = timezone if timezone is not None else self._timezone
        if timezone_value:
            params["timezone"] = timezone_value

        per_page_value = _parse_per_page(per_page) if per_page is not None else self._per_page
        return self._fetch_paginated(f"/fixtures/date/{date_iso}", params, per_page_value)

    def fixtures_between(
        self,
        start: _dt.date | str,
        end: _dt.date | str,
        include: str | None = None,
        *,
        per_page: int | None = None,
    ) -> list[dict[str, Any]]:
        start_iso = _coerce_date(start, field="start")
        end_iso = _coerce_date(end, field="end")
        self._validate_range(start_iso, end_iso)

        if self._stub:
            return self.fixtures_by_date(start_iso, include=include, per_page=per_page)

        params: dict[str, str] = {}
        include_value = include or self._includes
        if include_value:
            params["include"] = include_value

        per_page_value = _parse_per_page(per_page) if per_page is not None else self._per_page
        return self._fetch_paginated(
            f"/fixtures/between/{start_iso}/{end_iso}",
            params,
            per_page_value,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fetch_paginated(
        self,
        path: str,
        params: dict[str, str],
        per_page: int | None,
    ) -> list[dict[str, Any]]:
        page = 1
        items: list[dict[str, Any]] = []

        while True:
            page_params = dict(params)
            if per_page:
                page_params["per_page"] = str(per_page)
            page_params["page"] = str(page)
            payload = self._request(path, page_params)
            data = payload.get("data", []) if isinstance(payload, dict) else []
            if isinstance(data, list):
                items.extend(data)
            else:  # pragma: no cover - defensive fallback
                logger.debug("Unexpected SportMonks data payload", extra={"type": type(data).__name__})

            pagination = (
                (payload.get("meta") or {}).get("pagination")
                if isinstance(payload, dict)
                else None
            )
            total_pages = 1
            if isinstance(pagination, dict):
                total_pages = int(pagination.get("total_pages") or 1)
            if page >= total_pages:
                break
            page += 1

        return items

    def _validate_range(self, start_iso: str, end_iso: str) -> None:
        start_date = _dt.date.fromisoformat(start_iso)
        end_date = _dt.date.fromisoformat(end_iso)
        if end_date < start_date:
            raise SportMonksValidationError("end date must be greater than or equal to start date")
        if (end_date - start_date).days > MAX_BETWEEN_RANGE_DAYS:
            raise SportMonksValidationError("date range must not exceed 100 days")

    def _resolve_token(self) -> str:
        token = os.environ.get(TOKEN_ENV, "").strip()
        if not token:
            raise SportMonksValidationError("SPORTMONKS_API_TOKEN is required for live requests")
        return token

    def _request(self, path: str, params: dict[str, str] | None) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        params = dict(params or {})
        headers: dict[str, str] = {}

        token = None
        if not self._stub:
            token = self._resolve_token()
            if self._auth_mode == AUTH_MODE_HEADER:
                headers["Authorization"] = token
            else:
                params["api_token"] = token

        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers or None,
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:  # pragma: no cover - network failure
                masked_url = _mask_url(url)
                raise SportMonksError(f"SportMonks request failed for {masked_url}") from exc

            if response.status_code == 429:
                if attempt >= self._max_retries:
                    masked_url = _mask_url(response.url)
                    logger.warning(
                        "SportMonks rate limit exhausted at %s (masked)",
                        masked_url,
                    )
                    raise SportMonksRateLimitError("SportMonks rate limit exceeded")

                retry_after_header = response.headers.get("Retry-After")
                retry_after = _parse_retry_after(retry_after_header)
                backoff = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                sleep_for = min(retry_after or backoff, MAX_BACKOFF_SECONDS)
                masked_url = _mask_url(response.url)
                logger.info(
                    "SportMonks rate limited (429) at %s; retrying in %.1fs",
                    masked_url,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue

            if response.status_code >= 400:
                self._handle_http_error(response)

            try:
                return response.json()
            except ValueError as exc:  # pragma: no cover - unexpected body
                masked_url = _mask_url(response.url)
                raise SportMonksError(f"SportMonks returned invalid JSON for {masked_url}") from exc

    def _handle_http_error(self, response: requests.Response) -> None:
        masked_url = _mask_url(response.url)
        status = response.status_code
        snippet = response.text[:2000]

        if status == 400:
            message = "SportMonks request rejected (check date/include/timezone/per_page parameters)"
        elif status in {401, 403}:
            message = "SportMonks authentication failed (check API token or auth mode)"
        else:
            message = f"SportMonks HTTP error {status}"

        logger.error("%s at %s; body=%s", message, masked_url, snippet)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - propagate
            raise SportMonksError(message) from exc


__all__ = [
    "SportMonksClient",
    "SportMonksError",
    "SportMonksValidationError",
    "SportMonksRateLimitError",
]
