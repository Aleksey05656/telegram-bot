"""
@file: deps_lock.py
@description: Generate requirements.lock from installed packages
@dependencies: requirements.txt
@created: 2025-09-15
"""

import re
import subprocess
from pathlib import Path

reqs = Path("requirements.txt").read_text().splitlines()
freeze_output = subprocess.check_output(["python", "-m", "pip", "freeze"], text=True)
freeze = {
    line.split("==")[0].lower().replace("-", "_"): line.split("==")[1].strip()
    for line in freeze_output.splitlines()
    if "==" in line
}
lines = []
for r in reqs:
    r = r.strip()
    if not r or r.startswith("#"):
        lines.append(r)
        continue
    name_raw = re.split(r"[<>=!; ]", r)[0]
    key = name_raw.lower().replace("-", "_")
    ver = freeze.get(key)
    lines.append(f"{name_raw}=={ver}" if ver else r)
Path("requirements.lock").write_text("\n".join(lines) + "\n")
