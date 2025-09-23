"""
@file: idempotency.py
@description: Helpers to deduplicate command handling per user.
@dependencies: time
@created: 2025-09-30
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

__all__ = ["CommandDeduplicator"]


@dataclass
class CommandDeduplicator:
    ttl: float = 5.0
    _seen: dict[tuple[int, str], float] = field(default_factory=dict)

    def is_duplicate(self, user_id: int, command: str) -> bool:
        now = time.monotonic()
        key = (user_id, command or "")
        last = self._seen.get(key)
        if last is not None and now - last < self.ttl:
            return True
        self._seen[key] = now
        self._purge(now)
        return False

    def _purge(self, now: float) -> None:
        expired = [key for key, ts in self._seen.items() if now - ts > self.ttl]
        for key in expired:
            self._seen.pop(key, None)
