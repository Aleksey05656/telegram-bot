"""
@file: update_upcoming.py
@description: Cron entrypoint to refresh upcoming fixtures, build features, run simulations and persist results.
@dependencies: asyncio, argparse, datetime, config, sportmonks package, services.feature_builder, services.simulator
@created: 2025-09-23
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta
from config import get_settings
from services.feature_builder import FeatureBundle, feature_builder
from services.simulator import simulate_markets
from sportmonks import SportMonksClient, SportMonksEndpoints
from sportmonks.cache import sportmonks_cache
from sportmonks.repository import sportmonks_repository
from sportmonks.schemas import Fixture, LineupPlayerDetail, TeamStats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update upcoming fixtures from SportMonks")
    parser.add_argument("--days", type=int, default=3, help="How many days ahead to refresh")
    return parser.parse_args()


async def _extract_team_stats(fixture: Fixture, team_id: int | None) -> TeamStats | None:
    if not team_id:
        return None
    stats_raw = fixture.statistics.get(str(team_id), {}) if fixture.statistics else {}
    if not isinstance(stats_raw, dict):
        return None
    def _maybe_float(key: str) -> float | None:
        value = stats_raw.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _maybe_int(key: str) -> int | None:
        value = stats_raw.get(key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return TeamStats(
        team_id=int(team_id),
        fixture_id=fixture.id,
        xg=_maybe_float("expected_goals") or _maybe_float("xG"),
        xga=_maybe_float("expected_goals_against") or _maybe_float("xGA"),
        shots=_maybe_int("shots_total") or _maybe_int("shots"),
        shots_on_target=_maybe_int("shots_on_target"),
        possession=_maybe_float("possession_percentage") or _maybe_float("possession"),
        corners=_maybe_int("corners") or _maybe_int("corners_total"),
        fouls=_maybe_int("fouls") or _maybe_int("fouls_committed"),
        yellow_cards=_maybe_int("yellow_cards"),
        red_cards=_maybe_int("red_cards"),
    )


def _count_key_absences(players: list[LineupPlayerDetail]) -> int:
    return sum(1 for player in players if player.sidelined)


def _confidence(bundle: FeatureBundle, degraded: bool) -> float:
    base = 0.88
    if bundle.degraded or degraded:
        base -= 0.1
    penalty = sum(abs(1.0 - value) for value in bundle.adjustments.values()) * 0.05
    return max(0.25, min(0.98, base - penalty))


async def refresh_upcoming(days: int) -> None:
    settings = get_settings()
    client = SportMonksClient()
    endpoints = SportMonksEndpoints(client=client)
    today = date.today()
    start = today.isoformat()
    end = (today + timedelta(days=days)).isoformat()

    fixtures = await endpoints.fixtures_between(start, end)
    fixture_ids = [fixture.id for fixture in fixtures]
    expected_lineups = await endpoints.expected_lineups(fixture_ids)

    for fixture in fixtures:
        card = await endpoints.fixture_card(fixture.id)
        lineup_override, degraded_lineup = expected_lineups.get(fixture.id, ([], False))
        if lineup_override:
            card.lineups = lineup_override
        degraded = degraded_lineup or any(value.degraded_mode for value in card.xg_fixture)
        home_players = [p for p in card.lineups if p.team_id == card.home_team_id]
        away_players = [p for p in card.lineups if p.team_id == card.away_team_id]
        context = {
            "home_rest_days": settings.SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS,
            "away_rest_days": settings.SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS,
            "home_key_absences": _count_key_absences(home_players),
            "away_key_absences": _count_key_absences(away_players),
            "home_motivation": 0.0,
            "away_motivation": 0.0,
        }
        home_stats = await _extract_team_stats(card, card.home_team_id)
        away_stats = await _extract_team_stats(card, card.away_team_id)
        bundle = feature_builder.build(card, home_stats=home_stats, away_stats=away_stats, context=context)
        markets = simulate_markets(bundle.lambda_home, bundle.lambda_away, settings.SIM_RHO, settings.SIM_N)
        confidence = _confidence(bundle, degraded)
        features_snapshot = bundle.snapshot | {"adjustments": bundle.adjustments}

        await sportmonks_repository.upsert_fixture(card)
        await sportmonks_repository.store_prediction(
            fixture=card,
            lambda_home=bundle.lambda_home,
            lambda_away=bundle.lambda_away,
            markets=markets,
            confidence=confidence,
            model_version=settings.MODEL_VERSION or settings.MODEL_VERSION_FORMAT,
            features_snapshot=features_snapshot,
        )

        cached_payload = {
            "fixture": card.model_dump(mode="json"),
            "markets": markets,
            "confidence": confidence,
            "generated_at": datetime.utcnow().isoformat(),
        }
        await sportmonks_cache.set_ttl(
            "fixture-prediction",
            (card.id,),
            "fixtures_upcoming",
            cached_payload,
        )

        odds = await endpoints.odds_for_fixture(card.id, inplay=False)
        odds += await endpoints.odds_for_fixture(card.id, inplay=True)
        if odds:
            await sportmonks_repository.store_odds(odds)

    await client.close()


async def main_async(days: int) -> None:
    await refresh_upcoming(days)


def main() -> None:
    args = _parse_args()
    asyncio.run(main_async(args.days))


if __name__ == "__main__":
    main()
