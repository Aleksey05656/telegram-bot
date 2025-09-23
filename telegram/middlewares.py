"""
@file: telegram/middlewares.py
@description: Custom middlewares for Telegram bot.
@dependencies: aiogram
@created: 2025-08-24
"""
from __future__ import annotations

import statistics
import time
from collections import deque
from typing import Any, Awaitable, Callable, Deque, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.metrics import handler_latency, record_command, record_update
from logger import logger
from telegram.utils.idempotency import CommandDeduplicator
from telegram.utils.token_bucket import TokenBucket


class RateLimitMiddleware(BaseMiddleware):
    """Token-bucket based per-user throttling."""

    def __init__(self, capacity: int = 5, per_seconds: float = 3.0) -> None:
        self.capacity = max(1, capacity)
        refill_rate = self.capacity / max(per_seconds, 1e-3)
        self._refill_rate = refill_rate
        self._buckets: Dict[int, TokenBucket] = {}

    def _bucket_for(self, user_id: int) -> TokenBucket:
        bucket = self._buckets.get(user_id)
        if bucket is None:
            bucket = TokenBucket.create(self.capacity, self._refill_rate)
            self._buckets[user_id] = bucket
        return bucket

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None:
            bucket = self._bucket_for(user.id)
            if not bucket.consume():
                if isinstance(event, CallbackQuery):
                    await event.answer("Слишком много запросов. Попробуйте позже.", show_alert=True)
                else:
                    await event.answer("Слишком много запросов. Попробуйте позже.")
                return
        record_update()
        return await handler(event, data)


class IdempotencyMiddleware(BaseMiddleware):
    """Deduplicate repeated commands from the same user within TTL."""

    def __init__(self, ttl: float = 5.0) -> None:
        self._deduplicator = CommandDeduplicator(ttl=ttl)

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            user = getattr(event, "from_user", None)
            if user is not None:
                command = event.text.split()[0].lstrip("/")
                if self._deduplicator.is_duplicate(user.id, command):
                    await event.answer("Команда уже обрабатывается. Подождите ответ.")
                    return
                record_command(command)
        return await handler(event, data)


class ProcessingTimeMiddleware(BaseMiddleware):
    """Measure handler execution time and log aggregate stats."""

    def __init__(self, sample_size: int = 100) -> None:
        self.durations: Deque[float] = deque(maxlen=sample_size)

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        start = time.perf_counter()
        result = await handler(event, data)
        duration = time.perf_counter() - start
        self.durations.append(duration)
        avg = statistics.mean(self.durations)
        sorted_durations = sorted(self.durations)
        p95_index = max(int(len(sorted_durations) * 0.95) - 1, 0)
        p95 = sorted_durations[p95_index]
        handler_latency.observe(duration)
        logger.info(
            f"{handler.__name__} took {duration:.3f}s (avg {avg:.3f}s, p95 {p95:.3f}s)"
        )
        return result
