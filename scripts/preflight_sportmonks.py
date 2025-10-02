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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.sportmonks_client import (  # noqa: E402 - runtime import
    AUTH_MODE_ENV,
    PER_PAGE_ENV,
    TIMEZONE_ENV,
    SportMonksClient,
    SportMonksError,
    SportMonksValidationError,
)

TOKEN_ENV = "SPORTMONKS_API_TOKEN"
LEGACY_ENV = "SPORTMONKS_API_KEY"


def _mask_token(token: str | None) -> str:
    if not token:
        return "<missing>"
    token = token.strip()
    if len(token) <= 4:
        return "***"
    return f"{token[:2]}***{token[-2:]}"


def _resolve_token() -> str | None:
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
    return None


def _print_config(token: str | None) -> None:
    auth_mode = os.getenv(AUTH_MODE_ENV, "query").strip() or "query"
    timezone = os.getenv(TIMEZONE_ENV) or "<default>"
    per_page = os.getenv(PER_PAGE_ENV) or "<default>"
    print(f"[sportmonks] auth_mode={auth_mode}")
    print(f"[sportmonks] token={_mask_token(token)}")
    print(f"[sportmonks] timezone={timezone}")
    print(f"[sportmonks] per_page={per_page}")


def main() -> int:
    token = _resolve_token()
    _print_config(token)

    if not token:
        print("[sportmonks] error: SPORTMONKS_API_TOKEN is required", file=sys.stderr)
        return 1

    client = SportMonksClient()
    today = _dt.datetime.now(tz=_dt.timezone.utc).date()

    try:
        fixtures = client.fixtures_by_date(today)
    except SportMonksValidationError as exc:
        print(f"[sportmonks] validation error: {exc}", file=sys.stderr)
        return 1
    except SportMonksError as exc:
        print(f"[sportmonks] request failed: {exc}", file=sys.stderr)
        return 2

    count = len(fixtures)
    sample_ids = [str(item.get("id")) for item in fixtures[:5]]
    print(
        f"[sportmonks] fetched {count} fixtures for {today.strftime('%Y-%m-%d')}"
        + (f"; sample ids={', '.join(sample_ids)}" if sample_ids else ""),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
