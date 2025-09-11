# telegram/handlers/help.py
"""Обработчик команды /help и связанных команд (/examples, /stats)."""
import textwrap

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest  # Добавлен импорт
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Исправленный импорт кэша
from logger import logger
from telegram.models import CommandWithoutArgs

router = Router()


@router.message(Command("help"))
@router.message(Command("examples"))
@router.message(Command("stats"))
async def cmd_help(message: Message):
    """Обработчик команд /help, /examples, /stats."""
    try:
        CommandWithoutArgs.parse(message.text)
        command = message.get_command(pure=True).lstrip("/")
        logger.debug(f"Пользователь {message.from_user.id} запросил {command}")

        if command == "help":
            help_text = textwrap.dedent(
                """
                ℹ️ <b>Справка Football Predictor Bot</b>

                Доступные команды:
                • /start - Начало работы с ботом
                • /predict <code>Команда1 - Команда2</code> - Получить прогноз
                • /help - Показать эту справку
                • /examples - Примеры использования
                • /stats - Статистика бота
                • /terms - Условия использования
                • /disclaimer - Отказ от ответственности

                Используйте кнопки меню для навигации.
            """
            ).strip()
        elif command == "examples":
            help_text = textwrap.dedent(
                """
                📚 <b>Примеры использования Football Predictor Bot</b>

                1. Прогноз для конкретного матча:
                <code>/predict Бавария - Боруссия Д</code>

                2. Прогноз для матча Лиги Чемпионов:
                <code>/predict Реал Мадрид - Манчестер Сити</code>

                3. Прогноз для матчей АПЛ:
                <code>/predict Ливерпуль - Челси</code>

                Бот предоставит вероятности исходов, тоталов, рекомендации и т.д.
            """
            ).strip()
        elif command == "stats":
            # TODO: Добавить реальную статистику
            help_text = textwrap.dedent(
                """
                📊 <b>Статистика Football Predictor Bot</b>

                Версия: 1.0.0
                Обработано прогнозов: 0
                Активных пользователей: 1
                Точность прогнозов: N/A

                <i>Статистика будет обновляться по мере работы бота.</i>
            """
            ).strip()
        else:
            help_text = "ℹ️ Используйте /help для получения справки."

        await message.answer(help_text, parse_mode="HTML")
        logger.info(
            f"{command.capitalize()} отправлен(-а) пользователю {message.from_user.id}"
        )
    except ValueError as e:
        await message.answer(f"❌ {e}", parse_mode="HTML")
    except Exception as e:
        error_msg = f"Ошибка при отправке {command} пользователю {message.from_user.id}"
        logger.error(f"{error_msg}: {e}", exc_info=True)
        # Отправляем пользователю упрощенное сообщение об ошибке
        await message.answer(
            f"❌ Произошла ошибка при отправке {command}. Попробуйте позже.",
            parse_mode="HTML",
        )


# --- Обработчики Callback-запросов для меню (если они вызываются не из start.py) ---
# Эти функции дублируют логику из start.py и также обернуты в try...except.
# В идеале, эту логику лучше вынести в отдельный модуль утилит.


@router.callback_query(F.data == "show_help")
async def cb_show_help(callback: CallbackQuery):
    """Callback обработчик для отображения справки."""
    try:
        logger.debug(
            f"Пользователь {callback.from_user.id} запросил справку через callback"
        )
        help_text = textwrap.dedent(
            """
            ℹ️ <b>Справка Football Predictor Bot</b>

            Доступные команды:
            • /start - Начало работы с ботом
            • /predict <code>Команда1 - Команда2</code> - Получить прогноз
            • /help - Показать эту справку
            • /examples - Примеры использования
            • /stats - Статистика бота
            • /terms - Условия использования
            • /disclaimer - Отказ от ответственности

            Используйте кнопки меню для навигации.
        """
        ).strip()
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(
                help_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            logger.debug(
                f"Невозможно отредактировать сообщение для /help (callback) у {callback.from_user.id}: {e}. Отправляем новое."
            )
            await callback.message.answer(
                help_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в callback обработчике справки: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_examples")
async def cb_show_examples(callback: CallbackQuery):
    """Callback обработчик для отображения примеров."""
    try:
        logger.debug(
            f"Пользователь {callback.from_user.id} запросил примеры через callback"
        )
        examples_text = textwrap.dedent(
            """
            📚 <b>Примеры использования Football Predictor Bot</b>

            1. Прогноз для конкретного матча:
            <code>/predict Бавария - Боруссия Д</code>

            2. Прогноз для матча Лиги Чемпионов:
            <code>/predict Реал Мадрид - Манчестер Сити</code>

            3. Прогноз для матчей АПЛ:
            <code>/predict Ливерпуль - Челси</code>

            Бот предоставит вероятности исходов, тоталов, рекомендации и т.д.
        """
        ).strip()
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(
                examples_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            logger.debug(
                f"Невозможно отредактировать сообщение для /examples (callback) у {callback.from_user.id}: {e}. Отправляем новое."
            )
            await callback.message.answer(
                examples_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в callback обработчике примеров: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "show_stats")
async def cb_show_stats(callback: CallbackQuery):
    """Callback обработчик для отображения статистики."""
    try:
        logger.debug(
            f"Пользователь {callback.from_user.id} запросил статистику через callback"
        )
        # TODO: Добавить реальную статистику
        stats_text = textwrap.dedent(
            """
            📊 <b>Статистика Football Predictor Bot</b>

            Версия: 1.0.0
            Обработано прогнозов: 0
            Активных пользователей: 1
            Точность прогнозов: N/A

            <i>Статистика будет обновляться по мере работы бота.</i>
        """
        ).strip()
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="main_menu")
        builder.adjust(1)
        try:
            await callback.message.edit_text(
                stats_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            logger.debug(
                f"Невозможно отредактировать сообщение для /stats (callback) у {callback.from_user.id}: {e}. Отправляем новое."
            )
            await callback.message.answer(
                stats_text, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в callback обработчике статистики: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


# Экспорт роутера
__all__ = ["router"]
