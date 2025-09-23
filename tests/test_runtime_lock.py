# @file: test_runtime_lock.py
from pathlib import Path

import pytest

from app.runtime_lock import RuntimeLock, RuntimeLockError


@pytest.mark.asyncio
async def test_second_instance_cannot_acquire(tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime.lock"
    first = RuntimeLock(lock_path)
    await first.acquire()

    second = RuntimeLock(lock_path)
    with pytest.raises(RuntimeLockError):
        await second.acquire()

    await first.release()


@pytest.mark.asyncio
async def test_lock_released_after_context(tmp_path: Path) -> None:
    lock_path = tmp_path / "ctx.lock"
    async with RuntimeLock(lock_path) as lock:
        assert lock_path.exists()
    assert not lock_path.exists()
