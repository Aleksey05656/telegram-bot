"""
@file: test_todo_barriers.py
@description: tests deterministic behavior for unfinished handlers
@dependencies: app.handlers
@created: 2025-09-10
"""

import pytest
from app import handlers


@pytest.mark.asyncio
async def test_some_handler_returns_note() -> None:
    out = await handlers.some_handler({})
    assert out["status"] == "ok"
    assert "note" in out
