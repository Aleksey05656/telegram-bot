"""
@file: sitecustomize.py
@description: Automatically activates offline QA stubs when USE_OFFLINE_STUBS=1
@dependencies: tools.qa_stub_injector
@created: 2025-09-28
"""

from __future__ import annotations

import os
import sys
from types import ModuleType
from typing import Callable


def _safe_call(func: Callable[[], None]) -> None:
    try:
        func()
    except Exception:
        pass


def _inject_stub_marker(module: ModuleType) -> None:
    try:
        setattr(module, "__OFFLINE_STUB__", True)
    except Exception:
        pass


def _bootstrap_offline_stubs() -> None:
    os.environ.setdefault("_SITE_CUSTOMIZE_BOOTSTRAPPED", "0")

    if os.getenv("USE_OFFLINE_STUBS") != "1":
        return

    try:
        from tools import qa_stub_injector
    except Exception:
        return

    install = getattr(qa_stub_injector, "install_stubs", None)
    if not callable(install):
        return

    _safe_call(install)
    os.environ["_SITE_CUSTOMIZE_BOOTSTRAPPED"] = "1"

    # Ensure that minimal fastapi/starlette placeholders are marked so that
    # downstream checks can distinguish stubbed environments without skipping
    # the readiness probes entirely.
    for name in ("fastapi", "starlette", "starlette.testclient"):
        module = sys.modules.get(name)
        if isinstance(module, ModuleType):
            _inject_stub_marker(module)


_bootstrap_offline_stubs()
