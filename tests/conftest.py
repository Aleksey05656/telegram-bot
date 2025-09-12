"""
@file: tests/conftest.py
@description: Pytest fixtures to enable Prometheus metrics and reset settings cache
@dependencies: app/config.py
@created: 2025-09-10
"""

import os
import pathlib
import sys

import pytest


def _numpy_stack_ok() -> bool:
    """
    Пытаемся импортировать numpy/pandas и сделать примитивные вызовы.
    Ловим ImportError/OSError (бинарная несовместимость), ValueError.
    """
    try:
        import numpy as _np  # noqa
        import pandas as _pd  # noqa

        _ = _np.dtype("float64").itemsize
        _ = _pd.DataFrame({"a": [1, 2]}).shape
        return True
    except Exception:
        return False


_SKIP_NUMPY_STACK = os.getenv("CI_SKIP_NUMPY", "0") == "1" or not _numpy_stack_ok()


def pytest_configure(config):
    config.addinivalue_line("markers", "needs_np: test requires working numpy/pandas stack")


def pytest_collection_modifyitems(config, items):
    if not _SKIP_NUMPY_STACK:
        return
    skip_marker = pytest.mark.skip(
        reason="Skipped: numpy/pandas stack unavailable or binary-incompatible"
    )
    for item in items:
        if any(mark.name == "needs_np" for mark in item.iter_markers()):
            item.add_marker(skip_marker)


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config as cfg  # noqa: E402


@pytest.fixture(autouse=True)
def _force_prometheus_enabled(monkeypatch):
    monkeypatch.setenv("PROMETHEUS__ENABLED", "true")
    if hasattr(cfg, "reset_settings_cache"):
        cfg.reset_settings_cache()
    return


@pytest.fixture(autouse=True)
def _defaults_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", os.getenv("APP_NAME", "ml-service"))
    monkeypatch.setenv("DEBUG", os.getenv("DEBUG", "false"))
    return
