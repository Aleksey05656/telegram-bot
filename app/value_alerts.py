"""
/**
 * @file: app/value_alerts.py
 * @description: Alert hygiene helpers enforcing cooldown, quiet hours and staleness policies.
 * @dependencies: dataclasses, datetime, zoneinfo, app.bot.storage
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from app.bot.storage import (
    get_last_value_alert_sent,
    list_recent_value_alerts,
    record_value_alert_sent,
)


class AlertDecision(NamedTuple):
    should_send: bool
    reason: str


@dataclass(slots=True)
class AlertCandidate:
    user_id: int
    match_key: str
    market: str
    selection: str
    edge_pct: float
    pulled_at: datetime
    kickoff_utc: datetime
    user_timezone: str = "UTC"


class AlertHygiene:
    """Enforce anti-spam rules for value alerts."""

    def __init__(
        self,
        *,
        cooldown_minutes: int,
        min_edge_delta: float,
        staleness_fail_minutes: int,
        quiet_hours: str | None = None,
        update_delta: float = 1.0,
        max_updates: int = 3,
    ) -> None:
        self._cooldown = max(int(cooldown_minutes), 0)
        self._min_edge_delta = float(min_edge_delta)
        self._staleness = max(int(staleness_fail_minutes), 0)
        self._quiet_hours = _parse_quiet_hours(quiet_hours)
        self._update_delta = max(float(update_delta), 0.0)
        self._max_updates = max(int(max_updates), 0)

    def evaluate(self, candidate: AlertCandidate, *, now: datetime) -> AlertDecision:
        now = now.astimezone(UTC)
        if self._staleness and now - candidate.pulled_at > timedelta(minutes=self._staleness):
            return AlertDecision(False, "stale_quote")
        if self._is_quiet(candidate, now=now):
            return AlertDecision(False, "quiet_hours")
        last = get_last_value_alert_sent(
            candidate.user_id,
            match_key=candidate.match_key,
            market=candidate.market,
            selection=candidate.selection,
        )
        if self._max_updates:
            history = [
                row
                for row in list_recent_value_alerts(
                    candidate.user_id, limit=self._max_updates
                )
                if row.get("match_key") == candidate.match_key
                and row.get("market") == candidate.market
                and row.get("selection") == candidate.selection
            ]
            if len(history) >= self._max_updates:
                return AlertDecision(False, "max_updates")
        if last:
            last_sent = _coerce_datetime(last.get("sent_at"))
            if self._cooldown and now - last_sent < timedelta(minutes=self._cooldown):
                return AlertDecision(False, "cooldown")
            last_edge = float(last.get("edge_pct", 0.0))
            required_delta = max(self._min_edge_delta, self._update_delta)
            if candidate.edge_pct - last_edge < required_delta:
                return AlertDecision(False, "edge_delta")
        return AlertDecision(True, "ok")

    def record_delivery(self, candidate: AlertCandidate) -> None:
        record_value_alert_sent(
            candidate.user_id,
            match_key=candidate.match_key,
            market=candidate.market,
            selection=candidate.selection,
            edge_pct=candidate.edge_pct,
        )

    def recent_deliveries(self, user_id: int, *, limit: int = 5) -> list[dict[str, object]]:
        return list_recent_value_alerts(user_id, limit=limit)

    def _is_quiet(self, candidate: AlertCandidate, *, now: datetime) -> bool:
        if not self._quiet_hours:
            return False
        start, end = self._quiet_hours
        tz = _safe_timezone(candidate.user_timezone)
        local_now = now.astimezone(tz)
        current_time = local_now.timetz()
        return _within_quiet_hours(current_time, start, end)


def _parse_quiet_hours(value: str | None) -> tuple[time, time] | None:
    if not value:
        return None
    try:
        start_raw, end_raw = value.split("-", 1)
        start_time = datetime.strptime(start_raw.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_raw.strip(), "%H:%M").time()
        return start_time, end_time
    except ValueError:
        return None


def _within_quiet_hours(current: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _safe_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).astimezone(UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


__all__ = [
    "AlertCandidate",
    "AlertDecision",
    "AlertHygiene",
]
