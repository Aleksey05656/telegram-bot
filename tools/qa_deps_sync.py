"""
@file: tools/qa_deps_sync.py
@description: Offline installer for QA-min dependency profile
@dependencies: requirements-qa-min.txt, wheels/
@created: 2024-05-09
"""

from __future__ import annotations

import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Iterable


def _read_packages(requirements_path: Path) -> list[str]:
    packages: list[str] = []
    for line in requirements_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        packages.append(stripped.split()[0])
    return packages


def _print_report(packages: Iterable[str]) -> None:
    print("QA-min dependency report:")
    for name in packages:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            print(f"- {name} (not installed)")
        else:
            print(f"- {name}=={version}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    requirements_path = repo_root / "requirements-qa-min.txt"
    if not requirements_path.exists():
        print("requirements-qa-min.txt missing, nothing to install")
        return 0

    wheels_dir = repo_root / "wheels"
    wheel_files = sorted(wheels_dir.glob("*.whl")) if wheels_dir.exists() else []

    packages = _read_packages(requirements_path)

    if not wheel_files:
        print("no wheels found, skipping install")
        _print_report(packages)
        return 0

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-input",
        "--no-color",
        "--no-warn-script-location",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(wheels_dir),
        "-r",
        str(requirements_path),
    ]
    print("Installing QA-min dependencies from local wheels...")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        return result.returncode

    _print_report(packages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
