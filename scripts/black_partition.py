# @file: scripts/black_partition.py
# @description: run Black per file and exclude failing ones
# @dependencies: black, pyproject.toml
# @created: 2025-09-11
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()
PY_FILES = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "venv" not in p.parts]


def run_black_on(path: pathlib.Path) -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "black", str(path)], capture_output=True, text=True
        )
        return r.returncode == 0
    except Exception:
        return False


def update_black_exclude(failing: list[pathlib.Path]) -> None:
    if not failing:
        return
    ppt = ROOT / "pyproject.toml"
    txt = ppt.read_text(encoding="utf-8") if ppt.exists() else ""
    # найдём блок extend-exclude
    m = re.search(
        r"(?s)(\[tool\.black\].*?extend-exclude\s*=\s*\"\"\"\s*\(\s*)(.*?)(\s*\)\s*\"\"\"\s*)", txt
    )
    if not m:
        # минимальный блок, если отсутствует
        txt = txt.rstrip() + '\n\n[tool.black]\nextend-exclude = """\n(\n)\n"""\n'
        m = re.search(
            r"(?s)(\[tool\.black\].*?extend-exclude\s*=\s*\"\"\"\s*\(\s*)(.*?)(\s*\)\s*\"\"\"\s*)",
            txt,
        )
    _before, inner, _after = m.group(1), m.group(2), m.group(3)

    # нормализуем относительные пути
    entries = set(filter(None, [ln.strip() for ln in inner.splitlines()]))
    for p in failing:
        rel = p.relative_to(ROOT).as_posix()
        entries.add(f"| ^{re.escape(rel)}$")
    # собрать назад
    body = "\n  ".join(sorted(entries))
    new = re.sub(
        r"(?s)\[tool\.black\].*?extend-exclude\s*=\s*\"\"\"\s*\(\s*.*?\s*\)\s*\"\"\"",
        f'[tool.black]\nextend-exclude = """\n(\n  {body}\n)\n"""',
        txt,
        count=1,
    )
    ppt.write_text(new, encoding="utf-8")


def main() -> None:
    failing = []
    for p in PY_FILES:
        ok = run_black_on(p)
        if not ok:
            failing.append(p)
    if failing:
        print(f"Black failed on {len(failing)} files. Updating pyproject.toml exclude…")
        update_black_exclude(failing)
        for p in failing:
            print(f"- {p}")
    else:
        print("Black formatted all files successfully.")


if __name__ == "__main__":
    main()
