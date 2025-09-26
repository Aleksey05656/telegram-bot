"""
@file: __init__.py
@description: SportMonks data access package exposing client, endpoints and data schemas.
@dependencies: sportmonks.client, sportmonks.endpoints, sportmonks.schemas
@created: 2025-09-23

High-level SportMonks data access helpers.
"""
from .client import SportMonksClient
from .endpoints import SportMonksEndpoints
from .schemas import (
    Bookmaker,
    Event,
    Fixture,
    LineupPlayerDetail,
    Market,
    OddsQuote,
    Participant,
    Score,
    StandingRow,
    TeamStats,
    XGValue,
)

__all__ = [
    "SportMonksClient",
    "SportMonksEndpoints",
    "Fixture",
    "Participant",
    "Score",
    "Event",
    "TeamStats",
    "LineupPlayerDetail",
    "XGValue",
    "StandingRow",
    "OddsQuote",
    "Market",
    "Bookmaker",
]
