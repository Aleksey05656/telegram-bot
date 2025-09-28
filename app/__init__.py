"""
@file: __init__.py
@description: Lazily expose configuration helpers to avoid heavy imports.
@dependencies: importlib
@created: 2025-09-09
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {"Settings", "get_settings"}


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        module = import_module(".config", __name__)
        return getattr(module, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted({*globals().keys(), *_EXPORTS})


__all__ = sorted(_EXPORTS)
