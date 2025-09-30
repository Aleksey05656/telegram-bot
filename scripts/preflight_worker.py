"""
@file: scripts/preflight_worker.py
@description: Preflight check ensuring worker dependencies are importable.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib


def _check(module_name: str) -> None:
    importlib.import_module(module_name)
    print(f"preflight: import {module_name}: OK", flush=True)


def main() -> None:
    print("preflight: starting", flush=True)
    _check("telegram.bot")
    _check("telegram.middlewares")
    print("preflight: OK", flush=True)


if __name__ == "__main__":
    main()
