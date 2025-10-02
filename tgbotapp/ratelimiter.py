"""
/**
 * @file: tgbotapp/ratelimiter.py
 * @description: Sliding-window asynchronous rate limiter for Telegram bot messaging.
 * @dependencies: asyncio, collections, typing
 * @created: 2025-10-02
 */
"""
from __future__ import annotations

import asyncio
from collections import deque
from time import monotonic
from typing import Deque, Iterable, MutableMapping

ChatId = int | str


class _SlidingWindow:
    """Utility class encapsulating sliding window counters."""

    __slots__ = ("limit", "window", "events")

    def __init__(self, limit: int, window: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window <= 0:
            raise ValueError("window must be positive")
        self.limit = limit
        self.window = window
        self.events: Deque[float] = deque()

    def prune(self, now: float) -> None:
        cutoff = now - self.window
        events = self.events
        while events and events[0] <= cutoff:
            events.popleft()

    def register(self, timestamp: float) -> None:
        self.events.append(timestamp)

    def compute_delay(self, now: float) -> float:
        self.prune(now)
        if len(self.events) < self.limit:
            return 0.0
        oldest = self.events[0]
        return max(0.0, oldest + self.window - now)


class AsyncRateLimiter:
    """Asynchronous rate limiter with global, per-chat and group limits."""

    def __init__(
        self,
        *,
        global_limit: int = 30,
        global_window: float = 1.0,
        per_chat_limit: int = 1,
        per_chat_window: float = 1.0,
        group_limit: int = 20,
        group_window: float = 60.0,
    ) -> None:
        if global_limit <= 0:
            raise ValueError("global_limit must be positive")
        if per_chat_limit <= 0:
            raise ValueError("per_chat_limit must be positive")
        if group_limit <= 0:
            raise ValueError("group_limit must be positive")

        self._global_window = _SlidingWindow(global_limit, global_window)
        self._per_chat_limit = per_chat_limit
        self._per_chat_window = per_chat_window
        self._group_limit = group_limit
        self._group_window = group_window
        self._per_chat_windows: MutableMapping[ChatId, _SlidingWindow] = {}
        self._group_windows: MutableMapping[ChatId, _SlidingWindow] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, chat_id: ChatId) -> None:
        """Wait until sending a message to chat_id is allowed."""

        while True:
            async with self._lock:
                now = monotonic()
                wait_for = self._collect_wait_times(chat_id, now)
                delay = max(wait_for, default=0.0)
                if delay <= 0.0:
                    self._register(now, chat_id)
                    return
            await asyncio.sleep(delay)

    def _collect_wait_times(self, chat_id: ChatId, now: float) -> Iterable[float]:
        waits = [self._global_window.compute_delay(now)]

        per_chat_window = self._per_chat_windows.get(chat_id)
        if per_chat_window is None:
            per_chat_window = _SlidingWindow(self._per_chat_limit, self._per_chat_window)
            self._per_chat_windows[chat_id] = per_chat_window
        waits.append(per_chat_window.compute_delay(now))

        if self._is_group(chat_id):
            group_window = self._group_windows.get(chat_id)
            if group_window is None:
                group_window = _SlidingWindow(self._group_limit, self._group_window)
                self._group_windows[chat_id] = group_window
            waits.append(group_window.compute_delay(now))

        self._cleanup_stale(now)
        return waits

    def _register(self, timestamp: float, chat_id: ChatId) -> None:
        self._global_window.register(timestamp)

        per_chat_window = self._per_chat_windows.setdefault(
            chat_id,
            _SlidingWindow(self._per_chat_limit, self._per_chat_window),
        )
        per_chat_window.register(timestamp)

        if self._is_group(chat_id):
            group_window = self._group_windows.setdefault(
                chat_id,
                _SlidingWindow(self._group_limit, self._group_window),
            )
            group_window.register(timestamp)

    def _cleanup_stale(self, now: float) -> None:
        for windows in (self._per_chat_windows, self._group_windows):
            empty_keys: list[ChatId] = []
            for chat_id, window in windows.items():
                window.prune(now)
                if not window.events:
                    empty_keys.append(chat_id)
            for chat_id in empty_keys:
                del windows[chat_id]

    @staticmethod
    def _is_group(chat_id: ChatId) -> bool:
        if isinstance(chat_id, int):
            return chat_id < 0
        if isinstance(chat_id, str):
            return chat_id.startswith("-")
        return False


__all__ = ["AsyncRateLimiter"]
