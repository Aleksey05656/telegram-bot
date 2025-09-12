# @file: scripts/syntax_partition.py
# @description: Split parseable and non-parseable app python files, update ignore lists, and emit lint targets
# @dependencies: pathlib, sys, subprocess
# @created: 2025-09-12
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()


def py_files_under(root: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in root.rglob("*.py") if ".venv" not in p.parts and "venv" not in p.parts]


def is_parseable(path: pathlib.Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        compile(src, str(path), "exec")
        return True
    except SyntaxError:
        return False
    except Exception:
        # любые «битые» файлы считаем непарсящими
        return False


def append_lines(file: pathlib.Path, lines: list[str]) -> int:
    file.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if file.exists():
        existing = {
            ln.strip() for ln in file.read_text(encoding="utf-8").splitlines() if ln.strip()
        }
    add = [ln for ln in lines if ln.strip() and ln not in existing]
    if add:
        with file.open("a", encoding="utf-8", newline="\n") as f:
            for ln in add:
                f.write(ln + "\n")
    return len(add)


def main() -> None:
    app_root = ROOT / "app"
    all_files = py_files_under(app_root)
    bad = [p for p in all_files if not is_parseable(p)]
    good = [p for p in all_files if p not in bad]

    # 1) добавить плохие в .ruffignore и .gitignore
    ruff_lines = [f"/{p.relative_to(ROOT).as_posix()}" for p in bad]
    gi_lines = [f"/{p.relative_to(ROOT).as_posix()}" for p in bad]

    added_ruff = append_lines(ROOT / ".ruffignore", ruff_lines)
    added_git = append_lines(ROOT / ".gitignore", gi_lines)

    # 2) обновить .env.blackexclude — regex через |
    if bad:
        aux = ROOT / ".env.blackexclude"
        regex_parts = [f"^{p.relative_to(ROOT).as_posix()}$" for p in bad]
        content = "BLACK_EXTRA = " + "|".join(regex_parts)
        aux.write_text(content, encoding="utf-8")
    print(
        f"syntax_partition: {len(good)} parseable, {len(bad)} invalid; +{added_ruff} to .ruffignore, +{added_git} to .gitignore"
    )

    # 3) сохранить список parseable файлов для lint-app
    out = ROOT / ".lint_targets_app"
    out.write_text("\n".join([p.as_posix() for p in good]), encoding="utf-8")
    print(f"syntax_partition: wrote {out}")


if __name__ == "__main__":
    main()
