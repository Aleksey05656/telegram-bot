"""
@file: deps_lock.py
@description: Generate requirements.lock from installed packages
@dependencies: requirements.txt
@created: 2025-09-15
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable


def _read_requirements(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _freeze() -> Iterable[str]:
    output = subprocess.check_output(["python", "-m", "pip", "freeze"], text=True)
    return output.splitlines()


def generate_lock(requirements: Path, destination: Path | None = None) -> Path:
    lines = _read_requirements(requirements)
    frozen = {
        line.split("==")[0].lower().replace("-", "_"): line.split("==")[1].strip()
        for line in _freeze()
        if "==" in line
    }
    resolved: list[str] = []
    for entry in lines:
        token = entry.strip()
        if not token or token.startswith("#"):
            resolved.append(entry)
            continue
        name_raw = re.split(r"[<>=!; ]", token)[0]
        key = name_raw.lower().replace("-", "_")
        version = frozen.get(key)
        resolved.append(f"{name_raw}=={version}" if version else entry)
    target = destination or Path("requirements.lock")
    target.write_text("\n".join(resolved) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    generate_lock(Path("requirements.txt"))
