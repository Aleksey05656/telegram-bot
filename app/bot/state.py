"""
/**
 * @file: app/bot/state.py
 * @description: Shared singletons for bot caches and services.
 * @dependencies: app.bot.caching, app.bot.services
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from typing import Any

from config import settings

from .caching import TTLCache
from .services import Prediction, PredictionFacade

LIST_CACHE = TTLCache[str, list[Prediction]](
    maxsize=128, ttl_seconds=float(settings.CACHE_TTL_SECONDS)
)
MATCH_CACHE = TTLCache[str, Prediction](
    maxsize=256, ttl_seconds=float(settings.CACHE_TTL_SECONDS)
)
PAGINATION_CACHE = TTLCache[str, dict[str, Any]](
    maxsize=256, ttl_seconds=float(settings.CACHE_TTL_SECONDS)
)
FACADE = PredictionFacade()

__all__ = ["LIST_CACHE", "MATCH_CACHE", "PAGINATION_CACHE", "FACADE"]
