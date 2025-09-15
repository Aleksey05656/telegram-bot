"""
@file: sportmonks_client.py
@description: SportMonks client with optional stub mode for testing
@dependencies: requests (real mode)
@created: 2025-09-15
SportMonks client with STUB mode.
- Если переменная окружения SPORTMONKS_STUB=1 или SPORTMONKS_API_KEY пустой/равен "dummy",
  используется заглушка без реальных сетевых вызовов.
- Это позволяет запускать тесты и сервис локально без реального API-ключа.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class SportMonksConfig:
    api_key: str | None
    stub: bool
    base_url: str = "https://api.sportmonks.com/v3"

    @classmethod
    def from_env(cls) -> SportMonksConfig:
        key = os.getenv("SPORTMONKS_API_KEY")
        stub_flag = os.getenv("SPORTMONKS_STUB", "0") == "1" or not key or key.lower() == "dummy"
        return cls(api_key=key, stub=stub_flag)


class SportMonksClient:
    def __init__(self, cfg: SportMonksConfig | None = None):
        self.cfg = cfg or SportMonksConfig.from_env()

    def leagues(self) -> list[dict[str, Any]]:
        if self.cfg.stub:
            return [
                {"id": 1, "name": "Stub Premier League", "country": "GB"},
                {"id": 2, "name": "Stub La Liga", "country": "ES"},
            ]
        return _real_leagues(self.cfg)

    def fixtures_by_date(self, date_iso: str) -> list[dict[str, Any]]:
        if self.cfg.stub:
            return [
                {"id": 101, "home": "Stub FC", "away": "Mock United", "date": date_iso},
                {"id": 102, "home": "Sample City", "away": "Example Town", "date": date_iso},
            ]
        return _real_fixtures_by_date(self.cfg, date_iso)


def _require_requests():
    try:
        import requests  # type: ignore

        return requests
    except Exception as e:  # pragma: no cover - defensive
        raise RuntimeError("requests library required for real SportMonks calls") from e


def _real_headers(cfg: SportMonksConfig) -> dict[str, str]:
    if not cfg.api_key or cfg.api_key.lower() == "dummy":
        raise RuntimeError("SPORTMONKS_API_KEY missing. Enable stub or set real key.")
    return {"Authorization": f"Bearer {cfg.api_key}"}


def _real_leagues(cfg: SportMonksConfig) -> list[dict[str, Any]]:
    requests = _require_requests()
    url = f"{cfg.base_url}/football/leagues"
    r = requests.get(url, headers=_real_headers(cfg), timeout=10)
    r.raise_for_status()
    return r.json().get("data", [])


def _real_fixtures_by_date(cfg: SportMonksConfig, date_iso: str) -> list[dict[str, Any]]:
    requests = _require_requests()
    url = f"{cfg.base_url}/football/fixtures/date/{date_iso}"
    r = requests.get(url, headers=_real_headers(cfg), timeout=10)
    r.raise_for_status()
    return r.json().get("data", [])
