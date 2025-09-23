"""
/**
 * @file: app/bot/routers/commands.py
 * @description: Aiogram command handlers for production-grade prediction bot.
 * @dependencies: aiogram, app.bot.services, app.bot.formatting
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import monotonic
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import settings
from logger import logger

from ...metrics import observe_render_latency, record_command
from ..formatting import (
    format_about,
    format_explain,
    format_help,
    format_match_details,
    format_settings,
    format_start,
    format_today_matches,
)
from ..keyboards import match_details_keyboard, noop_keyboard, today_keyboard
from ..services import Prediction
from ..state import FACADE, LIST_CACHE, MATCH_CACHE, PAGINATION_CACHE
from ..storage import get_user_preferences, list_subscriptions, upsert_subscription

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
    }


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
