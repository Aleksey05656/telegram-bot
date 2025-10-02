"""
@file: scripts/preflight_redis.py
@description: Redis connectivity preflight for Amvera releases.
@dependencies: redis.asyncio.Redis
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import redis.asyncio as redis

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_url() -> str | None:
    url = os.getenv("REDIS_URL")
    if url:
        return url
    host = os.getenv("REDIS_HOST")
    if not host:
        return None
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    password = os.getenv("REDIS_PASSWORD")
    scheme = "rediss" if os.getenv("REDIS_SSL") in {"1", "true", "True"} else "redis"
    auth = f":{password}@" if password else ""
    return f"{scheme}://{auth}{host}:{port}/{db}"


def _mask_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    netloc = parts.netloc
    if "@" in netloc:
        creds, host_part = netloc.split("@", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            creds = f"{user}:***"
        elif creds:
            creds = "***"
        else:
            creds = ":***"
        netloc = f"{creds}@{host_part}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


async def main() -> None:
    url = build_url()
    if not url:
        print("[warn] redis preflight skipped: configuration missing")
        return
    masked = _mask_url(url)
    timeout = float(os.getenv("REDIS_PING_TIMEOUT", "3"))
    try:
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=timeout,
            socket_connect_timeout=timeout,
        )
    except Exception as exc:
        print(f"[warn] redis preflight failed to initialise client for {masked}: {type(exc).__name__}: {exc}")
        return
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=timeout)
    except Exception as exc:
        print(f"[warn] redis ping failed for {masked}: {type(exc).__name__}: {exc}")
    else:
        print(f"[OK] redis ping ok for {masked}: {pong}")
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
