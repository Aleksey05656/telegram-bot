"""
@file: test_runtime_lock_stale.py
@description: Ensure runtime lock recovers from stale PID entries.
@dependencies: app.runtime_lock
@created: 2025-09-30
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime_lock import RuntimeLock


@pytest.mark.asyncio()
async def test_runtime_lock_allows_stale_pid(tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime.lock"
    lock_path.write_text("pid=999999\n", encoding="utf-8")
    lock = RuntimeLock(lock_path)
    await lock.acquire()
    try:
        assert lock._file is not None  # internal file handle present
    finally:
        await lock.release()
    assert not lock_path.exists()
