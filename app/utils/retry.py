# @file: retry.py
# @description: Generic asynchronous retry helper.
# @dependencies: logger.py, config.py
"""Retry helpers for asynchronous callables."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from config import settings
from logger import logger

T = TypeVar("T")


async def retry_async(
    func: Callable[..., Awaitable[T] | T],
    *args: Any,
    retries: int | None = None,
    delay: float | None = None,
    max_delay: float | None = None,
    backoff: float | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """Execute ``func`` with retries using exponential backoff.

    ``func`` may return either an awaitable or a plain value. Synchronous callables
    should be lightweight; wrap blocking IO in ``asyncio.to_thread`` when needed.
    """

    attempts = retries if retries is not None else settings.RETRY_ATTEMPTS
    current_delay = delay if delay is not None else settings.RETRY_DELAY
    max_delay = max_delay if max_delay is not None else settings.RETRY_MAX_DELAY
    backoff = backoff if backoff is not None else settings.RETRY_BACKOFF

    if attempts < 0:
        raise ValueError("retries must be >= 0")

    attempt = 0
    while True:
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except exceptions as exc:  # pragma: no cover - retry path
            attempt += 1
            if attempt > attempts:
                logger.error("Retry attempts exhausted: %s", exc)
                raise
            wait_time = min(current_delay, max_delay)
            logger.warning(
                "Retrying %s in %.2fs (attempt %s/%s)",
                getattr(func, "__qualname__", getattr(func, "__name__", str(func))),
                wait_time,
                attempt,
                attempts,
            )
            await asyncio.sleep(wait_time)
            current_delay = min(current_delay * backoff, max_delay)


__all__ = ["retry_async"]
