"""
/**
 * @file: tests/_stubs/numpy.py
 * @description: Offline stub for numpy that surfaces informative import errors during tests.
 * @dependencies: none
 * @created: 2025-10-26
 */
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

__all__ = ()
__offline_stub__ = "numpy"
_ERROR = (
    "numpy is unavailable in offline mode. Install numpy or unset USE_OFFLINE_STUBS to use the real package."
)


class _OfflineAttribute(ModuleType):
    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive stub
        return _OfflineAttribute(f"{self.__name__}.{name}")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - defensive stub
        raise ModuleNotFoundError(_ERROR)

    def __iter__(self):  # pragma: no cover - defensive stub
        raise ModuleNotFoundError(_ERROR)


def __getattr__(name: str) -> Any:  # pragma: no cover - defensive stub
    return _OfflineAttribute(f"numpy.{name}")


def __dir__() -> list[str]:  # pragma: no cover - defensive stub
    return []
