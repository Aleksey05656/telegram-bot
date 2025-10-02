"""
/**
 * @file: scripts/preflight_sportmonks.py
 * @description: Release preflight check for SportMonks football API connectivity.
 * @dependencies: requests
 * @created: 2025-10-01
 */
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tgbotapp.sportmonks_client import SportMonksClient as SportMonks  # noqa: E402

TOKEN_ENV = "SPORTMONKS_API_TOKEN"


def _mask_token(token: str | None) -> str:
    if not token:
        return "<missing>"
    masked_source = token.strip()
    if not masked_source:
        return "<missing>"
    prefix = masked_source[:4]
    return f"{prefix}***"


def _extract_fixtures_count(payload: Any) -> int:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return len(data)
    if isinstance(payload, list):
        return len(payload)
    return 0


async def _fetch_fixtures_today(token: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    async with SportMonks(api_token=token) as client:
        payload = await client.fixtures_between(
            today,
            today,
            timezone="UTC",
            per_page=25,
        )
    return _extract_fixtures_count(payload)


def main() -> int:
    token = os.getenv(TOKEN_ENV, "").strip()
    if not token:
        print(
            "[ERROR] SPORTMONKS_API_TOKEN is not set. Provide a valid token to query SportMonks.",
            file=sys.stderr,
        )
        return 1

    try:
        fixtures_today = asyncio.run(_fetch_fixtures_today(token))
    except ValueError as exc:
        print(f"[ERROR] SportMonks validation error: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"[ERROR] SportMonks request failed with HTTP status {status}.", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(
            f"[ERROR] SportMonks network error: {exc.__class__.__name__}.",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001 - fail fast without exposing sensitive data
        print(
            f"[ERROR] SportMonks preflight failed unexpectedly: {exc.__class__.__name__}.",
            file=sys.stderr,
        )
        return 3

    masked_token = _mask_token(token)
    print(f"[OK] SportMonks token={masked_token}, fixtures_today={fixtures_today}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
