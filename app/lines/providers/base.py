"""
@file: app/lines/providers/base.py
@description: Abstract protocol for odds providers returning normalized odds snapshots.
@dependencies: dataclasses, typing
@created: 2025-09-24
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Sequence


@dataclass(slots=True, frozen=True)
class OddsSnapshot:
    provider: str
    pulled_at: datetime
    match_key: str
    league: str | None
    kickoff_utc: datetime
    market: str
    selection: str
    price_decimal: float
    extra: dict[str, Any] | None = None


class LinesProvider(Protocol):
    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[OddsSnapshot]:
        """Return normalized odds snapshots for the requested window."""


__all__ = ["LinesProvider", "OddsSnapshot"]
