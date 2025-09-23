"""
/**
 * @file: redis/__init__.py
 * @description: Minimal Redis client stub for offline tests.
 * @dependencies: none
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

__all__ = ["Redis", "ConnectionError"]


class ConnectionError(Exception):
    """Placeholder Redis connection error."""


class Redis:
    """Simplified Redis stub implementing methods used by TaskManager."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._storage: dict[str, bytes] = {}

    @classmethod
    def from_url(cls, url: str, **_kwargs: object) -> "Redis":
        return cls(url)

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: bytes) -> None:
        self._storage[key] = value

    def get(self, key: str) -> bytes | None:
        return self._storage.get(key)

