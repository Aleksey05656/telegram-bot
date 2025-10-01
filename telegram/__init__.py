"""Telegram bot package with middlewares, handlers and services."""

# NOTE: этот пакет переопределяет одноимённый пакет PyPI. Экспортируем ключевые
# подпакеты для явного указания локальной структуры и избежания конфликтов.

__all__ = [
    "bot",
    "dependencies",
    "handlers",
    "middlewares",
    "models",
    "services",
    "utils",
    "widgets",
]
