"""
/**
 * @file: app/lines/movement.py
 * @description: Helpers to derive line movement trends and closing line information.
 * @dependencies: dataclasses, datetime
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.lines.storage import LineHistoryPoint


@dataclass(slots=True, frozen=True)
class MovementResult:
    trend: str
    closing_price: float | None = None
    closing_pulled_at: datetime | None = None


def analyze_movement(
    history: Sequence[LineHistoryPoint],
    *,
    kickoff: datetime,
    window_minutes: int,
    tolerance_pct: float = 0.5,
) -> MovementResult:
    if not history:
        return MovementResult(trend="→")
    ordered = sorted(history, key=lambda item: item.pulled_at)
    first = ordered[0]
    last = ordered[-1]
    trend = _classify_trend(first.price_decimal, last.price_decimal, tolerance_pct)
    closing = _closing_point(ordered, kickoff=kickoff, window_minutes=window_minutes)
    if closing is None:
        return MovementResult(trend=trend)
    return MovementResult(
        trend=trend,
        closing_price=closing.price_decimal,
        closing_pulled_at=closing.pulled_at,
    )


def _classify_trend(start_price: float, end_price: float, tolerance_pct: float) -> str:
    if start_price <= 0 or end_price <= 0:
        return "→"
    delta = end_price - start_price
    threshold = start_price * (tolerance_pct / 100.0)
    if delta > threshold:
        return "↗︎"
    if delta < -threshold:
        return "↘︎"
    return "→"


def _closing_point(
    history: Sequence[LineHistoryPoint],
    *,
    kickoff: datetime,
    window_minutes: int,
) -> LineHistoryPoint | None:
    if window_minutes <= 0:
        return None
    window = timedelta(minutes=window_minutes)
    kickoff_utc = kickoff.astimezone(UTC)
    window_seconds = window.total_seconds()
    candidates = []
    for point in history:
        delta = kickoff_utc - point.pulled_at.astimezone(UTC)
        if delta.total_seconds() < 0:
            continue
        if delta.total_seconds() <= window_seconds:
            candidates.append(point)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.pulled_at)


__all__ = ["MovementResult", "analyze_movement"]
