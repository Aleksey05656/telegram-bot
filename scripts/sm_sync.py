"""
@dependencies: asyncio, click, datetime
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import click

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.data_providers.sportmonks import SportmonksClient, SportmonksProvider, SportmonksClientConfig
from app.data_providers.sportmonks.cache import SportmonksETagCache
from app.data_providers.sportmonks.metrics import (
    sm_etl_rows_upserted_total,
    sm_sync_failures_total,
    update_last_sync,
)
from app.data_providers.sportmonks.repository import SportmonksRepository
from app.data_providers.sportmonks.schemas import FixtureDTO
from app.mapping.sportmonks_map import SportmonksMappingRepository, TeamMappingConflict
from logger import logger


@click.command()
@click.option("--mode", type=click.Choice(["backfill", "incremental"]), required=True)
@click.option("--from", "from_", type=click.DateTime(formats=["%Y-%m-%d"]), help="Start date inclusive (UTC)")
@click.option("--to", "to", type=click.DateTime(formats=["%Y-%m-%d"]), help="End date inclusive (UTC)")
@click.option("--leagues", type=str, help="Comma separated list of league identifiers")
@click.option("--window-days", type=int, help="Override incremental window in days")
@click.option("--dry-run/--no-dry-run", default=False, help="Run against local fixtures without network access")
def main(
    mode: str,
    from_: datetime | None,
    to: datetime | None,
    leagues: str | None,
    window_days: int | None,
    dry_run: bool,
) -> None:
    """Execute Sportmonks synchronization pipeline."""

    league_ids = _parse_leagues(leagues)
    asyncio.run(_execute(mode, from_, to, league_ids, window_days, dry_run))


async def _execute(
    mode: str,
    date_from: datetime | None,
    date_to: datetime | None,
    league_ids: Sequence[str],
    window_days: int | None,
    dry_run: bool,
) -> None:
    repository = SportmonksRepository()
    mapping_repository = SportmonksMappingRepository()
    client: SportmonksClient | None = None
    provider: SportmonksProvider | None = None

    if dry_run:
        config = SportmonksClientConfig.from_env()
    else:
        client = SportmonksClient()
        provider = SportmonksProvider(
            client,
            etag_cache=SportmonksETagCache(repository, client.config.cache_ttl_seconds),
        )
        config = client.config

    try:
        resolved_from, resolved_to = _resolve_window(mode, date_from, date_to, window_days, config)
    except ValueError as err:
        raise click.UsageError(str(err)) from err

    logger.info(
        "Starting Sportmonks sync",
        extra={
            "mode": mode,
            "from": resolved_from.isoformat(),
            "to": resolved_to.isoformat(),
            "league_ids": league_ids,
            "dry_run": dry_run,
        },
    )

    pulled_at = datetime.now(tz=timezone.utc)
    all_teams: list[Any] = []

    try:
        if dry_run:
            dataset = _load_offline_dataset(resolved_from, resolved_to, league_ids, config)
            fixtures = dataset["fixtures"]
            all_teams = list(dataset["teams"])
            standings = dataset["standings"]
            injuries = dataset["injuries"]
            fixture_count = len(fixtures)
            teams_total = len(all_teams)
            standings_total = len(standings)
            injuries_total = len(injuries)
            leagues_to_fetch = sorted({f.league_id for f in fixtures if f.league_id})
            sm_etl_rows_upserted_total.labels(table="sm_fixtures").inc(fixture_count)
            sm_etl_rows_upserted_total.labels(table="sm_teams").inc(teams_total)
            sm_etl_rows_upserted_total.labels(table="sm_standings").inc(standings_total)
            sm_etl_rows_upserted_total.labels(table="sm_injuries").inc(injuries_total)
        else:
            assert provider is not None
            fixtures = await provider.fetch_fixtures(resolved_from, resolved_to, league_ids=league_ids)
            fixture_count = repository.upsert_fixtures(fixtures, pulled_at=pulled_at)
            sm_etl_rows_upserted_total.labels(table="sm_fixtures").inc(fixture_count)

            leagues_to_fetch = sorted({f.league_id for f in fixtures if f.league_id})
            teams_total = 0
            for league_id in leagues_to_fetch:
                teams = await provider.fetch_teams(str(league_id))
                all_teams.extend(teams)
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

        collision_status = _handle_team_collisions(all_teams)

        logger.info(
            "Sportmonks sync completed",
            extra={
                "mode": mode,
                "fixtures": fixture_count,
                "teams": teams_total,
                "standings": standings_total,
                "injuries": injuries_total,
                "leagues": leagues_to_fetch,
                "collisions": collision_status,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        sm_sync_failures_total.labels(mode=mode).inc()
        logger.exception("Sportmonks sync failed", extra={"mode": mode, "error": str(exc)})
        raise
    finally:
        if client is not None:
            await client.aclose()
        mapping_repository.ensure_tables()


def _resolve_window(
    mode: str,
    date_from: datetime | None,
    date_to: datetime | None,
    window_days: int | None,
    config: SportmonksClientConfig,
) -> tuple[datetime, datetime]:
    if mode == "backfill":
        if not date_from or not date_to:
            raise ValueError("backfill mode requires --from and --to arguments")
        return _normalize_day(date_from), _normalize_day(date_to)

    days = window_days if window_days is not None else config.default_timewindow_days
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


def _load_offline_dataset(
    date_from: datetime,
    date_to: datetime,
    league_ids: Sequence[str],
    config: SportmonksClientConfig,
) -> dict[str, list[Any]]:
    from app.data_providers.sportmonks import provider as provider_module

    root = Path(__file__).resolve().parents[1]
    fixtures_path = root / "tests" / "fixtures" / "sm" / "fixtures.json"
    teams_path = root / "tests" / "fixtures" / "sm" / "teams.json"
    standings_path = root / "tests" / "fixtures" / "sm" / "standings.json"
    injuries_path = root / "tests" / "fixtures" / "sm" / "injuries.json"

    payloads = {
        "fixtures": json.loads(fixtures_path.read_text(encoding="utf-8")),
        "teams": json.loads(teams_path.read_text(encoding="utf-8")),
        "standings": json.loads(standings_path.read_text(encoding="utf-8")),
        "injuries": json.loads(injuries_path.read_text(encoding="utf-8")),
    }

    allowed = _offline_allowed_set(league_ids, config)

    fixtures: list[FixtureDTO] = []
    for record in provider_module._iter_records(payloads["fixtures"]):  # type: ignore[attr-defined]
        dto = provider_module._parse_fixture(record)  # type: ignore[attr-defined]
        if not dto:
            continue
        kickoff = dto.kickoff_utc
        if kickoff and not (date_from <= kickoff <= date_to):
            continue
        if not provider_module.SportmonksProvider._is_league_allowed(dto.league_id, allowed):  # type: ignore[attr-defined]
            continue
        fixtures.append(dto)

    teams: list[Any] = []
    for record in provider_module._iter_records(payloads["teams"]):  # type: ignore[attr-defined]
        dto = provider_module._parse_team(record)  # type: ignore[attr-defined]
        if not dto:
            continue
        teams.append(dto)

    standings: list[Any] = []
    league_pairs = _unique_league_seasons(fixtures)
    for record in provider_module._iter_records(payloads["standings"]):  # type: ignore[attr-defined]
        dto = provider_module._parse_standing(record)  # type: ignore[attr-defined]
        if not dto:
            continue
        if (dto.league_id, dto.season_id) not in league_pairs:
            continue
        standings.append(dto)

    injuries: list[Any] = []
    for record in provider_module._iter_records(payloads["injuries"]):  # type: ignore[attr-defined]
        dto = provider_module._parse_injury(record)  # type: ignore[attr-defined]
        if not dto:
            continue
        if not provider_module.SportmonksProvider._is_league_allowed(dto.league_id, allowed):  # type: ignore[attr-defined]
            continue
        injuries.append(dto)

    return {
        "fixtures": fixtures,
        "teams": teams,
        "standings": standings,
        "injuries": injuries,
    }


def _offline_allowed_set(
    league_ids: Sequence[str],
    config: SportmonksClientConfig,
) -> set[str]:
    if league_ids:
        return {str(item) for item in league_ids if str(item)}
    if config.leagues_allowlist:
        return {str(item) for item in config.leagues_allowlist if str(item)}
    return set()


def _handle_team_collisions(teams: Sequence[Any]) -> str:
    if not teams:
        return "skipped"
    collisions: list[TeamMappingConflict] = []
    grouped: dict[str, list[int]] = defaultdict(list)
    for team in teams:
        grouped[getattr(team, "name_normalized", "")].append(int(team.team_id))
    for name_norm, ids in grouped.items():
        unique = sorted(set(ids))
        if len(unique) > 1 and name_norm:
            collisions.append(
                TeamMappingConflict(
                    sm_team_id=unique[0],
                    name_norm=name_norm,
                    candidates=tuple(unique),
                )
            )
    if not collisions:
        return "clean"
    reports_dir = Path("reports") / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)
    destination = reports_dir / "sportmonks_team_collisions.csv"
    SportmonksMappingRepository.export_conflicts(collisions, destination)
    logger.warning(
        "Detected Sportmonks team name collisions", extra={"count": len(collisions), "report": str(destination)}
    )
    return "handled"


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
