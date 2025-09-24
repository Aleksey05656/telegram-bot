"""
@file: tests/bot/test_value_commands.py
@description: Tests for Telegram command handlers related to value features.
@dependencies: asyncio, pytest
@created: 2025-09-24
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.value_detector import ValuePick

from app.bot.routers import commands


class DummyMessage:
    def __init__(self) -> None:
        self.responses: list[str] = []
        self.from_user = SimpleNamespace(id=42)

    async def answer(self, text: str, reply_markup=None) -> None:  # noqa: D401
        self.responses.append(text)


class FakeProvider:
    async def close(self) -> None:  # pragma: no cover - simple stub
        return None


def _ensure_commands_enabled() -> None:
    if not getattr(commands.settings, "ENABLE_VALUE_FEATURES", False):
        commands.settings.ENABLE_VALUE_FEATURES = True
        importlib.reload(commands)  # type: ignore[call-arg]
        commands.settings.ENABLE_VALUE_FEATURES = True


@pytest.mark.asyncio
async def test_handle_value_renders_picks(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_commands_enabled()
    pick = ValuePick(
        match_key="arsenal|manchester-city|2024-09-01T18:00Z",
        market="1X2",
        selection="HOME",
        fair_price=1.9,
        market_price=1.7,
        edge_pct=12.5,
        model_probability=0.45,
        market_probability=0.40,
        confidence=0.8,
        provider="csv",
        pulled_at=datetime(2024, 9, 1, 10, tzinfo=UTC),
        kickoff_utc=datetime(2024, 9, 1, 18, tzinfo=UTC),
    )
    cards = [
        {
            "match": {"home": "Arsenal", "away": "Manchester City", "league": "EPL", "kickoff": pick.kickoff_utc},
            "pick": pick,
        }
    ]

    class FakeService:
        async def value_picks(self, *, target_date, league):  # noqa: D401
            return cards

    monkeypatch.setattr(commands, "_create_value_service", lambda: (FakeService(), FakeProvider()))
    message = DummyMessage()
    await commands.handle_value(message, SimpleNamespace(args="limit=1"))
    assert message.responses
    assert "Value-кейсы" in message.responses[0]
    assert "Arsenal" in message.responses[0]


@pytest.mark.asyncio
async def test_handle_compare_outputs_table(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_commands_enabled()

    class FakeService:
        async def compare(self, *, query: str, target_date):  # noqa: D401
            return {
                "match": {"home": "Arsenal", "away": "Manchester City", "league": "EPL", "kickoff": datetime(2024, 9, 1, 18, tzinfo=UTC)},
                "picks": [],
                "markets": {
                    "1X2": {
                        "HOME": {"model_p": 0.45, "market_p": 0.40, "price": 1.7},
                        "AWAY": {"model_p": 0.25, "market_p": 0.35, "price": 3.2},
                    }
                },
            }

    monkeypatch.setattr(commands, "_create_value_service", lambda: (FakeService(), FakeProvider()))
    message = DummyMessage()
    await commands.handle_compare(message, SimpleNamespace(args="Arsenal"))
    assert message.responses
    assert "⚖️" in message.responses[0]
    assert "HOME" in message.responses[0]


@pytest.mark.asyncio
async def test_handle_alerts_updates_preferences(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_commands_enabled()
    state = {"enabled": False, "edge_threshold": 5.0, "league": None}
    monkeypatch.setattr(commands, "get_value_alert", lambda user_id: state.copy())

    def _upsert(user_id: int, *, enabled=None, edge_threshold=None, league=None, db_path=None):
        if enabled is not None:
            state["enabled"] = bool(enabled)
        if edge_threshold is not None:
            state["edge_threshold"] = float(edge_threshold)
        if league is not None:
            state["league"] = league
        return state.copy()

    monkeypatch.setattr(commands, "upsert_value_alert", _upsert)
    message = DummyMessage()
    await commands.handle_alerts(message, SimpleNamespace(args="on edge=6.5 EPL"))
    assert message.responses
    assert "6.5%" in message.responses[0]
    assert "EPL" in message.responses[0]
