"""
@file: app/lines/providers/csv.py
@description: Offline odds provider reading normalized CSV fixtures for deterministic testing.
@dependencies: csv, pathlib, app.lines.mapper
@created: 2025-09-24
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from app.lines.mapper import LinesMapper

from .base import LinesProvider, OddsSnapshot


def _parse_timestamp(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if value is None:
        raise ValueError("Timestamp is required in odds CSV")
    text = str(value).strip()
    if not text:
        raise ValueError("Timestamp is required in odds CSV")
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp in odds CSV: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(slots=True)
class CSVLinesProvider:
    """Read odds fixtures from CSV files stored on disk."""

    fixtures_dir: Path
    mapper: LinesMapper = field(default_factory=LinesMapper)
    provider_name: str = "csv"

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[OddsSnapshot]:
        rows: list[OddsSnapshot] = []
        league_filter = {league.lower(): league for league in leagues or []}
        for path in self._iter_csv_files():
            rows.extend(
                self._load_file(
                    path,
                    date_from=date_from,
                    date_to=date_to,
                    leagues=league_filter,
                )
            )
        rows.sort(key=lambda item: (item.match_key, item.market, item.selection))
        return rows

    def _iter_csv_files(self) -> Iterable[Path]:
        root = Path(self.fixtures_dir)
        if root.is_file():
            yield root
        elif root.is_dir():
            yield from sorted(root.glob("*.csv"))
        else:
            raise FileNotFoundError(f"CSV fixtures path not found: {self.fixtures_dir}")

    def _load_file(
        self,
        path: Path,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: dict[str, str],
    ) -> list[OddsSnapshot]:
        snapshots: list[OddsSnapshot] = []
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = self.mapper.normalize_row(row)
                league = normalized.get("league")
                if leagues and league:
                    league_norm = str(league).lower()
                    if league_norm not in leagues:
                        continue
                kickoff = _parse_timestamp(normalized.get("kickoff_utc"))
                if kickoff < date_from or kickoff > date_to:
                    continue
                pulled_at = _parse_timestamp(normalized.get("pulled_at"))
                price = float(normalized.get("price_decimal"))
                market = str(normalized.get("market") or "").strip()
                selection = str(normalized.get("selection") or "").strip()
                if not market or not selection:
                    continue
                snapshots.append(
                    OddsSnapshot(
                        provider=str(normalized.get("provider") or self.provider_name),
                        pulled_at=pulled_at,
                        match_key=str(normalized.get("match_key")),
                        league=str(league) if league is not None else None,
                        kickoff_utc=kickoff,
                        market=market,
                        selection=selection,
                        price_decimal=price,
                        extra={"source_file": str(path)},
                    )
                )
        return snapshots


__all__ = ["CSVLinesProvider"]
