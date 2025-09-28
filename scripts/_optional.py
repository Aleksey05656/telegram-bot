"""
/**
 * @file: scripts/_optional.py
 * @description: Helpers for importing optional dependencies with offline fallbacks.
 * @dependencies: importlib, os
 * @created: 2025-09-28
 */
"""

from __future__ import annotations

import importlib
import os
from types import ModuleType
from typing import Any

_OFFLINE_FLAGS = {"USE_OFFLINE_STUBS", "AMVERA", "FAILSAFE_MODE"}


class _MissingDependency:
    """Runtime placeholder raising informative errors when accessed."""

    def __init__(self, reference: str, original: Exception) -> None:
        self._reference = reference
        self._original = original

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - defensive
        raise ModuleNotFoundError(
            f"Optional dependency '{self._reference}' is unavailable; install required packages to use it."
        ) from self._original

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - defensive
        raise ModuleNotFoundError(
            f"Optional dependency '{self._reference}' is unavailable; install required packages to use it."
        ) from self._original

    def __bool__(self) -> bool:  # pragma: no cover - compatibility
        return False

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<MissingDependency {self._reference}>"


def _offline_mode() -> bool:
    for flag in _OFFLINE_FLAGS:
        value = os.getenv(flag)
        if isinstance(value, str) and value.lower() in {"1", "true", "yes"}:
            return True
    return False


def _missing(reference: str, exc: Exception) -> _MissingDependency:
    return _MissingDependency(reference, exc)


def optional_dependency(module: str, *, attr: str | None = None) -> ModuleType | _MissingDependency | Any:
    """Import optional module or attribute, providing a stub in offline mode."""

    reference = f"{module}.{attr}" if attr else module
    try:
        loaded = importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if _offline_mode():
            return _missing(reference, exc)
        raise
    if attr is None:
        return loaded
    try:
        return getattr(loaded, attr)
    except AttributeError as exc:
        if _offline_mode():
            return _missing(reference, exc)
        raise


__all__ = ["optional_dependency"]
