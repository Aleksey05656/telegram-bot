"""/**
 * @file: test_db_url.py
 * @description: Tests for the database URL builder utility.
 * @dependencies: os, pytest, tgbotapp.db_url
 * @created: 2025-10-02
 */
Tests for :mod:`tgbotapp.db_url`.
"""

from __future__ import annotations

import pytest

from tgbotapp.db_url import build_db_url


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure database-related environment variables are isolated per test."""

    keys = ["DATABASE_URL", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME"]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_returns_database_url_when_defined(monkeypatch: pytest.MonkeyPatch) -> None:
    """The explicit ``DATABASE_URL`` value takes priority."""

    expected = "postgresql+asyncpg://user:pass@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", expected)
    monkeypatch.setenv("DB_PASSWORD", "should_not_be_used")

    assert build_db_url() == expected


def test_builds_url_from_individual_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """The URL is assembled from individual credentials when needed."""

    monkeypatch.setenv("DB_USER", "bot")
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word")
    monkeypatch.setenv("DB_HOST", "db.internal")
    monkeypatch.setenv("DB_NAME", "telegram")

    url = build_db_url()

    assert url == "postgresql+asyncpg://bot:p%40ss%2Fword@db.internal:5432/telegram"


def test_returns_none_when_credentials_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials result in ``None`` to indicate unavailable DSN."""

    monkeypatch.setenv("DB_USER", "bot")
    monkeypatch.setenv("DB_PASSWORD", "secret")

    assert build_db_url() is None
