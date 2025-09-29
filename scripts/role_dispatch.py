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
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from logger import logger
from scripts.migrations import run_migrations


def _run_subprocess(
    argv: Sequence[str],
    *,
    allow_failure: bool = False,
    extra_env: Mapping[str, str] | None = None,
) -> int:
    """Execute a subprocess with the provided argv."""
    import subprocess

    logger.info("Запуск команды: %s", " ".join(shlex.quote(arg) for arg in argv))
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(argv, check=False, env=env)
    if result.returncode != 0:
        if allow_failure:
            logger.warning(
                "Команда %s завершилась с кодом %s, продолжаем", argv[0], result.returncode
            )
        else:
            raise SystemExit(result.returncode)
    return result.returncode


def _maybe_run_preflight(role: str) -> None:
    if os.getenv("PRESTART_PREFLIGHT", "0") == "1":
        _run_subprocess(
            (sys.executable, "-m", "scripts.preflight", "--role", role),
        )


def _run_api() -> int:
    _maybe_run_preflight("api")
    _run_subprocess((sys.executable, "-m", "app.migrations.up"), allow_failure=True)
    port = os.getenv("PORT", "80")
    return _run_subprocess(
        (
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ),
        extra_env={"API_ENABLED": "true"},
    )


def _run_worker() -> int:
    _maybe_run_preflight("worker")
    return _run_subprocess((sys.executable, "-m", "scripts.worker"))


def _run_tg_bot() -> int:
    _maybe_run_preflight("bot")
    return _run_subprocess((sys.executable, "-m", "scripts.tg_bot"))


def _run_migrations() -> int:
    return run_migrations(strict=True)


_COMMANDS: Final[dict[str, Callable[[], int | None]]] = {
    "api": _run_api,
    "bot": _run_tg_bot,
    "worker": _run_worker,
    "tgbot": _run_tg_bot,
    "migrate": _run_migrations,
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
    exit_code = handler()
    if exit_code is None:
        exit_code = 0
    raise SystemExit(int(exit_code))


if __name__ == "__main__":
    main()
