# telegram/handlers/start.py
"""Обработчик команды /start и главного меню."""
import asyncio
from typing import Union
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest # Добавлен импорт
from logger import logger

# Импорт текста дисклеймера из terms.py
from telegram.handlers.terms import DISCLAIMER_TEXT

router = Router()

START_MESSAGE = (
    "👋 <b>Добро пожаловать в Football Predictor Bot!</b>\n\n"
    "🤖 Я использую продвинутые алгоритмы ИИ и статистические модели для "
    "прогнозирования исходов футбольных матчей.\n"
    "🔮 Просто введите названия двух команд, и я предоставлю вам "
    "вероятностный прогноз, статистику и рекомендации по ставкам.\n"
    "💡 Используйте меню ниже или команду /help для получения справки."
)

MAIN_MENU_TEXT = "🏆 <b>Главное меню Football Predictor Bot</b>\nВыберите действие из меню ниже:"

# --- Новая функция для отправки главного меню ---
async def send_main_menu(message: Message):
    """Отправляет главное меню как новое сообщение."""
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔮 Сделать прогноз", callback_data="make_prediction")
        builder.button(text="ℹ️ Помощь", callback_data="show_help")
        builder.button(text="📚 Примеры", callback_data="show_examples")
        builder.button(text="📊 Статистика", callback_data="show_stats")
        builder.button(text="⚖️ Условия", callback_data="show_terms")
        builder.button(text="⚠️ Дисклеймер", callback_data="show_disclaimer")
        builder.adjust(2)

        menu_text = MAIN_MENU_TEXT
        await message.answer(menu_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        logger.debug(f"Главное меню отправлено пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке главного меню пользователю {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при отправке меню. Попробуйте позже.", parse_mode="HTML")

# --- Исправленная функция для отображения/редактирования главного меню через callback ---
async def edit_or_send_main_menu(callback: CallbackQuery):
    """Отображает главное меню, пытаясь отредактировать сообщение или отправляя новое."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} ({callback.from_user.username or 'N/A'}) запросил главное меню")

        builder = InlineKeyboardBuilder()
        builder.button(text="🔮 Сделать прогноз", callback_data="make_prediction")
        builder.button(text="ℹ️ Помощь", callback_data="show_help")
        builder.button(text="📚 Примеры", callback_data="show_examples")
        builder.button(text="📊 Статистика", callback_data="show_stats")
        builder.button(text="⚖️ Условия", callback_data="show_terms")
        builder.button(text="⚠️ Дисклеймер", callback_data="show_disclaimer")
        builder.adjust(2)

        menu_text = MAIN_MENU_TEXT
        try:
            # Сначала пытаемся отредактировать существующее сообщение
            await callback.message.edit_text(menu_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest as e:
            # Если редактирование невозможно (например, сообщение устарело),
            # отправляем новое сообщение.
            logger.debug(f"Невозможно отредактировать сообщение для пользователя {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(menu_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
        await callback.answer() # Всегда отвечаем на callback
    except Exception as e:
        logger.error(f"Ошибка в обработчике главного меню для пользователя {callback.from_user.id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    try:
        logger.info(f"Пользователь {message.from_user.id} ({message.from_user.username or 'N/A'}) начал работу с ботом")
        # Отправляем приветственное сообщение
        await message.answer(START_MESSAGE, parse_mode="HTML")
        # Отправляем главное меню как новое сообщение
        await send_main_menu(message)
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при запуске бота. Попробуйте позже.", parse_mode="HTML")

# Обработчик callback-а для возврата в главное меню
@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возвращает пользователя в главное меню."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} вернулся в главное меню")
        # Используем функцию, которая пытается редактировать или отправить новое
        await edit_or_send_main_menu(callback)
    except Exception as e:
        logger.error(f"Ошибка в обработчике возврата в главное меню для пользователя {callback.from_user.id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "show_help")
async def show_help(callback: CallbackQuery):
    """Отображает справку."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил справку")
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
            await callback.message.edit_text(help_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.debug(f"Невозможно отредактировать сообщение для /help у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(help_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике справки: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "show_examples")
async def show_examples(callback: CallbackQuery):
    """Отображает примеры использования."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил примеры")
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
            await callback.message.edit_text(examples_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.debug(f"Невозможно отредактировать сообщение для /examples у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(examples_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике примеров: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "show_stats")
async def show_stats(callback: CallbackQuery):
    """Отображает статистику бота."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил статистику")
        # TODO: Добавить реальную статистику
        stats_text = (
            "📊 <b>Статистика Football Predictor Bot</b>\n\n"
            "Версия: 1.0.0\n"
            "Обработано прогнозов: 0\n"
            "Активных пользователей: 1\n"
            "Точность прогнозов: N/A\n\n"
            "<i>Статистика будет обновляться по мере работы бота.</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(stats_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.debug(f"Невозможно отредактировать сообщение для /stats у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(stats_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике статистики: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "show_terms")
async def show_terms(callback: CallbackQuery):
    """Отображает условия использования."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил условия")
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
            logger.debug(f"Невозможно отредактировать сообщение для /terms у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(terms_text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике условий: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "show_disclaimer")
async def show_disclaimer(callback: CallbackQuery):
    """Отображает дисклеймер."""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} запросил дисклеймер")
        # Используем импортированный текст дисклеймера
        disclaimer_text = DISCLAIMER_TEXT
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.button(text="📋 Условия", callback_data="show_terms")
        builder.adjust(2)
        try:
            await callback.message.edit_text(disclaimer_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.debug(f"Невозможно отредактировать сообщение для /disclaimer у {callback.from_user.id}: {e}. Отправляем новое.")
            await callback.message.answer(disclaimer_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике дисклеймера: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

# Экспорт роутера
__all__ = ["router"]
