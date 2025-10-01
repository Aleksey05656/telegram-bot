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
from typing import Any

import requests

from logger import logger

BASE_URL = "https://api.sportmonks.com/v3/football"
TOKEN_ENV = "SPORTMONKS_API_TOKEN"
LEGACY_ENV = "SPORTMONKS_API_KEY"
INCLUDES_ENV = "SPORTMONKS_INCLUDES"
STUB_ENV = "SPORTMONKS_STUB"


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


def _mask_token(value: str) -> str:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        return value
    return value.replace(token, "***")


def _should_stub() -> bool:
    if os.getenv(STUB_ENV, "0") == "1":
        return True
    token = os.environ.get(TOKEN_ENV, "").strip()
    return not token or token.lower() == "dummy"


def _get(url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    merged = {**(params or {}), "api_token": os.environ[TOKEN_ENV]}
    response = requests.get(url, params=merged, timeout=10)
    if response.status_code >= 400:
        masked_url = _mask_token(response.url)
        logger.error(
            "sportmonks HTTP %s at %s; body=%s",
            response.status_code,
            masked_url,
            response.text[:2000],
        )
        response.raise_for_status()
    return response.json()


class SportMonksClient:
    """HTTP client for SportMonks football API with optional stub responses."""

    def __init__(self, *, stub: bool | None = None, includes: str | None = None) -> None:
        self._stub = _should_stub() if stub is None else bool(stub)
        self._includes = includes if includes is not None else os.getenv(INCLUDES_ENV)

    def leagues(self) -> list[dict[str, Any]]:
        if self._stub:
            return [
                {"id": 1, "name": "Stub Premier League", "country": "GB"},
                {"id": 2, "name": "Stub La Liga", "country": "ES"},
            ]

        payload = _get(f"{BASE_URL}/leagues")
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []

    def fixtures_by_date(self, date_iso: str) -> list[dict[str, Any]]:
        _dt.date.fromisoformat(date_iso)
        if self._stub:
            return [
                {"id": 101, "home": "Stub FC", "away": "Mock United", "date": date_iso},
                {"id": 102, "home": "Sample City", "away": "Example Town", "date": date_iso},
            ]

        params: dict[str, str] = {}
        if self._includes:
            params["include"] = self._includes
        payload = _get(f"{BASE_URL}/fixtures/date/{date_iso}", params or None)
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []

    def fixtures_between(self, start_iso: str, end_iso: str) -> list[dict[str, Any]]:
        _dt.date.fromisoformat(start_iso)
        _dt.date.fromisoformat(end_iso)
        if self._stub:
            return self.fixtures_by_date(start_iso)

        payload = _get(f"{BASE_URL}/fixtures/between/{start_iso}/{end_iso}")
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []


__all__ = ["SportMonksClient"]
