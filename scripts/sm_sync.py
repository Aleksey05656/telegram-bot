"""
@file: sm_sync.py
@description: CLI entry point for Sportmonks backfill and incremental ETL jobs.
@dependencies: asyncio, click, datetime
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from typing import Iterable, Sequence

import click

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.data_providers.sportmonks import SportmonksClient, SportmonksProvider
from app.data_providers.sportmonks.metrics import (
    sm_etl_rows_upserted_total,
    sm_sync_failures_total,
    update_last_sync,
)
from app.data_providers.sportmonks.repository import SportmonksRepository
from app.data_providers.sportmonks.schemas import FixtureDTO
from app.mapping.sportmonks_map import SportmonksMappingRepository
from logger import logger


@click.command()
@click.option("--mode", type=click.Choice(["backfill", "incremental"]), required=True)
@click.option("--from", "from_", type=click.DateTime(formats=["%Y-%m-%d"]), help="Start date inclusive (UTC)")
@click.option("--to", "to", type=click.DateTime(formats=["%Y-%m-%d"]), help="End date inclusive (UTC)")
@click.option("--leagues", type=str, help="Comma separated list of league identifiers")
@click.option("--window-days", type=int, help="Override incremental window in days")
def main(mode: str, from_: datetime | None, to: datetime | None, leagues: str | None, window_days: int | None) -> None:
    """Execute Sportmonks synchronization pipeline."""

    league_ids = _parse_leagues(leagues)
    asyncio.run(_execute(mode, from_, to, league_ids, window_days))


async def _execute(
    mode: str,
    date_from: datetime | None,
    date_to: datetime | None,
    league_ids: Sequence[str],
    window_days: int | None,
) -> None:
    client = SportmonksClient()
    provider = SportmonksProvider(client)
    repository = SportmonksRepository()
    mapping_repository = SportmonksMappingRepository()

    try:
        resolved_from, resolved_to = _resolve_window(mode, date_from, date_to, window_days, client)
    except ValueError as err:
        raise click.UsageError(str(err)) from err

    logger.info(
        "Starting Sportmonks sync",
        extra={
            "mode": mode,
            "from": resolved_from.isoformat(),
            "to": resolved_to.isoformat(),
            "league_ids": league_ids,
        },
    )

    pulled_at = datetime.now(tz=timezone.utc)

    try:
        fixtures = await provider.fetch_fixtures(resolved_from, resolved_to, league_ids=league_ids)
        fixture_count = repository.upsert_fixtures(fixtures, pulled_at=pulled_at)
        sm_etl_rows_upserted_total.labels(table="sm_fixtures").inc(fixture_count)

        leagues_to_fetch = sorted({f.league_id for f in fixtures if f.league_id})
        teams_total = 0
        for league_id in leagues_to_fetch:
            teams = await provider.fetch_teams(str(league_id))
            teams_total += repository.upsert_teams(teams, pulled_at=pulled_at)
        sm_etl_rows_upserted_total.labels(table="sm_teams").inc(teams_total)

        standings_total = 0
        for pair in _unique_league_seasons(fixtures):
            league_id, season_id = pair
            rows = await provider.fetch_standings(str(league_id), str(season_id))
            standings_total += repository.upsert_standings(rows, pulled_at=pulled_at)
        sm_etl_rows_upserted_total.labels(table="sm_standings").inc(standings_total)

        injuries = await provider.fetch_injuries(resolved_from, resolved_to, league_ids=league_ids)
        injuries_total = repository.upsert_injuries(injuries, pulled_at=pulled_at)
        sm_etl_rows_upserted_total.labels(table="sm_injuries").inc(injuries_total)

        repository.upsert_meta("last_sync_mode", mode)
        repository.upsert_meta("last_sync_from", resolved_from.isoformat())
        repository.upsert_meta("last_sync_to", resolved_to.isoformat())
        repository.upsert_meta("last_sync_completed_at", pulled_at.isoformat())

        update_last_sync(mode, pulled_at)
        logger.info(
            "Sportmonks sync completed",
            extra={
                "mode": mode,
                "fixtures": fixture_count,
                "teams": teams_total,
                "standings": standings_total,
                "injuries": injuries_total,
                "leagues": leagues_to_fetch,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        sm_sync_failures_total.labels(mode=mode).inc()
        logger.exception("Sportmonks sync failed", extra={"mode": mode, "error": str(exc)})
        raise
    finally:
        await client.aclose()
        mapping_repository.ensure_tables()


def _resolve_window(
    mode: str,
    date_from: datetime | None,
    date_to: datetime | None,
    window_days: int | None,
    client: SportmonksClient,
) -> tuple[datetime, datetime]:
    if mode == "backfill":
        if not date_from or not date_to:
            raise ValueError("backfill mode requires --from and --to arguments")
        return _normalize_day(date_from), _normalize_day(date_to)

    days = window_days if window_days is not None else client.config.default_timewindow_days
    if days < 0:
        raise ValueError("window-days must be non-negative")
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=days)
    end = now + timedelta(days=days)
    return _normalize_day(start), _normalize_day(end)


def _normalize_day(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_leagues(raw: str | None) -> Sequence[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _unique_league_seasons(fixtures: Iterable[FixtureDTO]) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for fixture in fixtures:
        if fixture.league_id is None or fixture.season_id is None:
            continue
        pairs.add((fixture.league_id, fixture.season_id))
    return pairs


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
