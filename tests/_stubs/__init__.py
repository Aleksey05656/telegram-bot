"""
/**
 * @file: tests/_stubs/__init__.py
 * @description: Helper utilities for loading offline stub packages in tests.
 * @dependencies: importlib, pathlib, types
 * @created: 2025-02-16
 */
"""

from __future__ import annotations

import os
import sys
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Iterable

__all__ = ["ensure_stub", "ensure_stubs"]


_STUBS_ROOT = Path(__file__).resolve().parent
_FORCE_STUBS = os.getenv("USE_OFFLINE_STUBS", "").lower() in {"1", "true", "yes"}


def _load_module_from_path(
    name: str,
    path: Path,
    *,
    package_dir: Path | None = None,
) -> ModuleType | None:
    search_locations = None
    if package_dir is not None:
        search_locations = [str(package_dir)]
    spec = spec_from_file_location(name, path, submodule_search_locations=search_locations)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        return None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_package(name: str) -> ModuleType | None:
    package_dir = _STUBS_ROOT / name
    module_file = _STUBS_ROOT / f"{name}.py"
    if package_dir.exists():
        init_path = package_dir / "__init__.py"
        if not init_path.exists():
            return None
        return _load_module_from_path(name, init_path, package_dir=package_dir)
    if module_file.exists():
        return _load_module_from_path(name, module_file)
    return None


def ensure_stub(package: str) -> None:
    """Register stub package in sys.modules when the real dependency is missing."""

    if not _FORCE_STUBS:
        if package in sys.modules:
            return
        try:
            import_module(package)
            return
        except ImportError:
            pass

    module = _load_package(package)
    if module is None:
        if _FORCE_STUBS:
            raise ImportError(f"Offline stub for {package!r} is missing")
        raise


def ensure_stubs(packages: Iterable[str]) -> None:
    for name in packages:
        ensure_stub(name)
