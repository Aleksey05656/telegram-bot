"""
@file: telegram/handlers/start.py
@description: Обработчик команды /start и главного меню.
@dependencies: aiogram, asyncio, sqlite3, config
@created: 2025-09-19
"""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from logger import logger
from telegram.handlers.terms import DISCLAIMER_TEXT
from telegram.models import CommandWithoutArgs


@dataclass(slots=True)
class BotStats:
    """Aggregated bot statistics pulled from SQLite state."""

    predictions_total: int = 0
    last_prediction_at: datetime | None = None
    reports_total: int = 0
    last_report_at: datetime | None = None
    users_total: int = 0
    subscriptions_total: int = 0
    last_subscription_at: datetime | None = None
    degraded: bool = False


def _parse_dt(raw: object) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    try:
        value = str(raw).strip()
        if not value:
            return None
        dt = datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (name,),
    )
    return cur.fetchone() is not None


def _count_and_max(
    conn: sqlite3.Connection,
    table: str,
    *,
    max_column: str,
) -> tuple[int, datetime | None]:
    if not _table_exists(conn, table):
        return 0, None
    query = f"SELECT COUNT(*) AS cnt, MAX({max_column}) AS max_ts FROM {table}"
    cur = conn.execute(query)
    row = cur.fetchone()
    if not row:
        return 0, None
    return int(row["cnt"]), _parse_dt(row["max_ts"])


def _load_stats_sync(db_path: Path) -> BotStats:
    if not db_path.exists():
        return BotStats(degraded=True)
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:  # pragma: no cover - defensive fallback
        logger.warning("Не удалось подключиться к БД для статистики: %s", exc)
        return BotStats(degraded=True)
    conn.row_factory = sqlite3.Row
    try:
        predictions_total, last_prediction_at = _count_and_max(
            conn, "predictions", max_column="ts"
        )
        reports_total, last_report_at = _count_and_max(
            conn, "reports", max_column="created_at"
        )
        users_total, _ = _count_and_max(conn, "user_prefs", max_column="updated_at")
        subscriptions_total, last_subscription_at = _count_and_max(
            conn, "subscriptions", max_column="updated_at"
        )
    except sqlite3.Error as exc:  # pragma: no cover - defensive fallback
        logger.warning("Ошибка при сборе статистики бота: %s", exc)
        return BotStats(degraded=True)
    finally:
        conn.close()
    degraded = predictions_total == 0 and last_prediction_at is None
    return BotStats(
        predictions_total=predictions_total,
        last_prediction_at=last_prediction_at,
        reports_total=reports_total,
        last_report_at=last_report_at,
        users_total=users_total,
        subscriptions_total=subscriptions_total,
        last_subscription_at=last_subscription_at,
        degraded=degraded,
    )


async def _load_bot_stats() -> BotStats:
    db_path = Path(settings.DB_PATH)
    return await asyncio.to_thread(_load_stats_sync, db_path)


def _format_dt(value: datetime | None) -> str:
    if not value:
        return "—"
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _main_menu_builder() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔮 Сделать прогноз", callback_data="make_prediction")
    builder.button(text="ℹ️ Помощь", callback_data="show_help")
    builder.button(text="📚 Примеры", callback_data="show_examples")
    builder.button(text="📊 Статистика", callback_data="show_stats")
    builder.button(text="⚖️ Условия", callback_data="show_terms")
    builder.button(text="⚠️ Дисклеймер", callback_data="show_disclaimer")
    builder.adjust(2)
    return builder


async def _send_main_menu(message: Message) -> None:
    try:
        builder = _main_menu_builder()
        await message.answer(
            "🏆 <b>Главное меню Football Predictor Bot</b>\nВыберите действие из меню ниже:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        logger.debug("Главное меню отправлено пользователю %s", message.from_user.id)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error(
            "Ошибка при отправке главного меню пользователю %s: %s",
            message.from_user.id,
            exc,
        )
        await message.answer("❌ Ошибка при отправке меню. Попробуйте позже.", parse_mode="HTML")


