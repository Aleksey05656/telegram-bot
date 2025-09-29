"""
@file: scripts/preflight.py
@description: Validate environment prerequisites before launching Amvera roles.
@dependencies: logger
@created: 2025-11-07
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable, Mapping, Sequence

from logger import logger

REQUIRED_ENV: Mapping[str, tuple[str, ...]] = {
    "bot": ("TELEGRAM_BOT_TOKEN",),
}


def _missing_variables(names: Iterable[str]) -> list[str]:
    missing = []
    for name in names:
        value = os.getenv(name, "")
        if value.strip() == "":
            missing.append(name)
    return missing


def _validate_role(role: str) -> int:
    required = REQUIRED_ENV.get(role.lower(), ())
    if not required:
        logger.bind(role=role).info("No preflight requirements for role")
        return 0

    missing = _missing_variables(required)
    if missing:
        logger.bind(role=role, missing=missing).error(
            "Preflight validation failed: required environment variables are absent",
        )
        return os.EX_CONFIG

    logger.bind(role=role).info("Preflight validation successful")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.preflight",
        description="Validate runtime prerequisites for service roles.",
    )
    parser.add_argument(
        "--role",
        help="Role name to validate (falls back to ROLE environment variable).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    role = (args.role or os.getenv("ROLE", "")).strip()
    if not role:
        logger.error("ROLE is required for preflight validation")
        return os.EX_USAGE

    exit_code = _validate_role(role)
    if exit_code != 0:
        return exit_code

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI execution
    raise SystemExit(main())
