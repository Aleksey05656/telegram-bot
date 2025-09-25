"""
/**
 * @file: tests/_stubs/sqlalchemy.py
 * @description: Offline stub for SQLAlchemy; used to short-circuit heavy optional dependency.
 * @dependencies: none
 * @created: 2025-10-26
 */
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

__all__ = ()
__offline_stub__ = "sqlalchemy"
_ERROR = (
    "sqlalchemy is unavailable in offline mode. Install SQLAlchemy or unset USE_OFFLINE_STUBS to use the real package."
)


class _OfflineAttribute(ModuleType):
    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive stub
        return _OfflineAttribute(f"sqlalchemy.{name}")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - defensive stub
        raise ModuleNotFoundError(_ERROR)


def __getattr__(name: str) -> Any:  # pragma: no cover - defensive stub
    return _OfflineAttribute(f"sqlalchemy.{name}")


def __dir__() -> list[str]:  # pragma: no cover - defensive stub
    return []
