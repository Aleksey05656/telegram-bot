"""
/**
 * @file: cache.py
 * @description: Persistent ETag cache helpers for Sportmonks HTTP client.
 * @dependencies: dataclasses, datetime, hashlib, json, re, typing, urllib.parse
 * @created: 2025-02-14
 */
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping, Protocol
from urllib.parse import urlsplit


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


DEFAULT_PARAM_ALLOWLIST: tuple[str, ...] = (
    "include",
    "from",
    "to",
    "date_from",
    "date_to",
    "league_id",
    "league_ids",
    "season_id",
    "season_ids",
    "team_id",
    "team_ids",
    "player_id",
    "player_ids",
    "page",
    "per_page",
    "offset",
    "limit",
    "tz",
    "timezone",
    "language",
    "lang",
)


class SportmonksETagCache:
    """Persist and retrieve ETag headers for Sportmonks endpoints."""

    def __init__(
        self,
        storage: MetaStorage,
        ttl_seconds: int,
        *,
        param_allowlist: Iterable[str] | None = None,
    ) -> None:
        self._storage = storage
        self._ttl = max(int(ttl_seconds), 0)
        allowed = tuple(param_allowlist) if param_allowlist is not None else DEFAULT_PARAM_ALLOWLIST
        self._allowed_params = {str(item) for item in allowed}

    def load(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        *,
        method: str = "GET",
    ) -> CacheEntry | None:
        if self._ttl == 0:
            return None
        key = self._key(method, endpoint, params)
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
        method: str = "GET",
    ) -> None:
        if self._ttl == 0:
            return
        entry = CacheEntry(
            etag=etag,
            last_modified=last_modified,
            stored_at=datetime.now(tz=UTC),
        )
        self._persist(method, endpoint, params, entry)

    def touch(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None,
        entry: CacheEntry | None,
        *,
        method: str = "GET",
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        if self._ttl == 0 or entry is None:
            return
        refreshed = CacheEntry(
            etag=etag if etag is not None else entry.etag,
            last_modified=last_modified if last_modified is not None else entry.last_modified,
            stored_at=entry.stored_at,
        )
        self._persist(method, endpoint, params, refreshed)

    def _persist(
        self,
        method: str,
        endpoint: str,
        params: Mapping[str, Any] | None,
        entry: CacheEntry,
    ) -> None:
        key = self._key(method, endpoint, params)
        filtered_params = _filter_params(params, self._allowed_params)
        payload = {
            "method": _canonical_method(method),
            "endpoint": _canonical_path(endpoint),
            "params": filtered_params,
            "etag": entry.etag,
            "last_modified": entry.last_modified,
            "stored_at": entry.stored_at.isoformat(),
            "canonical": _canonical_source(method, endpoint, params, self._allowed_params),
        }
        self._storage.upsert_meta(key, json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def _key(self, method: str, endpoint: str, params: Mapping[str, Any] | None) -> str:
        canonical = _canonical_source(method, endpoint, params, self._allowed_params)
        digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
        return f"sportmonks:etag:{digest}"


def _filter_params(params: Mapping[str, Any] | None, allowed: set[str]) -> dict[str, str]:
    if not params:
        return {}
    normalized: dict[str, str] = {}
    for key, value in params.items():
        key_str = str(key)
        if key_str in allowed:
            normalized[key_str] = _stringify(value)
    return dict(sorted(normalized.items()))


def _canonical_source(
    method: str,
    endpoint: str,
    params: Mapping[str, Any] | None,
    allowed: set[str],
) -> str:
    method_part = _canonical_method(method)
    path_part = _canonical_path(endpoint)
    filtered = _filter_params(params, allowed)
    if filtered:
        query = "&".join(f"{name}={filtered[name]}" for name in filtered)
        return f"{method_part}:{path_part}?{query}"
    return f"{method_part}:{path_part}"


def _canonical_method(method: str | None) -> str:
    if not method:
        return "GET"
    normalized = method.strip().upper()
    return normalized or "GET"


def _canonical_path(endpoint: str) -> str:
    if not endpoint:
        return "/"
    candidate = endpoint.strip()
    if "//" in candidate or "://" in candidate:
        parsed = urlsplit(candidate)
        path = parsed.path or "/"
    else:
        path = candidate if candidate.startswith("/") else f"/{candidate}"
    squashed = re.sub(r"/{2,}", "/", path)
    if len(squashed) > 1 and squashed.endswith("/"):
        squashed = squashed.rstrip("/")
    if not squashed.startswith("/"):
        squashed = f"/{squashed}"
    return squashed


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
