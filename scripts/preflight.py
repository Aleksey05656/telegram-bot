"""
/**
 * @file: scripts/preflight.py
 * @description: Deployment preflight checks for Amvera roles.
 * @dependencies: app.config, scripts.prestart, logger
 * @created: 2025-10-29
 */
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

from app.config import get_settings
from logger import logger
from scripts import prestart


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.preflight",
        description="Run preflight checks before launching a service role.",
    )
    parser.add_argument(
        "--mode",
        choices=("strict", "health"),
        default="strict",
        help="Preflight mode: 'strict' runs migrations and health probes, 'health' only runs probes.",
    )
    return parser


async def _run_checks(mode: str) -> None:
    settings = get_settings()
    logger.bind(event="preflight.start", mode=mode).info("Starting preflight checks")

    if mode == "strict":
        prestart.run_migrations(settings)

    await prestart.run_health_checks(settings)
    logger.bind(event="preflight.ok", mode=mode).info("Preflight checks completed")


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    try:
        asyncio.run(_run_checks(args.mode))
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.bind(event="preflight.failed", mode=args.mode, error=str(exc)).error(
            "Preflight checks failed"
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
