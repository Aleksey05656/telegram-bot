"""
@file: get_match_prediction.py
@description: CLI utility returning stored prediction probabilities and short explanation for a fixture.
@dependencies: asyncio, argparse, json, sqlalchemy, config, sportmonks.cache, database.db_router
@created: 2025-09-23
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import text

from config import get_settings
from database import get_db_router
from sportmonks.cache import sportmonks_cache


async def _fetch_from_cache(fixture_id: int) -> dict[str, Any] | None:
    cached = await sportmonks_cache.get_or_set(
        "fixture-prediction",
        (fixture_id,),
        "fixtures_upcoming",
        loader=lambda: asyncio.sleep(0, result=None),  # type: ignore[arg-type]
    )
    return cached


async def _fetch_from_db(fixture_id: int) -> dict[str, Any] | None:
    settings = get_settings()
    router = get_db_router(settings)
    async with router.session(read_only=True) as session:
        result = await session.execute(
            text(
                """
                SELECT prob_home_win, prob_draw, prob_away_win, totals_probs, btts_probs, features_snapshot
                FROM predictions
                WHERE fixture_id = :fixture_id
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"fixture_id": fixture_id},
        )
        row = result.first()
        if not row:
            return None
        totals = json.loads(row.totals_probs) if row.totals_probs else {}
        btts = json.loads(row.btts_probs) if row.btts_probs else {}
        features = json.loads(row.features_snapshot) if row.features_snapshot else {}
        return {
            "1x2": {"home": float(row.prob_home_win), "draw": float(row.prob_draw), "away": float(row.prob_away_win)},
            "totals": totals,
            "btts": btts,
            "features": features,
        }


async def get_prediction(fixture_id: int) -> dict[str, Any] | None:
    cached = await _fetch_from_cache(fixture_id)
    if cached:
        return cached
    payload = await _fetch_from_db(fixture_id)
    if payload:
        factors = payload.get("features", {}).get("adjustments", {})
        explanation = _build_explanation(factors)
        payload["explain"] = explanation
    return payload


def _build_explanation(adjustments: dict[str, float]) -> str:
    if not adjustments:
        return "Факторы: базовая модель без корректировок."
    items = sorted(adjustments.items(), key=lambda kv: abs(1 - kv[1]), reverse=True)
    top = items[:3]
    parts = []
    for key, value in top:
        delta = (value - 1.0) * 100
        if "fatigue" in key:
            label = "усталость"
        elif "injuries" in key:
            label = "инжюрии"
        elif "motivation" in key:
            label = "мотивация"
        else:
            label = key
        parts.append(f"{label}: {delta:+.1f}%")
    return "Факторы: " + ", ".join(parts)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get stored prediction for a fixture")
    parser.add_argument("fixture_id", type=int, help="SportMonks fixture id")
    return parser.parse_args()


async def main_async(fixture_id: int) -> None:
    payload = await get_prediction(fixture_id)
    if not payload:
        print("{}")
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    args = _parse_args()
    asyncio.run(main_async(args.fixture_id))


if __name__ == "__main__":
    main()
