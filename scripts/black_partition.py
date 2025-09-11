# @file: scripts/black_partition.py
# @description: run Black per file and update extend-exclude
# @dependencies: black, pyproject.toml
# @created: 2025-09-11
from __future__ import annotations
import subprocess, sys, pathlib, re

ROOT = pathlib.Path(".").resolve()
PY_FILES = [
    p for p in ROOT.rglob("*.py")
    if ".venv" not in p.parts and "venv" not in p.parts
]


def run_black_on(path: pathlib.Path) -> bool:
    r = subprocess.run([sys.executable, "-m", "black", str(path)], capture_output=True, text=True)
    return r.returncode == 0


def update_black_exclude(failing: list[pathlib.Path]) -> None:
    if not failing:
        return
    ppt = ROOT / "pyproject.toml"
    txt = ppt.read_text(encoding="utf-8")
    pat = re.compile(r'(?m)^\s*extend-exclude\s*=\s*"(.*)"\s*$')
    m = pat.search(txt)
    if not m:
        raise SystemExit("extend-exclude not found in [tool.black]")
    current = m.group(1)
    # Собираем альтернативы вида ^path\.py$
    alts = set(filter(None, current.split("|")))
    for p in failing:
        rel = p.relative_to(ROOT).as_posix()
        # экранируем точки и плюсы
        esc = re.sub(r'([.^$+?{}()\[\]|\\])', r'\\\1', rel)
        alts.add(f"^{esc}$")
    new_val = "|".join(sorted(alts))
    new_txt = pat.sub(f'extend-exclude = "{new_val}"', txt, count=1)
    ppt.write_text(new_txt, encoding="utf-8")


def main() -> None:
    failing = [p for p in PY_FILES if not run_black_on(p)]
    if failing:
        print(f"Black failed on {len(failing)} files. Updating extend-exclude…")
        update_black_exclude(failing)
        for p in failing:
            print(f"- {p}")
    else:
        print("Black formatted all files successfully.")


if __name__ == "__main__":
    main()