async def _edit_or_send_main_menu(callback: CallbackQuery) -> None:
    builder = _main_menu_builder()
    menu_text = "🏆 <b>Главное меню Football Predictor Bot</b>\nВыберите действие из меню ниже:"
    try:
        await callback.message.edit_text(
            menu_text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except TelegramBadRequest as exc:
        logger.debug(
            "Невозможно отредактировать сообщение для пользователя %s: %s. Отправляем новое.",
            callback.from_user.id,
            exc,
        )
        await callback.message.answer(
            menu_text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    await callback.answer()


async def _build_stats_message() -> str:
    stats = await _load_bot_stats()
    lines = [
        "📊 <b>Статистика Football Predictor Bot</b>",
        "",
        f"Версия: {settings.APP_VERSION} ({settings.GIT_SHA})",
        f"Предсказаний сохранено: {stats.predictions_total}",
        f"Последний прогноз: {_format_dt(stats.last_prediction_at)}",
        f"Отчётов сформировано: {stats.reports_total}",
        f"Последний отчёт: {_format_dt(stats.last_report_at)}",
        f"Пользовательских профилей: {stats.users_total}",
        f"Активных подписок: {stats.subscriptions_total}",
        f"Последнее обновление подписки: {_format_dt(stats.last_subscription_at)}",
    ]
    if stats.degraded:
        lines.append("")
        lines.append("⚠️ Статистика доступна не полностью (DEGRADED)")
    return "\n".join(lines)


router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    try:
        CommandWithoutArgs.parse(message.text)
        logger.info(
            "Пользователь %s (%s) начал работу с ботом",
            message.from_user.id,
            message.from_user.username or "N/A",
        )
        await message.answer(
            "👋 <b>Добро пожаловать в Football Predictor Bot!</b>\n\n"
            "🤖 Я использую продвинутые алгоритмы ИИ и статистические модели для "
            "прогнозирования исходов футбольных матчей.\n"
            "🔮 Просто введите названия двух команд, и я предоставлю вам "
            "вероятностный прогноз, статистику и рекомендации по ставкам.\n"
            "💡 Используйте меню ниже или команду /help для получения справки.",
            parse_mode="HTML",
        )
        await _send_main_menu(message)
    except ValueError as exc:
        await message.answer(f"❌ {exc}", parse_mode="HTML")
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error(
            "Ошибка в обработчике /start для пользователя %s: %s",
            message.from_user.id,
            exc,
        )
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже.", parse_mode="HTML"
        )


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery) -> None:
    try:
        logger.debug("Пользователь %s вернулся в главное меню", callback.from_user.id)
        await _edit_or_send_main_menu(callback)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error(
            "Ошибка в обработчике возврата в главное меню для пользователя %s: %s",
            callback.from_user.id,
            exc,
        )
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_help")
async def show_help(callback: CallbackQuery) -> None:
    try:
        logger.debug("Пользователь %s запросил справку", callback.from_user.id)
        help_text = (
            "ℹ️ <b>Справка Football Predictor Bot</b>\n\n"
            "Доступные команды:\n"
            "• /start - Начало работы с ботом\n"
            "• /predict <code>Команда1 - Команда2</code> - Получить прогноз\n"
            "• /help - Показать эту справку\n"
            "• /examples - Примеры использования\n"
            "• /stats - Статистика бота\n"
            "• /terms - Условия использования\n"
            "• /disclaimer - Отказ от ответственности\n\n"
            "Используйте кнопки меню для навигации."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(
                help_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as exc:
            logger.debug(
                "Невозможно отредактировать сообщение для /help у %s: %s. Отправляем новое.",
                callback.from_user.id,
                exc,
            )
            await callback.message.answer(
                help_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("Ошибка в обработчике справки: %s", exc)
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_examples")
async def show_examples(callback: CallbackQuery) -> None:
    try:
        logger.debug("Пользователь %s запросил примеры", callback.from_user.id)
        examples_text = (
            "📚 <b>Примеры использования Football Predictor Bot</b>\n\n"
            "1. Прогноз для конкретного матча:\n"
            "<code>/predict Бавария - Боруссия Д</code>\n\n"
            "2. Прогноз для матча Лиги Чемпионов:\n"
            "<code>/predict Реал Мадрид - Манчестер Сити</code>\n\n"
            "3. Прогноз для матчей АПЛ:\n"
            "<code>/predict Ливерпуль - Челси</code>\n\n"
            "Бот предоставит вероятности исходов, тоталов, рекомендации и т.д."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(
                examples_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as exc:
            logger.debug(
                "Невозможно отредактировать сообщение для /examples у %s: %s. Отправляем новое.",
                callback.from_user.id,
                exc,
            )
            await callback.message.answer(
                examples_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("Ошибка в обработчике примеров: %s", exc)
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_stats")
async def show_stats(callback: CallbackQuery) -> None:
    try:
        logger.debug("Пользователь %s запросил статистику", callback.from_user.id)
        stats_text = await _build_stats_message()
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(
                stats_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as exc:
            logger.debug(
                "Невозможно отредактировать сообщение для /stats у %s: %s. Отправляем новое.",
                callback.from_user.id,
                exc,
            )
            await callback.message.answer(
                stats_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("Ошибка в обработчике статистики: %s", exc)
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_terms")
async def show_terms(callback: CallbackQuery) -> None:
    try:
        logger.debug("Пользователь %s запросил условия", callback.from_user.id)
        terms_text = (
            "⚖️ <b>Условия использования Football Predictor Bot</b>\n\n"
            "1. Бот предоставляется 'как есть' без каких-либо гарантий.\n"
            "2. Информация, предоставляемая ботом, носит исключительно информационный характер.\n"
            "3. Администрация бота не несет ответственности за любые убытки или ущерб, "
            "возникшие в результате использования информации, предоставляемой ботом.\n"
            "4. Используя бота, вы соглашаетесь с этими условиями."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.button(text="⚠️ Дисклеймер", callback_data="show_disclaimer")
        builder.adjust(2)
        try:
            await callback.message.edit_text(
                terms_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as exc:
            logger.debug(
                "Невозможно отредактировать сообщение для /terms у %s: %s. Отправляем новое.",
                callback.from_user.id,
                exc,
            )
            await callback.message.answer(
                terms_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        await callback.answer()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("Ошибка в обработчике условий: %s", exc)
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_disclaimer")
async def show_disclaimer(callback: CallbackQuery) -> None:
    try:
        logger.debug("Пользователь %s запросил дисклеймер", callback.from_user.id)
        disclaimer_text = DISCLAIMER_TEXT
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.button(text="📋 Условия", callback_data="show_terms")
        builder.adjust(2)
        try:
            await callback.message.edit_text(
                disclaimer_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as exc:
            logger.debug(
                "Невозможно отредактировать сообщение для /disclaimer у %s: %s. Отправляем новое.",
                callback.from_user.id,
                exc,
            )
            await callback.message.answer(
                disclaimer_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error("Ошибка в обработчике дисклеймера: %s", exc)
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


__all__ = ["router"]
