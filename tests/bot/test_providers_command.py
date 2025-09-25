"""
/**
 * @file: tests/bot/test_providers_command.py
 * @description: Validates /providers admin command access and rendering.
 * @dependencies: app.bot.routers.commands
 * @created: 2025-10-28
 */
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.bot.routers import commands


class DummyMessage:
    def __init__(self, user_id: int) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.responses: list[str] = []

    async def answer(self, text: str, reply_markup=None) -> None:  # noqa: D401
        self.responses.append(text)


@pytest.mark.asyncio
async def test_providers_command_requires_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "_ADMIN_IDS", {99})
    monkeypatch.setattr(commands, "observe_render_latency", lambda *args, **kwargs: None)
    monkeypatch.setattr(commands, "record_command", lambda *args, **kwargs: None)
    message = DummyMessage(user_id=1)
    await commands.handle_providers(message, SimpleNamespace(args=""))
    assert message.responses
    assert "только администраторам" in message.responses[0]


@pytest.mark.asyncio
async def test_providers_command_renders_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "_ADMIN_IDS", {42})
    monkeypatch.setattr(commands, "observe_render_latency", lambda *args, **kwargs: None)
    monkeypatch.setattr(commands, "record_command", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        commands,
        "reliability_v2",
        SimpleNamespace(
            get_provider_scores=lambda league, market: [
                {
                    "provider": "csv",
                    "score": 0.74,
                    "coverage": 0.82,
                    "samples": 120,
                    "fresh_share": 0.7,
                    "latency_ms": 180,
                },
                {
                    "provider": "http",
                    "score": 0.55,
                    "coverage": 0.6,
                    "samples": 90,
                    "fresh_share": 0.5,
                    "latency_ms": 450,
                },
            ],
            explain_components=lambda provider, league, market: {},
        ),
    )
    message = DummyMessage(user_id=42)
    await commands.handle_providers(message, SimpleNamespace(args="EPL 1X2"))
    assert message.responses
    text = message.responses[0]
    assert "Reliability v2" in text
    assert "csv" in text
    assert "⚠️" in text  # низкий скор помечается
