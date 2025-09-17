"""
@file: tests/security/test_masking.py
@description: Security checks ensuring DSN masking in logs.
@dependencies: database.db_router, scripts.prestart, workers.redis_factory
@created: 2025-09-23
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from database.db_router import mask_dsn
import scripts.prestart as prestart
import workers.redis_factory as redis_factory


def test_mask_dsn_hides_credentials() -> None:
    masked = mask_dsn("postgresql+asyncpg://user:pass@localhost:5432/db")
    assert "user" not in masked
    assert "pass" not in masked
    assert "***" in masked


def test_run_migrations_uses_masked_dsn(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class StubLogger:
        def bind(self, **kwargs):  # noqa: D401 - mimic loguru API
            calls.append(kwargs)
            return self

        def info(self, message):  # noqa: D401 - log sink
            calls.append({"level": "info", "message": message})

        def error(self, message):  # pragma: no cover - not triggered
            calls.append({"level": "error", "message": message})

    monkeypatch.setattr(prestart, "logger", StubLogger())
    monkeypatch.setattr(prestart.command, "upgrade", lambda *args, **kwargs: None)
    settings = SimpleNamespace(DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db")
    prestart.run_migrations(settings)
    masked_dsns = [entry["dsn"] for entry in calls if "dsn" in entry]
    assert masked_dsns
    assert all("***" in value for value in masked_dsns)


@pytest.mark.asyncio
async def test_redis_health_check_logs_masked_url(monkeypatch) -> None:
    class StubLogger:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        def bind(self, **kwargs):
            self.records.append(kwargs)
            return self

        def info(self, message, *args):
            self.records.append({"message": message, "args": args})

        def warning(self, message, *args):  # pragma: no cover - not used here
            self.records.append({"warning": message, "args": args})

        def debug(self, message, *args):  # pragma: no cover - not used in assertion
            self.records.append({"debug": message, "args": args})

    class DummyRedis:
        async def ping(self) -> None:
            return None

        async def close(self) -> None:
            return None

    logger_stub = StubLogger()
    monkeypatch.setattr(redis_factory, "logger", logger_stub)
    monkeypatch.setattr(redis_factory, "from_url", lambda *args, **kwargs: DummyRedis())
    factory = redis_factory.RedisFactory(url="redis://:secret@localhost:6379/0")
    await factory.health_check()
    masked_entries = [entry for entry in logger_stub.records if "url" in entry]
    assert masked_entries
    assert all("***" in entry["url"] for entry in masked_entries)

