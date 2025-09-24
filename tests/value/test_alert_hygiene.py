"""
/**
 * @file: tests/value/test_alert_hygiene.py
 * @description: Ensure alert hygiene enforces cooldown, quiet hours and staleness.
 * @dependencies: pytest, app.value_alerts
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.value_alerts import AlertCandidate, AlertHygiene
from config import settings


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    path = tmp_path / "alerts.sqlite"
    monkeypatch.setattr(settings, "DB_PATH", str(path))
    return path


def test_alert_hygiene_cooldown_and_delta(temp_db) -> None:  # noqa: ANN001
    hygiene = AlertHygiene(
        cooldown_minutes=60,
        min_edge_delta=0.7,
        staleness_fail_minutes=30,
        quiet_hours="23:00-08:00",
    )
    now = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    candidate = AlertCandidate(
        user_id=1,
        match_key="M1",
        market="1X2",
        selection="HOME",
        edge_pct=4.0,
        pulled_at=now - timedelta(minutes=5),
        kickoff_utc=now + timedelta(hours=3),
        user_timezone="Europe/Moscow",
    )
    decision = hygiene.evaluate(candidate, now=now)
    assert decision.should_send and decision.reason == "ok"
    hygiene.record_delivery(candidate)
    decision = hygiene.evaluate(candidate, now=now + timedelta(minutes=10))
    assert not decision.should_send and decision.reason == "cooldown"
    later_candidate = AlertCandidate(
        user_id=1,
        match_key="M1",
        market="1X2",
        selection="HOME",
        edge_pct=4.3,
        pulled_at=now + timedelta(minutes=70),
        kickoff_utc=now + timedelta(hours=5),
        user_timezone="Europe/Moscow",
    )
    decision = hygiene.evaluate(later_candidate, now=now + timedelta(minutes=120))
    assert not decision.should_send and decision.reason == "edge_delta"


def test_alert_hygiene_staleness_and_quiet_hours(temp_db) -> None:  # noqa: ANN001
    hygiene = AlertHygiene(
        cooldown_minutes=10,
        min_edge_delta=0.5,
        staleness_fail_minutes=15,
        quiet_hours="22:00-07:00",
    )
    now = datetime(2024, 1, 1, 22, 30, tzinfo=UTC)
    stale_candidate = AlertCandidate(
        user_id=2,
        match_key="M2",
        market="BTTS",
        selection="YES",
        edge_pct=5.5,
        pulled_at=now - timedelta(minutes=40),
        kickoff_utc=now + timedelta(hours=4),
        user_timezone="UTC",
    )
    decision = hygiene.evaluate(stale_candidate, now=now)
    assert not decision.should_send and decision.reason == "stale_quote"
    fresh_candidate = AlertCandidate(
        user_id=2,
        match_key="M2",
        market="BTTS",
        selection="YES",
        edge_pct=5.5,
        pulled_at=now - timedelta(minutes=5),
        kickoff_utc=now + timedelta(hours=4),
        user_timezone="UTC",
    )
    decision = hygiene.evaluate(fresh_candidate, now=now)
    assert not decision.should_send and decision.reason == "quiet_hours"
