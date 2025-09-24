"""
/**
 * @file: app/bot/keyboards.py
 * @description: Inline keyboard factories for pagination, match details and exports.
 * @dependencies: aiogram
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import quote_plus

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def _providers_callback(match_key: str, market: str, selection: str) -> str:
    encoded = [quote_plus(str(item)) for item in (match_key, market, selection)]
    return "providers:" + ":".join(encoded)


def _why_provider_callback(
    match_key: str,
    market: str,
    selection: str,
    provider: str,
) -> str:
    encoded = [quote_plus(str(item)) for item in (match_key, market, selection, provider)]
    return "whyprov:" + ":".join(encoded)


def today_keyboard(
    matches: Iterable[dict[str, object]],
    *,
    query_hash: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for match in matches:
        match_id = match.get("id")
        if match_id is None:
            continue
        title = f"Подробнее · {match.get('home')} vs {match.get('away')}"
        builder.button(
            text=title,
            callback_data=f"match:{match_id}:{query_hash}:{page}",
        )
    if builder.buttons:
        builder.adjust(1)
    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"page:{query_hash}:{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"page:{query_hash}:{page+1}"))
    builder.row(*nav_row)
    return builder.as_markup()


def match_details_keyboard(
    match_id: int,
    *,
    query_hash: str | None = None,
    page: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧠 Объяснить", callback_data=f"explain:{match_id}")
    builder.button(text="📤 Экспорт", callback_data=f"export:{match_id}")
    if query_hash:
        back_payload = f"back:{query_hash}:{page or 1}"
        builder.button(text="⬅️ Назад", callback_data=back_payload)
        builder.adjust(2, 1)
    else:
        builder.adjust(2)
    return builder.as_markup()


def noop_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="OK", callback_data="noop")
    builder.adjust(1)
    return builder.as_markup()


def value_providers_keyboard(cards: Iterable[dict[str, object]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, card in enumerate(cards, start=1):
        consensus = card.get("consensus") or {}
        match_key = consensus.get("match_key") or card.get("match", {}).get("match_key")
        pick = card.get("pick")
        market = consensus.get("market") or getattr(pick, "market", None)
        selection = consensus.get("selection") or getattr(pick, "selection", None)
        if not match_key or not market or not selection:
            continue
        builder.button(
            text=f"Провайдеры #{idx}",
            callback_data=_providers_callback(str(match_key), str(market), str(selection)),
        )
        best = card.get("best_price") or {}
        provider = best.get("provider")
        if provider:
            builder.button(
                text=f"Почему {provider}",
                callback_data=_why_provider_callback(
                    str(match_key), str(market), str(selection), str(provider)
                ),
            )
    builder.button(text="OK", callback_data="noop")
    builder.adjust(2, 1)
    return builder.as_markup()


def comparison_providers_keyboard(
    match_key: str,
    consensus_map: Mapping[tuple[str, str], dict[str, object]],
    best_price: Mapping[tuple[str, str], dict[str, object]] | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for market, selection in consensus_map.keys():
        builder.button(
            text=f"{market}/{selection}",
            callback_data=_providers_callback(match_key, market, selection),
        )
        if best_price:
            payload = best_price.get((market, selection))
            if payload and payload.get("provider"):
                builder.button(
                    text=f"Почему {payload['provider']}",
                    callback_data=_why_provider_callback(
                        match_key, market, selection, str(payload["provider"])
                    ),
                )
    builder.button(text="OK", callback_data="noop")
    builder.adjust(2, 1)
    return builder.as_markup()


__all__ = [
    "today_keyboard",
    "match_details_keyboard",
    "noop_keyboard",
    "value_providers_keyboard",
    "comparison_providers_keyboard",
]
