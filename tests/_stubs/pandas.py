"""
/**
 * @file: tests/_stubs/pandas.py
 * @description: Offline stub for pandas used when heavyweight dependencies are unavailable.
 * @dependencies: none
 * @created: 2025-10-26
 */
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

__all__ = ()
__offline_stub__ = "pandas"
_ERROR = (
    "pandas is unavailable in offline mode. Install pandas or unset USE_OFFLINE_STUBS to use the real package."
)


class _OfflineAttribute(ModuleType):
    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive stub
        return _OfflineAttribute(f"{self.__name__}.{name}")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - defensive stub
        raise ModuleNotFoundError(_ERROR)

    def __iter__(self):  # pragma: no cover - defensive stub
        raise ModuleNotFoundError(_ERROR)


def __getattr__(name: str) -> Any:  # pragma: no cover - defensive stub
    return _OfflineAttribute(f"pandas.{name}")


def __dir__() -> list[str]:  # pragma: no cover - defensive stub
    return []
