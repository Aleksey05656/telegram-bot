"""
@file: test_windows.py
@description: Validate window resolution logic for Sportmonks sync CLI.
@dependencies: pytest, datetime
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest

from app.data_providers.sportmonks.client import SportmonksClientConfig
import scripts.sm_sync as sm_sync


class _FixedDateTime(datetime):
    """Helper to freeze datetime.now within the sm_sync module."""

    _now = datetime(2025, 2, 14, 12, 30, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
        if tz is None:
            return cls._now.replace(tzinfo=None)
        return cls._now.astimezone(tz)


def _config(window_days: int = 2) -> SportmonksClientConfig:
    return SportmonksClientConfig(
        api_token="token",
        base_url="https://example.test",
        timeout=1.0,
        retry_attempts=0,
        backoff_base=0.0,
        rps_limit=1.0,
        default_timewindow_days=window_days,
        leagues_allowlist=(),
        cache_ttl_seconds=0,
    )


def test_incremental_window_uses_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sm_sync, "datetime", _FixedDateTime)
    start, end = sm_sync._resolve_window("incremental", None, None, None, _config(3))
    assert start == datetime(2025, 2, 11, tzinfo=UTC)
    assert end == datetime(2025, 2, 17, tzinfo=UTC)


def test_incremental_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sm_sync, "datetime", _FixedDateTime)
    start, end = sm_sync._resolve_window("incremental", None, None, 1, _config(5))
    assert start == datetime(2025, 2, 13, tzinfo=UTC)
    assert end == datetime(2025, 2, 15, tzinfo=UTC)


def test_backfill_requires_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sm_sync, "datetime", _FixedDateTime)
    with pytest.raises(ValueError):
        sm_sync._resolve_window("backfill", None, None, None, _config())

    start, end = sm_sync._resolve_window(
        "backfill",
        datetime(2025, 2, 10),
        datetime(2025, 2, 12, tzinfo=timezone.utc),
        None,
        _config(),
    )
    assert start == datetime(2025, 2, 10, tzinfo=UTC)
    assert end == datetime(2025, 2, 12, tzinfo=UTC)


def test_negative_window_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sm_sync, "datetime", _FixedDateTime)
    with pytest.raises(ValueError):
        sm_sync._resolve_window("incremental", None, None, -1, _config())
