"""
@file: diagtools/value_check.py
@description: CLI utility to validate odds provider snapshots and basic value metrics.
@dependencies: asyncio, config, app.value_service
@created: 2025-09-24
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Sequence

from config import settings

from app.bot.services import PredictionFacade
from app.lines.mapper import LinesMapper
from app.lines.providers import CSVLinesProvider, HTTPLinesProvider
from app.value_detector import ValueDetector
from app.value_service import ValueService


@dataclass(slots=True)
class _DummyProvider:
    mapper: LinesMapper

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[Any]:  # pragma: no cover - fallback path
        return []


def _parse_markets() -> tuple[str, ...]:
    raw = getattr(settings, "VALUE_MARKETS", "1X2,OU_2_5,BTTS")
    return tuple(item.strip() for item in str(raw).split(",") if item.strip())


def _build_detector() -> ValueDetector:
    return ValueDetector(
        min_edge_pct=float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0)),
        min_confidence=float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6)),
        max_picks=int(getattr(settings, "VALUE_MAX_PICKS", 5)),
        markets=_parse_markets(),
        overround_method=str(getattr(settings, "ODDS_OVERROUND_METHOD", "proportional")),
    )


def _create_provider(mapper: LinesMapper):
    provider_type = str(getattr(settings, "ODDS_PROVIDER", "dummy") or "dummy").lower()
    if provider_type == "csv":
        fixtures_root = os.getenv("ODDS_FIXTURES_PATH")
        if fixtures_root:
            path = Path(fixtures_root)
        else:
            base = getattr(settings, "DATA_ROOT", "/data")
            path = Path(base) / "odds"
        return CSVLinesProvider(fixtures_dir=path, mapper=mapper)
    if provider_type == "http":
        base_url = os.getenv("ODDS_HTTP_BASE_URL", "").strip()
        if not base_url:
            raise RuntimeError("ODDS_HTTP_BASE_URL не задан")
        return HTTPLinesProvider(
            base_url=base_url,
            token=getattr(settings, "ODDS_API_KEY", "") or None,
            timeout=float(getattr(settings, "ODDS_TIMEOUT_SEC", 8.0)),
            retry_attempts=int(getattr(settings, "ODDS_RETRY_ATTEMPTS", 4)),
            backoff_base=float(getattr(settings, "ODDS_BACKOFF_BASE", 0.4)),
            rps_limit=float(getattr(settings, "ODDS_RPS_LIMIT", 3.0)),
            mapper=mapper,
        )
    return _DummyProvider(mapper)


async def _run_check_async() -> dict[str, Any]:
    mapper = LinesMapper()
    provider = _create_provider(mapper)
    detector = _build_detector()
    facade = PredictionFacade()
    service = ValueService(facade=facade, provider=provider, detector=detector, mapper=mapper)
    target_date = date.today()
    meta: dict[str, dict[str, object]] = {}
    predictions = await facade.today(target_date)
    outcomes = list(service._build_model_outcomes(predictions, meta))
    date_from = datetime.combine(target_date, time.min, tzinfo=UTC)
    date_to = datetime.combine(target_date, time.max, tzinfo=UTC)
    odds = await provider.fetch_odds(date_from=date_from, date_to=date_to)
    picks = detector.detect(model=outcomes, market=odds)
    edges = [float(p.edge_pct) for p in picks]
    invalid_prices = [snap.price_decimal for snap in odds if getattr(snap, "price_decimal", 0.0) <= 1.0]
    cards = [
        {
            "match": meta.get(pick.match_key, {}),
            "market": pick.market,
            "selection": pick.selection,
            "edge_pct": pick.edge_pct,
            "provider": pick.provider,
        }
        for pick in picks
    ]
    close_fn = getattr(provider, "close", None)
    if close_fn:
        result = close_fn()
        if asyncio.iscoroutine(result):
            await result
    return {
        "predictions": len(predictions),
        "odds_count": len(odds),
        "picks": len(picks),
        "edges": edges,
        "invalid_prices": invalid_prices,
        "cards": cards[:5],
    }


def main() -> None:
    try:
        summary = asyncio.run(_run_check_async())
    except Exception as exc:  # pragma: no cover - unexpected runtime failure
        print(f"value_check failed: {exc}")
        raise SystemExit(2)
    print("Value & Odds summary:")
    for key in ("predictions", "odds_count", "picks"):
        print(f"  {key}: {summary.get(key)}")
    if summary.get("edges"):
        edges = summary["edges"]
        print(f"  edge_max: {max(edges):.2f}% edge_mean: {sum(edges)/len(edges):.2f}%")
    if summary.get("cards"):
        print("  top picks:")
        for card in summary["cards"]:
            match = card.get("match", {})
            title = f"{match.get('home', '?')} vs {match.get('away', '?')}"
            print(
                f"    {title} • {card['market']} {card['selection']} edge={card['edge_pct']:.1f}% provider={card['provider']}"
            )
    if summary.get("invalid_prices") or summary.get("odds_count", 0) == 0:
        print("Provider validation failed: no odds or invalid prices detected")
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
