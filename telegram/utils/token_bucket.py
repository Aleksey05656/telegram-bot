"""
"""
@file: token_bucket.py
@description: Simple token bucket rate limiter utility.
@dependencies: time
@created: 2025-09-30
"""
from __future__ import annotations

import time
from dataclasses import dataclass

__all__ = ["TokenBucket"]


@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float
    tokens: float
    updated_at: float

    @classmethod
    def create(cls, capacity: int, refill_rate: float) -> TokenBucket:
        now = time.monotonic()
        return cls(
            capacity=float(max(1, capacity)),
            refill_rate=float(max(refill_rate, 0.0)),
            tokens=float(max(1, capacity)),
            updated_at=now,
        )

    def consume(self, amount: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def available(self) -> float:
        return max(self.tokens, 0.0)
