"""
/**
 * @file: app/bot/routers/commands.py
 * @description: Aiogram command handlers for production-grade prediction bot.
 * @dependencies: aiogram, app.bot.services, app.bot.formatting
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message

from config import settings
from logger import logger

from ...metrics import observe_render_latency, record_command
from ..formatting import (
    format_about,
    format_explain,
    format_help,
    format_match_details,
    format_value_comparison,
    format_value_picks,
    format_settings,
    format_start,
    format_today_matches,
)
from ..keyboards import match_details_keyboard, noop_keyboard, today_keyboard
from ..services import Prediction
from ..state import FACADE, LIST_CACHE, MATCH_CACHE, PAGINATION_CACHE
from ..storage import (
    get_user_preferences,
    get_value_alert,
    list_recent_value_alerts,
    list_subscriptions,
    upsert_subscription,
    upsert_value_alert,
)
from diagtools import scheduler as diag_scheduler

from app.lines.mapper import LinesMapper
from app.lines.providers import CSVLinesProvider, HTTPLinesProvider
from app.lines.providers.base import LinesProvider
from app.value_calibration import CalibrationService
from app.value_detector import ValueDetector
from app.value_service import ValueService

commands_router = Router()
_ADMIN_IDS = {
    int(item.strip())
    for item in settings.ADMIN_IDS.split(",")
    if item.strip().isdigit()
}
_COMMANDS_LIST = [
    "/start",
    "/help",
    "/today",
    "/match",
    "/explain",
    "/league",
    "/subscribe",
    "/settings",
    "/export",
    "/about",
]

if settings.ENABLE_VALUE_FEATURES:
    _COMMANDS_LIST.extend(["/value", "/compare", "/alerts"])


def _hash_query(user_id: int, key: str) -> str:
    digest = hashlib.sha1(f"{user_id}:{key}".encode("utf-8")).hexdigest()
    return digest[:12]


def _get_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _prediction_to_item(prediction: Prediction) -> dict[str, Any]:
    return {
        "id": prediction.match_id,
        "home": prediction.home,
        "away": prediction.away,
        "league": prediction.league,
        "kickoff": prediction.kickoff,
        "markets": prediction.markets.get("1x2", {}),
        "confidence": prediction.confidence,
        "expected_goals": prediction.expected_goals,
        "totals": prediction.totals,
        "freshness_hours": prediction.freshness_hours,
    }


def _prediction_to_detail(prediction: Prediction) -> dict[str, Any]:
    return {
        "fixture": {
            "id": prediction.match_id,
            "home": prediction.home,
            "away": prediction.away,
            "league": prediction.league,
            "kickoff": prediction.kickoff,
        },
        "markets": prediction.markets,
        "totals": prediction.totals,
        "both_teams_to_score": prediction.btts,
        "top_scores": prediction.top_scores,
        "fair_odds": prediction.fair_odds,
        "confidence": prediction.confidence,
        "standings": prediction.standings,
        "injuries": prediction.injuries,
        "freshness_hours": prediction.freshness_hours,
    }


def _prediction_to_explain(prediction: Prediction) -> dict[str, Any]:
    return {
        "id": prediction.match_id,
        "fixture": {
            "home": prediction.home,
            "away": prediction.away,
        },
        "lambda_home": prediction.lambda_home,
        "lambda_away": prediction.lambda_away,
        "modifiers": prediction.modifiers,
        "delta_probabilities": prediction.delta_probabilities,
        "confidence": prediction.confidence,
        "summary": prediction.summary,
        "standings": prediction.standings,
        "injuries": prediction.injuries,
        "freshness_hours": prediction.freshness_hours,
    }


def _format_freshness_badge(hours: float) -> str:
    warn = float(settings.SM_FRESHNESS_WARN_HOURS)
    fail = float(settings.SM_FRESHNESS_FAIL_HOURS)
    if hours <= warn:
        if hours < 1:
            minutes = max(1, int(hours * 60))
            return f"🟢 updated {minutes}m ago"
        return f"🟢 updated {int(hours)}h ago"
    if hours <= fail:
        return f"⚠️ stale {int(hours)}h (warn)"
    return f"⚠️ stale {int(hours)}h (fail)"


def _freshness_note(predictions: Sequence[Prediction]) -> str | None:
    if not settings.SHOW_DATA_STALENESS:
        return None
    hours = [
        float(p.freshness_hours)
        for p in predictions
        if isinstance(p.freshness_hours, (int, float))
    ]
    if not hours:
        return None
    worst = max(hours)
    return _format_freshness_badge(worst)


def _paginate(items: Sequence[Prediction], page: int, page_size: int) -> Sequence[Prediction]:
    start = (page - 1) * page_size
    return items[start : start + page_size]


def _calculate_total_pages(count: int, page_size: int) -> int:
    if count == 0:
        return 1
    return max(1, math.ceil(count / page_size))


@dataclass
class TodayArgs:
    league: str | None = None
    limit: int = settings.PAGINATION_PAGE_SIZE


def _parse_today_args(raw: str | None) -> TodayArgs:
    if not raw:
        return TodayArgs()
    tokens = [token.strip() for token in raw.split() if token.strip()]
    league = None
    limit = settings.PAGINATION_PAGE_SIZE
    for token in tokens:
        if token.startswith("limit="):
            try:
                limit = max(1, min(20, int(token.split("=", 1)[1])))
            except ValueError:
                raise ValueError("Некорректное значение limit")
        elif league is None:
            league = token
    return TodayArgs(league=league, limit=limit)


@dataclass
class ValueArgs:
    league: str | None = None
    target_date: date = date.today()
    limit: int = settings.VALUE_MAX_PICKS


def _parse_value_args(raw: str | None) -> ValueArgs:
    if not raw:
        return ValueArgs()
    tokens = [token.strip() for token in raw.split() if token.strip()]
    league: str | None = None
    target_date = date.today()
    limit = settings.VALUE_MAX_PICKS
    for token in tokens:
        if token.startswith("date="):
            _, value = token.split("=", 1)
            try:
                target_date = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Некорректная дата, ожидается YYYY-MM-DD") from exc
        elif token.startswith("limit="):
            try:
                limit = max(1, min(20, int(token.split("=", 1)[1])))
            except ValueError as exc:
                raise ValueError("Некорректное значение limit") from exc
        elif league is None:
            league = token
    return ValueArgs(league=league, target_date=target_date, limit=limit)


@dataclass(slots=True)
class _DummyLinesProvider:
    mapper: LinesMapper

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[Any]:  # pragma: no cover - fallback path
        return []


def _create_lines_provider(mapper: LinesMapper) -> LinesProvider:
    provider_type = (getattr(settings, "ODDS_PROVIDER", "dummy") or "dummy").lower()
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
            raise RuntimeError("ODDS_HTTP_BASE_URL не задан для HTTP-провайдера котировок")
        return HTTPLinesProvider(
            base_url=base_url,
            token=getattr(settings, "ODDS_API_KEY", "") or None,
            timeout=float(getattr(settings, "ODDS_TIMEOUT_SEC", 8.0)),
            retry_attempts=int(getattr(settings, "ODDS_RETRY_ATTEMPTS", 4)),
            backoff_base=float(getattr(settings, "ODDS_BACKOFF_BASE", 0.4)),
            rps_limit=float(getattr(settings, "ODDS_RPS_LIMIT", 3.0)),
            mapper=mapper,
        )
    return _DummyLinesProvider(mapper=mapper)


_CALIBRATION_SERVICE: CalibrationService | None = None


def _get_calibration_service() -> CalibrationService:
    global _CALIBRATION_SERVICE
    if _CALIBRATION_SERVICE is None:
        _CALIBRATION_SERVICE = CalibrationService(
            default_edge_pct=float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0)),
            default_confidence=float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6)),
        )
    return _CALIBRATION_SERVICE


def _build_value_detector() -> ValueDetector:
    markets_raw = getattr(settings, "VALUE_MARKETS", "1X2,OU_2_5,BTTS")
    markets = tuple(item.strip() for item in str(markets_raw).split(",") if item.strip())
    confidence_method = str(getattr(settings, "VALUE_CONFIDENCE_METHOD", "none"))
    return ValueDetector(
        min_edge_pct=float(getattr(settings, "VALUE_MIN_EDGE_PCT", 3.0)),
        min_confidence=float(getattr(settings, "VALUE_MIN_CONFIDENCE", 0.6)),
        max_picks=int(getattr(settings, "VALUE_MAX_PICKS", 5)),
        markets=markets,
        overround_method=str(getattr(settings, "ODDS_OVERROUND_METHOD", "proportional")),
        confidence_method=confidence_method,
        calibration=_get_calibration_service(),
    )


def _create_value_service() -> tuple[ValueService, LinesProvider]:
    mapper = LinesMapper()
    provider = _create_lines_provider(mapper)
    detector = _build_value_detector()
    service = ValueService(facade=FACADE, provider=provider, detector=detector, mapper=mapper)
    return service, provider


async def _close_lines_provider(provider: LinesProvider) -> None:
    close_fn = getattr(provider, "close", None)
    if close_fn is None:
        return
    result = close_fn()
    if asyncio.iscoroutine(result):
        await result


@dataclass
class AlertsArgs:
    enabled: bool | None = None
    edge_threshold: float | None = None
    league: str | None = None


def _parse_alert_args(raw: str | None) -> AlertsArgs:
    if not raw:
        return AlertsArgs()
    tokens = [token.strip() for token in raw.split() if token.strip()]
    enabled: bool | None = None
    edge_threshold: float | None = None
    league: str | None = None
    for token in tokens:
        lowered = token.lower()
        if lowered in {"on", "off"}:
            enabled = lowered == "on"
        elif lowered.startswith("edge="):
            try:
                edge_threshold = float(lowered.split("=", 1)[1])
            except ValueError as exc:
                raise ValueError("Некорректное значение edge") from exc
        elif league is None:
            league = token
    return AlertsArgs(enabled=enabled, edge_threshold=edge_threshold, league=league)


@commands_router.message(Command("start"))
async def handle_start(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    prefs = get_user_preferences(user_id)
    tz_name = prefs.get("tz", "UTC")
    lang = prefs.get("lang", "ru")
    text = format_start(lang, tz_name, _COMMANDS_LIST)
    record_command("start")
    await message.answer(text, reply_markup=noop_keyboard())


@commands_router.message(Command("help"))
async def handle_help(message: Message, command: CommandObject) -> None:
    record_command("help")
    await message.answer(format_help(), reply_markup=noop_keyboard())


@commands_router.message(Command("today"))
async def handle_today(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    args_text = command.args or ""
    try:
        parsed = _parse_today_args(args_text)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    prefs = get_user_preferences(user_id)
    tz_name = prefs.get("tz", "UTC")
    tz = _get_timezone(tz_name)
    today_date = datetime.now(UTC).astimezone(tz).date()
    cache_key = f"today:{today_date.isoformat()}:{parsed.league or 'all'}"
    predictions, cache_hit = await LIST_CACHE.get_or_set(
        cache_key,
        lambda: FACADE.today(today_date, league=parsed.league),
    )
    if not predictions:
        await message.answer("На выбранную дату матчей не найдено.")
        return
    page_size = parsed.limit
    total_pages = _calculate_total_pages(len(predictions), page_size)
    page = 1
    slice_items = _paginate(predictions, page, page_size)
    query_hash = _hash_query(user_id, cache_key)
    await PAGINATION_CACHE.set(
        query_hash,
        {
            "items": predictions,
            "page_size": page_size,
            "title": "Матчи на сегодня",
            "timezone": tz_name,
        },
    )
    render_start = monotonic()
    formatted = format_today_matches(
        title="Матчи на сегодня",
        timezone=tz_name,
        items=[_prediction_to_item(item) for item in slice_items],
        page=page,
        total_pages=total_pages,
        freshness_note=_freshness_note(predictions),
    )
    observe_render_latency("today", monotonic() - render_start)
    record_command("today")
    keyboard = today_keyboard(
        [_prediction_to_item(item) for item in slice_items],
        query_hash=query_hash,
        page=page,
        total_pages=total_pages,
    )
    logger.info(
        "Команда /today", extra={"user_id": user_id, "league": parsed.league, "cache_hit": cache_hit}
    )
    await message.answer(formatted, reply_markup=keyboard)


@commands_router.message(Command("match"))
async def handle_match(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    args = (command.args or "").strip()
    if not args:
        await message.answer("Укажите идентификатор матча: /match &lt;id&gt;")
        return
    try:
        match_id = int(args.split()[0])
    except ValueError:
        await message.answer("Пока поддерживается поиск только по идентификатору.")
        return
    cache_key = f"match:{match_id}"
    prediction, cache_hit = await MATCH_CACHE.get_or_set(
        cache_key,
        lambda: FACADE.match(match_id),
    )
    render_start = monotonic()
    text = format_match_details(_prediction_to_detail(prediction))
    observe_render_latency("match", monotonic() - render_start)
    record_command("match")
    logger.info("Команда /match", extra={"user_id": user_id, "match_id": match_id, "cache_hit": cache_hit})
    keyboard = match_details_keyboard(match_id, query_hash=None)
    await message.answer(text, reply_markup=keyboard)


@commands_router.message(Command("explain"))
async def handle_explain(message: Message, command: CommandObject) -> None:
    args = (command.args or "").strip()
    if not args:
        await message.answer("Укажите идентификатор: /explain &lt;id&gt;")
        return
    try:
        match_id = int(args.split()[0])
    except ValueError:
        await message.answer("Используйте числовой идентификатор матча")
        return
    cache_key = f"match:{match_id}"
    prediction, _ = await MATCH_CACHE.get_or_set(
        cache_key,
        lambda: FACADE.match(match_id),
    )
    render_start = monotonic()
    text = format_explain(_prediction_to_explain(prediction))
    observe_render_latency("explain", monotonic() - render_start)
    record_command("explain")
    await message.answer(text)


@commands_router.message(Command("league"))
async def handle_league(message: Message, command: CommandObject) -> None:
    args = (command.args or "").strip()
    if not args:
        await message.answer("Используйте: /league &lt;code&gt; [YYYY-MM-DD]")
        return
    tokens = args.split()
    league_code = tokens[0]
    if len(tokens) > 1:
        try:
            target_date = date.fromisoformat(tokens[1])
        except ValueError:
            await message.answer("Дата должна быть в формате YYYY-MM-DD")
            return
    else:
        target_date = datetime.now(UTC).date()
    cache_key = f"league:{league_code}:{target_date.isoformat()}"
    predictions, cache_hit = await LIST_CACHE.get_or_set(
        cache_key,
        lambda: FACADE.league_fixtures(league_code, target_date),
    )
    if not predictions:
        await message.answer("Матчи лиги не найдены.")
        return
    page_size = settings.PAGINATION_PAGE_SIZE
    total_pages = _calculate_total_pages(len(predictions), page_size)
    page = 1
    slice_items = _paginate(predictions, page, page_size)
    query_hash = _hash_query(message.from_user.id if message.from_user else 0, cache_key)
    await PAGINATION_CACHE.set(
        query_hash,
        {
            "items": predictions,
            "page_size": page_size,
            "title": f"Лига {league_code.upper()}",
            "timezone": "UTC",
        },
    )
    render_start = monotonic()
    text = format_today_matches(
        title=f"Лига {league_code.upper()}",
        timezone="UTC",
        items=[_prediction_to_item(item) for item in slice_items],
        page=page,
        total_pages=total_pages,
        freshness_note=_freshness_note(predictions),
    )
    observe_render_latency("league", monotonic() - render_start)
    record_command("league")
    logger.info(
        "Команда /league", extra={"user_id": message.from_user.id if message.from_user else 0, "league": league_code, "cache_hit": cache_hit}
    )
    keyboard = today_keyboard(
        [_prediction_to_item(item) for item in slice_items],
        query_hash=query_hash,
        page=page,
        total_pages=total_pages,
    )
    await message.answer(text, reply_markup=keyboard)


@commands_router.message(Command("subscribe"))
async def handle_subscribe(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    args = (command.args or settings.DIGEST_DEFAULT_TIME).split()
    if not args:
        args = [settings.DIGEST_DEFAULT_TIME]
    time_part = args[0]
    league = args[1] if len(args) > 1 else None
    if ":" not in time_part:
        await message.answer("Время должно быть в формате HH:MM")
        return
    try:
        hour, minute = [int(part) for part in time_part.split(":", 1)]
    except ValueError:
        await message.answer("Время должно быть в формате HH:MM")
        return
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await message.answer("Укажите корректное время от 00:00 до 23:59")
        return
    prefs = get_user_preferences(user_id)
    tz_name = prefs.get("tz", "UTC")
    upsert_subscription(user_id, send_at=f"{hour:02d}:{minute:02d}", tz=tz_name, league=league)
    record_command("subscribe")
    await message.answer(
        f"Подписка сохранена на {hour:02d}:{minute:02d} {tz_name}. Лига: {league or 'все'}"
    )


@commands_router.message(Command("settings"))
async def handle_settings(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    prefs = get_user_preferences(user_id)
    record_command("settings")
    await message.answer(format_settings(prefs))


@commands_router.message(Command("export"))
async def handle_export(message: Message, command: CommandObject) -> None:
    args = (command.args or "").strip()
    if not args:
        await message.answer("Используйте: /export &lt;match_id&gt;")
        return
    try:
        match_id = int(args.split()[0])
    except ValueError:
        await message.answer("match_id должен быть числом")
        return
    prediction, _ = await MATCH_CACHE.get_or_set(
        f"match:{match_id}",
        lambda: FACADE.match(match_id),
    )
    csv_path = FACADE.generate_csv(prediction)
    png_path = FACADE.generate_png(prediction)
    record_command("export")
    await message.answer(
        f"Готово! CSV: {csv_path.name}, PNG: {png_path.name} сохранены в {settings.REPORTS_DIR}"
    )


@commands_router.message(Command("about"))
async def handle_about(message: Message, command: CommandObject) -> None:
    metadata = {
        "APP_VERSION": settings.APP_VERSION,
        "GIT_SHA": settings.GIT_SHA,
        "MODEL_VERSION": settings.MODEL_VERSION,
        "DB_PATH": settings.DB_PATH,
    }
    record_command("about")
    await message.answer(format_about(metadata))


if settings.ENABLE_VALUE_FEATURES:

    @commands_router.message(Command("value"))
    async def handle_value(message: Message, command: CommandObject) -> None:
        try:
            parsed = _parse_value_args(command.args)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        service, provider = _create_value_service()
        try:
            cards = await service.value_picks(
                target_date=parsed.target_date,
                league=parsed.league,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Команда /value упала",  # noqa: TRY400
                extra={
                    "user_id": message.from_user.id if message.from_user else 0,
                    "league": parsed.league,
                },
            )
            await message.answer("Не удалось загрузить value-кейсы, попробуйте позже.")
            return
        finally:
            await _close_lines_provider(provider)
        cards = cards[: parsed.limit]
        title = f"Value-кейсы на {parsed.target_date.isoformat()}"
        if parsed.league:
            title += f" ({parsed.league})"
        render_start = monotonic()
        text = format_value_picks(title=title, cards=cards)
        observe_render_latency("value", monotonic() - render_start)
        record_command("value")
        logger.info(
            "Команда /value",  # noqa: TRY400
            extra={
                "user_id": message.from_user.id if message.from_user else 0,
                "league": parsed.league,
                "date": parsed.target_date.isoformat(),
                "picks": len(cards),
            },
        )
        await message.answer(text, reply_markup=noop_keyboard)

    @commands_router.message(Command("compare"))
    async def handle_compare(message: Message, command: CommandObject) -> None:
        query = (command.args or "").strip()
        if not query:
            await message.answer("Использование: /compare &lt;match_id или команды&gt;")
            return
        service, provider = _create_value_service()
        try:
            summary = await service.compare(query=query, target_date=date.today())
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Команда /compare упала",  # noqa: TRY400
                extra={"user_id": message.from_user.id if message.from_user else 0, "query": query},
            )
            await message.answer("Не удалось получить сравнение рынков, попробуйте позже.")
            return
        finally:
            await _close_lines_provider(provider)
        if not summary:
            await message.answer("Матч не найден или котировки недоступны.")
            return
        render_start = monotonic()
        text = format_value_comparison(summary)
        observe_render_latency("compare", monotonic() - render_start)
        record_command("compare")
        logger.info(
            "Команда /compare",  # noqa: TRY400
            extra={"user_id": message.from_user.id if message.from_user else 0, "query": query},
        )
        await message.answer(text, reply_markup=noop_keyboard)

    @commands_router.message(Command("alerts"))
    async def handle_alerts(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id if message.from_user else 0
        if user_id <= 0:
            await message.answer("Не удалось определить пользователя.")
            return
        try:
            parsed = _parse_alert_args(command.args)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        changes = any(
            value is not None for value in (parsed.enabled, parsed.edge_threshold, parsed.league)
        )
        if changes:
            prefs = upsert_value_alert(
                user_id,
                enabled=parsed.enabled,
                edge_threshold=parsed.edge_threshold,
                league=parsed.league,
            )
        else:
            prefs = get_value_alert(user_id)
        status = "включены" if prefs.get("enabled") else "выключены"
        league = prefs.get("league") or "все лиги"
        edge_threshold = float(prefs.get("edge_threshold", 5.0))
        render_start = monotonic()
        rules = [
            "⚙️ Правила рассылки:",
            f"• Cooldown: {int(getattr(settings, 'VALUE_ALERT_COOLDOWN_MIN', 60))} мин",
            f"• Quiet hours: {getattr(settings, 'VALUE_ALERT_QUIET_HOURS', '—')}",
            f"• Δ edge ≥ {float(getattr(settings, 'VALUE_ALERT_MIN_EDGE_DELTA', 0.0)):.1f} п.п.",
            f"• Ста́лость ≤ {int(getattr(settings, 'VALUE_STALENESS_FAIL_MIN', 30))} мин",
        ]
        recent = list_recent_value_alerts(user_id, limit=5)
        delta_history: dict[tuple[str, str, str], float] = {}
        deltas: dict[int, float | None] = {}
        for row in reversed(recent):
            key = (str(row.get("match_key")), str(row.get("market")), str(row.get("selection")))
            prev = delta_history.get(key)
            deltas[int(row.get("id", 0))] = None if prev is None else float(row.get("edge_pct", 0.0)) - prev
            delta_history[key] = float(row.get("edge_pct", 0.0))
        recent_lines = ["📝 Последние алерты:"]
        if recent:
            for row in recent:
                sent_at = str(row.get("sent_at", ""))
                edge_val = float(row.get("edge_pct", 0.0))
                delta_val = deltas.get(int(row.get("id", 0)))
                delta_str = "Δ=—" if delta_val is None else f"Δ={delta_val:+.1f} п.п."
                recent_lines.append(
                    f"• {row.get('match_key')} {row.get('market')}/{row.get('selection')}"
                    f" edge={edge_val:.1f}% ({delta_str}) {sent_at}"
                )
        else:
            recent_lines.append("• пока нет истории")
        text = "\n".join(
            [
                f"Value-оповещения {status}.",
                f"Порог edge: {edge_threshold:.1f}%.",
                f"Лиги: {league}.",
                "",
                *rules,
                "",
                *recent_lines,
                "",
                "Команды: /alerts on, /alerts off, /alerts edge=5.5",
            ]
        )
        observe_render_latency("alerts", monotonic() - render_start)
        record_command("alerts")
        logger.info(
            "Команда /alerts",  # noqa: TRY400
            extra={
                "user_id": user_id,
                "status": status,
                "edge": edge_threshold,
                "league": league,
            },
        )
        await message.answer(text, reply_markup=noop_keyboard)


@commands_router.message(Command("diag"))
async def handle_diag_admin(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if _ADMIN_IDS and user_id not in _ADMIN_IDS:
        await message.answer("Недостаточно прав")
        return
    record_command("diag")
    args = (command.args or "").strip().split()
    subcommand = args[0] if args else ""
    loop = asyncio.get_running_loop()

    if subcommand == "last":
        history = diag_scheduler.load_history(limit=1)
        if not history:
            await message.answer("История диагностики пуста")
            return
        entry = history[0]
        warn = ", ".join(entry.warn_sections) or "—"
        fail = ", ".join(entry.fail_sections) or "—"
        await message.answer(
            "\n".join(
                [
                    f"Последний запуск: {entry.timestamp}",
                    f"Статус: {entry.status}",
                    f"Длительность: {entry.duration_sec:.1f}с",
                    f"WARN: {warn}",
                    f"FAIL: {fail}",
                    f"HTML: {entry.html_path or '—'}",
                ]
            )
        )
        return

    if subcommand == "drift":
        await message.answer("Запускаю drift-чек…")
        try:
            result = await loop.run_in_executor(None, lambda: diag_scheduler.run_drift(trigger="manual"))
        except Exception as exc:  # pragma: no cover - executor errors
            await message.answer(f"Ошибка drift-чека: {exc}")
            return
        await message.answer(
            f"drift завершён: rc={result.returncode} за {result.duration_sec:.1f}с"
        )
        return

    if subcommand == "link":
        html_path = Path(settings.REPORTS_DIR) / "diagnostics" / "site" / "index.html"
        if not html_path.exists():
            await message.answer("HTML-дэшборд ещё не сформирован")
            return
        await message.answer_document(FSInputFile(html_path), caption="Diagnostics dashboard")
        return

    await message.answer("Диагностика запущена, это может занять пару минут…")
    try:
        result = await loop.run_in_executor(None, lambda: diag_scheduler.run_suite(trigger="manual"))
    except Exception as exc:  # pragma: no cover - unexpected failure
        await message.answer(f"Ошибка запуска диагностики: {exc}")
        return
    statuses = result.statuses
    warn_sections = [name for name, payload in statuses.items() if payload.get("status") == "⚠️"]
    fail_sections = [name for name, payload in statuses.items() if payload.get("status") == "❌"]
    duration = (result.finished_at - result.started_at).total_seconds()
    lines = [
        f"Готово за {duration:.1f}с",
        f"WARN: {', '.join(warn_sections) if warn_sections else '—'}",
        f"FAIL: {', '.join(fail_sections) if fail_sections else '—'}",
        f"Лог: {result.log_path}",
    ]
    if result.html_path:
        lines.append(f"HTML: {result.html_path}")
    if result.alerts_sent:
        lines.append("Алерт отправлен в админ-чат")
    await message.answer("\n".join(lines))


@commands_router.message(Command("admin"))
async def handle_admin(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if _ADMIN_IDS and user_id not in _ADMIN_IDS:
        await message.answer("Недостаточно прав")
        return
    args = (command.args or "").strip().split()
    if not args:
        await message.answer("Доступно: stats, reload")
        return
    record_command("admin")
    subcommand = args[0]
    if subcommand == "stats":
        subscriptions = list_subscriptions()
        payload = {
            "subscribers": len(subscriptions),
            "cache_size": _PREDICTION_CACHE.stats()["size"],
        }
        await message.answer(str(payload))
    elif subcommand == "reload":
        await LIST_CACHE.clear()
        await MATCH_CACHE.clear()
        await PAGINATION_CACHE.clear()
        await message.answer("Кеш очищен")
    else:
        await message.answer("Неизвестная команда администратора")
