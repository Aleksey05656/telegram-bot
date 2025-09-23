"""
/**
 * @file: aiogram/__init__.py
 * @description: Minimal aiogram stubs providing Router for offline tests.
 * @dependencies: typing
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from typing import Any, Callable, List

__all__ = ["Router", "F"]


class Router:
    """Lightweight router collecting decorated handlers."""

    def __init__(self) -> None:
        self._handlers: List[Callable[..., Any]] = []

    def message(self, *_filters: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self._handlers.append(handler)
            return handler

        return decorator

    def callback_query(self, *_filters: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self._handlers.append(handler)
            return handler

        return decorator


class _FilterField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, _other: Any) -> Callable[..., bool]:
        return lambda *_args, **_kwargs: True

    def startswith(self, _prefix: str) -> Callable[..., bool]:
        return lambda *_args, **_kwargs: True


class _FilterBuilder:
    def __getattr__(self, name: str) -> _FilterField:
        return _FilterField(name)


F = _FilterBuilder()

