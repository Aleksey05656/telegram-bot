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

from redis.asyncio import Redis

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
    print(f"[preflight] built_url={_mask_url(url) if url else None!r}")
    if not url:
        print("[preflight] no redis config, skip")
        return
    client = Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=3,
        socket_connect_timeout=3,
    )
    pong = await client.ping()
    print(f"[preflight] redis ping: {pong}")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
