"""
/**
 * @file: app/bot/routers/callbacks.py
 * @description: Inline callback handlers for pagination and match actions.
 * @dependencies: aiogram, app.bot.state
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from html import escape
from time import monotonic
from urllib.parse import unquote_plus

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

try:  # pragma: no cover - fallback when reliability_v2 is unavailable
    from app.lines import reliability_v2  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - offline/test environments
    class _ReliabilityV2Stub:
        @staticmethod
        def get_provider_scores(*_args, **_kwargs) -> list[dict[str, object]]:
            return []

        @staticmethod
        def explain_components(*_args, **_kwargs) -> dict[str, object]:
            return {}

    reliability_v2 = _ReliabilityV2Stub()
from app.lines.aggregator import LinesAggregator, parse_provider_weights
from app.lines.storage import OddsSQLiteStore
from config import settings

from ...metrics import observe_render_latency, record_command
from ..formatting import (
    format_explain,
    format_match_details,
    format_providers_breakdown,
    format_today_matches,
)
from ..keyboards import match_details_keyboard, today_keyboard
from ..state import FACADE, MATCH_CACHE, PAGINATION_CACHE
from .commands import (
    _calculate_total_pages,
    _paginate,
    _prediction_to_detail,
    _prediction_to_explain,
    _prediction_to_item,
)

callbacks_router = Router()


@callbacks_router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("page:"))
async def handle_page(callback: CallbackQuery) -> None:
    try:
        _, query_hash, page_raw = callback.data.split(":", 2)
        page = max(1, int(page_raw))
    except (ValueError, AttributeError):
        await callback.answer("Не удалось перелистнуть страницу")
        return
    state = await PAGINATION_CACHE.get(query_hash)
    if not state:
        await callback.answer("Данные устарели, выполните команду снова")
        return
    predictions = state.get("items", [])
    page_size = int(state.get("page_size", settings.PAGINATION_PAGE_SIZE))
    total_pages = _calculate_total_pages(len(predictions), page_size)
    page = min(page, total_pages)
    slice_items = _paginate(predictions, page, page_size)
    render_start = monotonic()
    text = format_today_matches(
        title=str(state.get("title", "Матчи")),
        timezone=str(state.get("timezone", "UTC")),
        items=[_prediction_to_item(item) for item in slice_items],
        page=page,
        total_pages=total_pages,
    )
    observe_render_latency("page", monotonic() - render_start)
    keyboard = today_keyboard(
        [_prediction_to_item(item) for item in slice_items],
        query_hash=query_hash,
        page=page,
        total_pages=total_pages,
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("match:"))
async def handle_match(callback: CallbackQuery) -> None:
    try:
        _, match_raw, query_hash, page_raw = callback.data.split(":", 3)
        match_id = int(match_raw)
        page = int(page_raw)
    except (ValueError, AttributeError):
        await callback.answer("Не удалось открыть матч")
        return
    prediction = None
    state = await PAGINATION_CACHE.get(query_hash)
    if state:
        for item in state.get("items", []):
            if item.match_id == match_id:
                prediction = item
                break
    if prediction is None:
        prediction, _ = await MATCH_CACHE.get_or_set(
            f"match:{match_id}",
            lambda: FACADE.match(match_id),
        )
    render_start = monotonic()
    text = format_match_details(_prediction_to_detail(prediction))
    observe_render_latency("match_callback", monotonic() - render_start)
    keyboard = match_details_keyboard(match_id, query_hash=query_hash, page=page)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("providers:"))
async def handle_providers(callback: CallbackQuery) -> None:
    try:
        _, match_enc, market_enc, selection_enc = callback.data.split(":", 3)
        match_key = unquote_plus(match_enc)
        market = unquote_plus(market_enc)
        selection = unquote_plus(selection_enc)
    except (ValueError, AttributeError):
        await callback.answer("Некорректные данные")
        return
    store = OddsSQLiteStore()
    quotes = store.latest_quotes(match_key=match_key, market=market, selection=selection)
    aggregator = LinesAggregator(
        method=str(getattr(settings, "ODDS_AGG_METHOD", "median")),
        provider_weights=parse_provider_weights(getattr(settings, "ODDS_PROVIDER_WEIGHTS", None)),
        store=None,
        retention_days=0,
        movement_window_minutes=int(getattr(settings, "CLV_WINDOW_BEFORE_KICKOFF_MIN", 120)),
    )
    consensus_payload = None
    if quotes:
        aggregated = aggregator.aggregate(quotes)
        if aggregated:
            consensus_payload = aggregated[0].extra.get("consensus")
    text = format_providers_breakdown(
        match_key=match_key,
        market=market,
        selection=selection,
        quotes=quotes,
        consensus=consensus_payload,
    )
    await callback.message.answer(text)
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("whyprov:"))
async def handle_why_provider(callback: CallbackQuery) -> None:
    try:
        _, match_enc, market_enc, selection_enc, provider_enc = callback.data.split(":", 4)
    except (ValueError, AttributeError):
        await callback.answer("Некорректные данные")
        return
    match_key = unquote_plus(match_enc)
    market = unquote_plus(market_enc)
    selection = unquote_plus(selection_enc)
    provider = unquote_plus(provider_enc)
    store = OddsSQLiteStore()
    quotes = store.latest_quotes(
        match_key=match_key,
        market=market,
        selection=selection,
    )
    league = None
    for quote in quotes:
        if quote.provider.lower() == provider.lower():
            league = quote.league
            break
    league_norm = league.upper() if isinstance(league, str) else None
    try:
        explanation = reliability_v2.explain_components(
            provider=provider,
            league=league_norm,
            market=market.upper(),
        )
    except Exception:
        explanation = None
    if not explanation:
        await callback.answer("Нет данных по провайдеру")
        return
    league_label = explanation.get("league") or league_norm or "GLOBAL"
    metrics = []
    fresh_val = explanation.get("fresh")
    if fresh_val is not None:
        try:
            metrics.append(f"fresh={float(fresh_val):.2f}")
        except (TypeError, ValueError):
            pass
    latency_val = explanation.get("latency")
    if latency_val is not None:
        try:
            metrics.append(f"latency={float(latency_val):.0f}мс")
        except (TypeError, ValueError):
            pass
    stability_val = explanation.get("stability")
    if stability_val is not None:
        try:
            metrics.append(f"stability={float(stability_val):.2f}")
        except (TypeError, ValueError):
            pass
    closing_val = explanation.get("closing")
    if closing_val is not None:
        try:
            metrics.append(f"closingΔ={float(closing_val):+.2f}")
        except (TypeError, ValueError):
            pass
    trend_note = explanation.get("trend")
    lines = [
        f"🤔 <b>Почему {escape(provider)}</b>",
        f"Лига: {escape(str(league_label))}",
        f"Рынок: {escape(market.upper())}",
    ]
    if trend_note:
        lines.append(f"Тренд: {escape(str(trend_note))}")
    if metrics:
        lines.append(" · ".join(metrics))
    else:
        lines.append("Деталей reliability_v2 нет.")
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("back:"))
async def handle_back(callback: CallbackQuery) -> None:
    try:
        _, query_hash, page_raw = callback.data.split(":", 2)
        page = int(page_raw)
    except (ValueError, AttributeError):
        await callback.answer("Не удалось вернуться")
        return
    state = await PAGINATION_CACHE.get(query_hash)
    if not state:
        await callback.answer("Данные устарели, вызовите команду снова")
        return
    predictions = state.get("items", [])
    page_size = int(state.get("page_size", settings.PAGINATION_PAGE_SIZE))
    total_pages = _calculate_total_pages(len(predictions), page_size)
    page = max(1, min(page, total_pages))
    slice_items = _paginate(predictions, page, page_size)
    render_start = monotonic()
    text = format_today_matches(
        title=str(state.get("title", "Матчи")),
        timezone=str(state.get("timezone", "UTC")),
        items=[_prediction_to_item(item) for item in slice_items],
        page=page,
        total_pages=total_pages,
    )
    observe_render_latency("back", monotonic() - render_start)
    keyboard = today_keyboard(
        [_prediction_to_item(item) for item in slice_items],
        query_hash=query_hash,
        page=page,
        total_pages=total_pages,
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("explain:"))
async def handle_explain(callback: CallbackQuery) -> None:
    try:
        match_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный идентификатор")
        return
    prediction, _ = await MATCH_CACHE.get_or_set(
        f"match:{match_id}",
        lambda: FACADE.match(match_id),
    )
    render_start = monotonic()
    text = format_explain(_prediction_to_explain(prediction))
    observe_render_latency("explain_callback", monotonic() - render_start)
    await callback.message.answer(text)
    await callback.answer()


@callbacks_router.callback_query(F.data.startswith("export:"))
async def handle_export(callback: CallbackQuery) -> None:
    try:
        match_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный идентификатор")
        return
    prediction, _ = await MATCH_CACHE.get_or_set(
        f"match:{match_id}",
        lambda: FACADE.match(match_id),
    )
    csv_path = FACADE.generate_csv(prediction)
    png_path = FACADE.generate_png(prediction)
    record_command("export_callback")
    await callback.message.answer(
        f"Экспорт сохранён: {csv_path.name}, {png_path.name}"
    )
    await callback.answer("Отправлено")
