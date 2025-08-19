# telegram/handlers/terms.py
"""Обработчик команд /terms и /disclaimer, а также связанных callback-ов."""
from typing import Union
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest # Добавлен импорт
from logger import logger

# Исправленный импорт кэша
from database.cache_postgres import cache

router = Router()

DISCLAIMER_TEXT = (
    "⚖️ <b>Условия использования и отказ от ответственности</b>\n\n"
    "1. Бот предоставляется 'как есть' без каких-либо гарантий.\n"
    "2. Информация, предоставляемая ботом, носит исключительно информационный характер.\n"
    "3. Администрация бота не несет ответственности за любые убытки или ущерб, "
    "возникшие в результате использования информации, предоставляемой ботом."
)

@router.message(Command("terms"))
@router.message(Command("disclaimer"))
async def cmd_terms(message: Message):
    """Обработчик команд /terms и /disclaimer."""
    try:
        command = message.get_command(pure=True).lstrip('/')
        logger.debug(f"Пользователь {message.from_user.id} запросил {command}")

        if command == "terms":
            text_to_send = (
                "⚖️ <b>Условия использования Football Predictor Bot</b>\n\n"
                "1. Бот предоставляется 'как есть' без каких-либо гарантий.\n"
                "2. Информация, предоставляемая ботом, носит исключительно информационный характер.\n"
                "3. Администрация бота не несет ответственности за любые убытки или ущерб, "
                "возникшие в результате использования информации, предоставляемой ботом.\n"
                "4. Используя бота, вы соглашаетесь с этими условиями."
            )
        elif command == "disclaimer":
            text_to_send = DISCLAIMER_TEXT
        else:
            text_to_send = "ℹ️ Используйте /terms или /disclaimer для получения информации."

        await message.answer(text_to_send, parse_mode="HTML")
        logger.info(f"{command.capitalize()} отправлен(-а) пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке {command} пользователю {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при отправке информации.", parse_mode="HTML")

# --- Обработчики Callback-запросов для меню (если они вызываются не из start.py) ---
# Эти функции дублируют логику из start.py и также обернуты в try...except.

@router.callback_query(F.data == "show_terms")
async def cb_show_terms(callback: CallbackQuery):
    """Callback обработчик для отображения условий."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил условия через callback")
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
            await callback.message.edit_text(terms_text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)
        except TelegramBadRequest as e:
            logger.debug(f"Невозможно отредактировать сообщение для /terms (callback) у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(terms_text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в callback обработчике условий: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "show_disclaimer")
async def cb_show_disclaimer(callback: CallbackQuery):
    """Callback обработчик для отображения дисклеймера."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил дисклеймер через callback")
        disclaimer_text = DISCLAIMER_TEXT
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.button(text="📋 Условия", callback_data="show_terms")
        builder.adjust(2)
        try:
            await callback.message.edit_text(disclaimer_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.debug(f"Невозможно отредактировать сообщение для /disclaimer (callback) у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(disclaimer_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в callback обработчике дисклеймера: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

# Экспорт роутера
__all__ = ["router"]
