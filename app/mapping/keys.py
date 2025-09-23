"""
@file: keys.py
@description: Helpers for normalizing team names and generating internal match keys.
@dependencies: datetime, re, unicodedata
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime


__all__ = ["normalize_name", "build_match_key"]


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_name(value: str | None) -> str:
    """Normalize textual identifier for matching operations."""

    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = _NON_ALNUM_RE.sub("-", normalized)
    return normalized.strip("-")


def build_match_key(home: str, away: str, kickoff: datetime | None) -> str:
    """Generate deterministic match key for mapping table alignment."""

    home_norm = normalize_name(home)
    away_norm = normalize_name(away)
    kickoff_norm = _format_kickoff(kickoff)
    return f"{home_norm}|{away_norm}|{kickoff_norm}"


def _format_kickoff(kickoff: datetime | None) -> str:
    if kickoff is None:
        return ""
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)
    kickoff_utc = kickoff.astimezone(UTC)
    return kickoff_utc.strftime("%Y-%m-%dT%H:%MZ")
