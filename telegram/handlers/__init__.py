# app/telegram/handlers/__init__.py
# Регистрация всех обработчиков команд.
from aiogram import Dispatcher

# Импортируем сами роутеры/хендлеры
from . import help, predict, start


def register_handlers(dp: Dispatcher):
    """Регистрирует все обработчики команд в диспетчере."""
    dp.include_router(start.router)
    dp.include_router(help.router)
    dp.include_router(predict.router)
