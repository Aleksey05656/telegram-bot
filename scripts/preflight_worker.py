"""
@file: scripts/preflight_worker.py
@description: Preflight check ensuring worker dependencies are importable.
@dependencies: telegram.bot, telegram.middlewares
"""

from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(module_name: str) -> None:
    print(f"[preflight] importing {module_name}...", flush=True)
    importlib.import_module(module_name)
    print(f"[preflight] {module_name}: OK", flush=True)


def main() -> None:
    try:
        _check("telegram.bot")
        _check("telegram.middlewares")
        print("[preflight] OK", flush=True)
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
