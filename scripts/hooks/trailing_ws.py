#!/usr/bin/env python
"""
@file: scripts/hooks/trailing_ws.py
@description: Strip trailing whitespace from text files
@dependencies: pathlib
@created: 2025-09-12
"""
from __future__ import annotations

import sys
from pathlib import Path


def fix_file(path: Path) -> bool:
    try:
        orig = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # бинарники пропускаем
        return False
    lines = orig.splitlines(True)
    changed = False
    new_lines = []
    for ln in lines:
        if ln.endswith(("\r\n", "\n")):
            ln_nl = ln[-1]
            body = ln[:-1].rstrip(" \t")
            if body + ln_nl != ln:
                changed = True
            new_lines.append(body + ln_nl)
        else:
            body = ln.rstrip(" \t")
            if body != ln:
                changed = True
            new_lines.append(body)
    if changed:
        path.write_text("".join(new_lines), encoding="utf-8", newline="\n")
    return changed


def main(argv: list[str]) -> int:
    changed_any = False
    for name in argv[1:]:
        p = Path(name)
        if p.is_file():
            changed_any |= fix_file(p)
    return 1 if changed_any else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
