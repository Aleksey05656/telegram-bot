"""tgbotapp package bundling middlewares, handlers and services."""

# NOTE: пакет tgbotapp перекрывает одноимённые сторонние библиотеки, поэтому
# экспортируем ключевые подпакеты явно, чтобы избегать конфликтов при импортах.

__all__ = [
    "bot",
    "dependencies",
    "handlers",
    "middlewares",
    "models",
    "ratelimiter",
    "sender",
    "services",
    "utils",
    "widgets",
]
