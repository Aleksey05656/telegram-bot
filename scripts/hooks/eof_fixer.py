#!/usr/bin/env python
"""
@file: scripts/hooks/eof_fixer.py
@description: Ensure files end with a newline character
@dependencies: pathlib
@created: 2025-09-12
"""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_trailing_nl(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except Exception:
        return False
    if not data:
        return False
    # текстовые файлы: попытаемся декодировать; бинарные игнорируем
    try:
        txt = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if txt.endswith("\n"):
        return False
    Path(path).write_text(txt + "\n", encoding="utf-8", newline="\n")
    return True


def main(argv: list[str]) -> int:
    changed = False
    for name in argv[1:]:
        p = Path(name)
        if p.is_file():
            changed |= ensure_trailing_nl(p)
    # pre-commit ожидает ненулевой код, чтобы пометить как "исправлено"
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
