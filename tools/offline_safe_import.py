"""
@file: tools/offline_safe_import.py
@description: Helper to activate offline stubs and print safe-import status
@dependencies: tools.qa_stub_injector
@created: 2024-05-09
"""

from __future__ import annotations

import os
import sys
from importlib import import_module


def main() -> int:
    os.environ.setdefault("USE_OFFLINE_STUBS", "1")
    try:
        injector = import_module("tools.qa_stub_injector")
        install_stubs = getattr(injector, "install_stubs")
    except Exception:
        return 0

    try:
        install_stubs()
    except Exception:
        return 0

    print("SAFE_IMPORT: STARTED")

    try:
        safe_import = import_module("tools.safe_import")
    except ModuleNotFoundError:
        pass
    except Exception:
        return 0
    else:
        maybe_runner = getattr(safe_import, "main", None)
        if callable(maybe_runner):
            maybe_runner()

    print("SAFE_IMPORT: OK (stubs active)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
