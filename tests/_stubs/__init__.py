"""
/**
 * @file: tests/_stubs/__init__.py
 * @description: Helper utilities for loading offline stub packages in tests.
 * @dependencies: importlib, pathlib, types
 * @created: 2025-02-16
 */
"""

from __future__ import annotations

import sys
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Iterable

__all__ = ["ensure_stub", "ensure_stubs"]


_STUBS_ROOT = Path(__file__).resolve().parent


def _load_package(package: str) -> ModuleType | None:
    package_path = _STUBS_ROOT / package
    init_path = package_path / "__init__.py"
    if not init_path.exists():
        return None
    spec = spec_from_file_location(
        package,
        init_path,
        submodule_search_locations=[str(package_path)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        return None
    module = module_from_spec(spec)
    sys.modules[package] = module
    spec.loader.exec_module(module)
    return module


def ensure_stub(package: str) -> None:
    """Register stub package in sys.modules when the real dependency is missing."""

    if package in sys.modules:
        return
    try:
        import_module(package)
    except ImportError:
        module = _load_package(package)
        if module is None:
            raise


def ensure_stubs(packages: Iterable[str]) -> None:
    for name in packages:
        ensure_stub(name)
