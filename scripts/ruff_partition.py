"""
@file: scripts/ruff_partition.py
@description: Detect Ruff parse errors and append offenders to .ruffignore
@dependencies: .ruffignore
@created: 2025-09-12
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()
RUFF = [sys.executable, "-m", "ruff", "check", "--exit-zero"]  # не фейлим сразу


def py_files() -> list[pathlib.Path]:
    return [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "venv" not in p.parts]


def main() -> None:
    offenders: list[str] = []
    for p in py_files():
        # Запуск на конкретном файле с жёстким выходом
        code = subprocess.run([sys.executable, "-m", "ruff", "check", str(p)], text=True).returncode
        if code == 2:  # код 2 — parse error / internal error
            rel = p.relative_to(ROOT).as_posix()
            offenders.append(rel)

    if offenders:
        gi = ROOT / ".ruffignore"
        text = gi.read_text(encoding="utf-8") if gi.exists() else ""
        existing = set(ln.strip() for ln in text.splitlines() if ln.strip())
        add = [f"/{o}" for o in offenders if f"/{o}" not in existing]
        if add:
            with gi.open("a", encoding="utf-8", newline="\n") as f:
                for ln in add:
                    f.write(ln + "\n")
            print(f"Ruff: added {len(add)} parse-offenders to .ruffignore")
    else:
        print("Ruff: no parse offenders")


if __name__ == "__main__":
    main()
