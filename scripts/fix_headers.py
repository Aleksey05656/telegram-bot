# @file: scripts/fix_headers.py
# @description: Normalize file headers by removing BOM and cleaning coding cookies
# @dependencies: pathlib
# @created: 2025-09-10
from __future__ import annotations

import io
import pathlib


def normalize_file(p: pathlib.Path) -> bool:
    try:
        raw = p.read_bytes()
        # Убираем BOM
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return False

    lines = text.splitlines()
    changed = False

    # Удаляем дублирующиеся/битые coding cookies, оставляем корректный только в первой строке при необходимости
    def is_coding_line(s: str) -> bool:
        return "coding:" in s.replace(" ", "").lower()

    # Фильтруем все coding-строки, добавим корректную при необходимости
    clean = [ln for ln in lines if not is_coding_line(ln)]

    # Если исходный файл содержал coding-строку, добавим стандартный вариант в первую строку
    if any(is_coding_line(ln) for ln in lines):
        clean = ["# -*- coding: utf-8 -*-"] + clean
        changed = True

    new_text = "\n".join(clean) + (
        "\n" if clean and not clean[-1].endswith("\n") else ""
    )
    if new_text != text:
        p.write_text(new_text, encoding="utf-8", newline="\n")
        changed = True
    return changed


def main() -> None:
    root = pathlib.Path(".")
    py_files = [
        p
        for p in root.rglob("*.py")
        if "venv" not in p.parts and ".venv" not in p.parts
    ]
    touched = 0
    for p in py_files:
        if normalize_file(p):
            touched += 1
    print(f"Normalized headers in {touched} files")


if __name__ == "__main__":
    main()
