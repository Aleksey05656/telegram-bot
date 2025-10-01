"""
/**
 * @file: scripts/preflight_sportmonks.py
 * @description: Release preflight check for SportMonks football API connectivity.
 * @dependencies: requests
 * @created: 2025-10-01
 */
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_URL = "https://api.sportmonks.com/v3/football"
TOKEN_ENV = "SPORTMONKS_API_TOKEN"
LEGACY_ENV = "SPORTMONKS_API_KEY"


def _resolve_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        return token
    legacy = os.environ.get(LEGACY_ENV, "").strip()
    if legacy:
        print(
            "[sportmonks] warning: SPORTMONKS_API_KEY is deprecated; falling back to legacy token",
            flush=True,
        )
        return legacy
    raise RuntimeError("SPORTMONKS_API_TOKEN is required for SportMonks preflight")


def _mask(url: str, token: str) -> str:
    return url.replace(token, "***") if token else url


def main() -> int:
    token = _resolve_token()
    today = _dt.date.today().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures/date/{today}"
    response = requests.get(url, params={"api_token": token}, timeout=5)
    masked = _mask(response.url, token)
    snippet = response.text[:200]
    print(f"[sportmonks] url={masked}")
    print(f"[sportmonks] status={response.status_code}")
    print(f"[sportmonks] body={snippet}")
    response.raise_for_status()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
