"""
@file: tests/conftest_np_guard.py
@description: Skip numpy/pandas dependent tests when stack unavailable
@dependencies: pytest
@created: 2025-09-15
"""

from __future__ import annotations

import os
import re

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
_RAW_PATTERNS = os.getenv("NEEDS_NP_PATTERNS", "test_ml.py|test_services.py|test_metrics.py")
_PATTERNS = "|".join(re.escape(p) for p in _RAW_PATTERNS.split("|"))
_PATTERN_RE = re.compile(_PATTERNS)
_SKIP_MARK = pytest.mark.skip(
    reason="Skipped: numpy/pandas stack unavailable or binary-incompatible",
)


def pytest_collection_modifyitems(config, items):
    if _NUMPY_STACK_OK:
        return
    for item in items:
        if any(mark.name == "needs_np" for mark in item.iter_markers()) or _PATTERN_RE.search(item.fspath.basename):
            item.add_marker(_SKIP_MARK)
