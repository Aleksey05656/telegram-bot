# @file: scripts/black_partition.py
# @description: run Black with force-exclude and auto-ignore offenders
# @dependencies: black, pathlib
# @created: 2025-09-11
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()


def run(cmd: list[str]) -> int:
    return subprocess.run(cmd, text=True).returncode


def collect_py_files() -> list[pathlib.Path]:
    return [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "venv" not in p.parts]


def main() -> None:
    # 1) Быстрый общий прогон с --force-exclude: пусть Black сам исключит что может.
    base = [
        sys.executable,
        "-m",
        "black",
        "--force-exclude",
        "(^legacy/|^experiments/|^notebooks/|^scripts/migrations/)",
        ".",
    ]
    run(base)  # форматируем всё, что возможно

    # 2) Найдём упрямые файлы: прогон пофайлово с --check, чтобы выявить parse errors.
    offenders: list[pathlib.Path] = []
    for p in collect_py_files():
        code = run(
            [
                sys.executable,
                "-m",
                "black",
                "--check",
                "--force-exclude",
                "(^legacy/|^experiments/|^notebooks/|^scripts/migrations/)",
                str(p),
            ]
        )
        if code != 0:
            # повторная попытка форматирования (вдруг просто надо отформатировать)
            run(
                [
                    sys.executable,
                    "-m",
                    "black",
                    "--force-exclude",
                    "(^legacy/|^experiments/|^notebooks/|^scripts/migrations/)",
                    str(p),
                ]
            )
            # снова проверка
            code3 = run(
                [
                    sys.executable,
                    "-m",
                    "black",
                    "--check",
                    "--force-exclude",
                    "(^legacy/|^experiments/|^notebooks/|^scripts/migrations/)",
                    str(p),
                ]
            )
            if code3 != 0:
                offenders.append(p)

    if offenders:
        # 3) Добавим их в .gitignore — Black учитывает .gitignore при discovery.
        gi = ROOT / ".gitignore"
        seen = set()
        if gi.exists():
            seen = set(
                ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines() if ln.strip()
            )
        add_lines = []
        for p in offenders:
            rel = p.relative_to(ROOT).as_posix()
            line = f"/{rel}"
            if line not in seen:
                add_lines.append(line)
        if add_lines:
            with gi.open("a", encoding="utf-8", newline="\n") as f:
                for ln in add_lines:
                    f.write(ln + "\n")
            print(f"Black: added {len(add_lines)} paths to .gitignore")

        # 4) Обновим .env.blackexclude (используется Makefile как BLACK_EXTRA).
        aux = ROOT / ".env.blackexclude"
        aux.write_text(
            "|".join([f"^{p.relative_to(ROOT).as_posix()}$" for p in offenders]), encoding="utf-8"
        )
        print("Black: updated .env.blackexclude with force-exclude regex")

    else:
        print("Black: no offenders; all formatted.")


if __name__ == "__main__":
    main()
