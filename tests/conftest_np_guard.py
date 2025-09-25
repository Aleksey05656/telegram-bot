"""
@file: tests/conftest_np_guard.py
@description: Skip numpy/pandas dependent tests when stack unavailable
@dependencies: pytest
@created: 2025-09-15
"""

from __future__ import annotations

import os

import pytest


def _numpy_stack_ok() -> bool:
    """Check whether numpy and pandas import successfully and are usable."""
    try:
        import numpy as _np  # noqa: F401
        import pandas as _pd  # noqa: F401

        _ = _np.dtype("float64").itemsize
        _ = _pd.DataFrame({"a": [1]}).shape
        return True
    except Exception:
        return False


_NUMPY_STACK_OK = _numpy_stack_ok()
_FORCE_OFFLINE = os.getenv("USE_OFFLINE_STUBS", "").lower() in {"1", "true", "yes"}
_SKIP_MARK = pytest.mark.skip(
    reason="Skipped: numpy/pandas stack unavailable or binary-incompatible",
)
_HEAVY_PATH_PATTERNS = [
    "tests/bot/",
    "tests/diag/",
    "tests/data_processor/",
    "tests/database/",
    "tests/diagnostics/",
    "tests/integration/",
    "tests/ml/",
    "tests/odds/",
    "tests/scripts/",
    "tests/security/",
    "tests/services/",
    "tests/sm/",
    "tests/smoke/",
    "tests/workers/",
    "tests/value/",
    "tests/contracts/",
    "tests/test_metrics_sentry.py",
    "tests/test_ml.py",
    "tests/test_metrics_server.py",
    "tests/test_readiness.py",
    "tests/test_registry_local.py",
    "tests/test_task_manager",
]


def pytest_collection_modifyitems(config, items):
    offline_mode = _FORCE_OFFLINE or not _NUMPY_STACK_OK
    if not offline_mode:
        return
    for item in items:
        if any(mark.name == "needs_np" for mark in item.iter_markers()):
            item.add_marker(_SKIP_MARK)
            continue
        path = str(item.fspath)
        if any(pattern in path for pattern in _HEAVY_PATH_PATTERNS):
            item.add_marker(
                pytest.mark.skip(
                    reason="Skipped in offline stub mode: requires heavy ML/data stack",
                )
            )


def pytest_ignore_collect(path, config):  # pragma: no cover - collection guard
    offline_mode = _FORCE_OFFLINE or not _NUMPY_STACK_OK
    if not offline_mode:
        return False
    path_str = str(path)
    return any(pattern in path_str for pattern in _HEAVY_PATH_PATTERNS)
