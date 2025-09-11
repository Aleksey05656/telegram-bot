/**
 * @file: telegram/middlewares.py
 * @description: Custom middlewares for Telegram bot.
 * @dependencies: aiogram
 * @created: 2025-08-24
 */
from __future__ import annotations

import statistics
import time
from collections import deque
from typing import Any, Awaitable, Callable, Deque, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from logger import logger


class RateLimitMiddleware(BaseMiddleware):
    """Simple per-user rate limiting."""

    def __init__(self, limit: float = 1.0) -> None:
        self.limit = limit
        self._last_call: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None:
            now = time.monotonic()
            last = self._last_call.get(user.id, 0.0)
            if now - last < self.limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("Слишком много запросов. Попробуйте позже.", show_alert=True)
                else:
                    await event.answer("Слишком много запросов. Попробуйте позже.")
                return
            self._last_call[user.id] = now
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
        logger.info(
            f"{handler.__name__} took {duration:.3f}s (avg {avg:.3f}s, p95 {p95:.3f}s)"
        )
        return result
