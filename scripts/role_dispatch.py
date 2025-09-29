"""
@file: scripts/role_dispatch.py
@description: Safe dispatcher for launching Amvera workloads without shell interpolation issues.
@dependencies: scripts.preflight, app.migrations.up, scripts.worker, scripts.tg_bot, uvicorn
@created: 2025-11-03
"""

from __future__ import annotations

import os
import shlex
import sys
from collections.abc import Callable, Sequence
from typing import Final

from logger import logger


def _run_subprocess(argv: Sequence[str], *, allow_failure: bool = False) -> None:
    """Execute a subprocess with the provided argv."""
    import subprocess

    logger.info("Запуск команды: %s", " ".join(shlex.quote(arg) for arg in argv))
    result = subprocess.run(argv, check=False)
    if result.returncode != 0:
        if allow_failure:
            logger.warning(
                "Команда %s завершилась с кодом %s, продолжаем", argv[0], result.returncode
            )
        else:
            raise SystemExit(result.returncode)


def _maybe_run_preflight() -> None:
    if os.getenv("PRESTART_PREFLIGHT", "0") == "1":
        _run_subprocess((sys.executable, "-m", "scripts.preflight", "--mode", "strict"))


def _run_api() -> None:
    _maybe_run_preflight()
    _run_subprocess((sys.executable, "-m", "app.migrations.up"), allow_failure=True)
    port = os.getenv("PORT", "80")
    _run_subprocess(
        (
            sys.executable,
            "-m",
            "uvicorn",
            "app.api:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        )
    )


def _run_worker() -> None:
    _maybe_run_preflight()
    _run_subprocess((sys.executable, "-m", "scripts.worker"))


def _run_tg_bot() -> None:
    _run_subprocess((sys.executable, "-m", "scripts.tg_bot"))


_COMMANDS: Final[dict[str, Callable[[], None]]] = {
    "api": _run_api,
    "worker": _run_worker,
    "tgbot": _run_tg_bot,
}


def main() -> None:
    role = os.getenv("ROLE", "").strip()
    if not role:
        raise SystemExit("ROLE environment variable must be set")

    handler = _COMMANDS.get(role)
    if handler is None:
        valid = ", ".join(sorted(_COMMANDS))
        raise SystemExit(f"Unknown ROLE={role!r}. Use one of: {valid}")

    logger.info("Выбран режим запуска ROLE=%s", role)
    handler()


if __name__ == "__main__":
    main()
