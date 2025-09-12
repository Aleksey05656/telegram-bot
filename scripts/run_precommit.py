#!/usr/bin/env python
"""
@file: scripts/run_precommit.py
@description: Smart pre-commit runner with offline fallback.
@dependencies: pre-commit, .pre-commit-config.offline.yaml
@created: 2025-09-12
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

"""
Smart pre-commit runner:
- tries standard pre-commit (remote hooks)
- if network/proxy blocks (CONNECT 403, fetch error, SSL, etc.), falls back to offline config
Usage:
  python scripts/run_precommit.py [--all-files | --files <list>]
Env:
  PRECOMMIT (command, default 'pre-commit')
  OFFLINE_CFG (path, default '.pre-commit-config.offline.yaml')
"""

CONNECT_ERR_MARKERS = (
    "CONNECT tunnel failed",
    "Could not resolve host",
    "Failed to fetch",
    "TLS/SSL",
    "timed out",
    "proxy error",
    "Repository not found",
)


def run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd, text=True)
    return proc.returncode


def run_capture(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def looks_like_network_block(stderr: str) -> bool:
    s = stderr.lower()
    return any(m.lower() in s for m in CONNECT_ERR_MARKERS)


def main(argv: list[str]) -> int:
    precommit = os.getenv("PRECOMMIT", "pre-commit")
    offline_cfg = os.getenv("OFFLINE_CFG", ".pre-commit-config.offline.yaml")
    args = argv[1:] if len(argv) > 1 else ["run", "--all-files"]

    code, out, err = run_capture([precommit] + args)
    if code == 0:
        print(out, end="")
        return 0

    if looks_like_network_block(out + "\n" + err) or "fatal: unable to access" in (out + err):
        print(
            "[pre-commit] network/remote blocked; falling back to offline config", file=sys.stderr
        )
        if not Path(offline_cfg).exists():
            print(f"[pre-commit] offline config not found: {offline_cfg}", file=sys.stderr)
            return code or 1
        code2 = run([precommit, args[0], "-c", offline_cfg] + args[1:])
        return 0 if code2 == 0 else code2

    sys.stderr.write(err)
    return code or 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
