"""
/**
 * @file: tests/scripts/test_preflight.py
 * @description: Unit tests for the deployment preflight checks.
 * @dependencies: scripts.preflight, pytest
 * @created: 2025-10-29
 */
"""

from __future__ import annotations

from types import SimpleNamespace
import pytest

import scripts.preflight as preflight


@pytest.mark.asyncio
@pytest.mark.bot_smoke
async def test_run_checks_strict_invokes_migrations_and_health(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(preflight, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        preflight.prestart,
        "run_migrations",
        lambda settings: calls.append("migrations"),
    )

    async def _fake_health(settings):
        calls.append("health")

    monkeypatch.setattr(preflight.prestart, "run_health_checks", _fake_health)

    await preflight._run_checks("strict")
    assert calls == ["migrations", "health"]


@pytest.mark.asyncio
async def test_run_checks_health_skips_migrations(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(preflight, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        preflight.prestart,
        "run_migrations",
        lambda settings: calls.append("migrations"),
    )

    async def _fake_health(settings):
        calls.append("health")

    monkeypatch.setattr(preflight.prestart, "run_health_checks", _fake_health)

    await preflight._run_checks("health")
    assert calls == ["health"]


def test_main_propagates_failures_with_exit_code(monkeypatch):
    class StubLogger:
        def __init__(self) -> None:
            self.records: list[tuple[str, dict[str, str]]] = []

        def bind(self, **extra):  # noqa: D401 - structured logging helper
            self.records.append(("bind", extra))
            return self

        def info(self, message: str) -> None:  # noqa: D401 - structured logging helper
            self.records.append(("info", {"message": message}))

        def error(self, message: str) -> None:  # noqa: D401 - structured logging helper
            self.records.append(("error", {"message": message}))

    stub_logger = StubLogger()
    monkeypatch.setattr(preflight, "logger", stub_logger)

    def _raise(_coroutine):  # noqa: D401 - substitute for asyncio.run
        raise RuntimeError("boom")

    monkeypatch.setattr(preflight.asyncio, "run", _raise)

    with pytest.raises(SystemExit) as excinfo:
        preflight.main(["--mode", "strict"])

    assert excinfo.value.code == 1
    assert ("error", {"message": "Preflight checks failed"}) in stub_logger.records
