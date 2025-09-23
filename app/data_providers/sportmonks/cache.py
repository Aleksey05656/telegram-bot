"""
/**
 * @file: cache.py
 * @description: Persistent ETag cache helpers for Sportmonks HTTP client.
 * @dependencies: dataclasses, datetime, hashlib, json, typing
 * @created: 2025-02-14
 */
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol


class MetaStorage(Protocol):
    """Minimal storage protocol backed by SportmonksRepository."""

    def get_meta(self, key: str) -> str | None:
        """Return stored value for the given key."""

    def upsert_meta(self, key: str, value: str) -> None:
        """Persist value for the given key."""


@dataclass(slots=True)
class CacheEntry:
    """Cached response metadata for conditional requests."""

    etag: str | None
    last_modified: str | None
    stored_at: datetime

    def is_expired(self, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            return True
        age = datetime.now(tz=UTC) - self.stored_at
        return age.total_seconds() > ttl_seconds


class SportmonksETagCache:
    """Persist and retrieve ETag headers for Sportmonks endpoints."""

    def __init__(self, storage: MetaStorage, ttl_seconds: int) -> None:
        self._storage = storage
        self._ttl = max(int(ttl_seconds), 0)

    def load(self, endpoint: str, params: Mapping[str, Any] | None = None) -> CacheEntry | None:
        if self._ttl == 0:
            return None
        key = self._key(endpoint, params)
        raw = self._storage.get_meta(key)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        stored_at = _parse_ts(payload.get("stored_at"))
        if stored_at is None:
            return None
        entry = CacheEntry(
            etag=payload.get("etag"),
            last_modified=payload.get("last_modified"),
            stored_at=stored_at,
        )
        if entry.is_expired(self._ttl):
            return None
        return entry

    def store(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None,
        *,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        if self._ttl == 0:
            return
        key = self._key(endpoint, params)
        payload = {
            "endpoint": endpoint,
            "params": _normalize_params(params),
            "etag": etag,
            "last_modified": last_modified,
            "stored_at": datetime.now(tz=UTC).isoformat(),
        }
        self._storage.upsert_meta(key, json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def touch(self, endpoint: str, params: Mapping[str, Any] | None, entry: CacheEntry | None) -> None:
        if self._ttl == 0 or entry is None:
            return
        self.store(endpoint, params, etag=entry.etag, last_modified=entry.last_modified)

    def _key(self, endpoint: str, params: Mapping[str, Any] | None) -> str:
        normalized_endpoint = endpoint.strip()
        digest = hashlib.sha1(normalized_endpoint.encode("utf-8")).hexdigest()
        return f"sportmonks:etag:{digest}"


def _normalize_params(params: Mapping[str, Any] | None) -> dict[str, str]:
    if not params:
        return {}
    normalized: dict[str, str] = {}
    for key, value in params.items():
        normalized[str(key)] = _stringify(value)
    return dict(sorted(normalized.items()))


def _stringify(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ",".join(sorted(_stringify(item) for item in value))
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    return str(value)


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, str):
        candidate = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None
