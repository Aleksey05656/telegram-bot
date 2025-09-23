# @file: runtime_lock.py
# @description: Cooperative runtime lock to prevent multiple instances.
# @dependencies: config.py, logger.py
"""Filesystem-based runtime lock helpers."""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Optional

from logger import logger


class RuntimeLockError(RuntimeError):
    """Raised when the runtime lock cannot be acquired."""


@dataclass(slots=True)
class RuntimeLock:
    """A cooperative filesystem lock used to guard single-instance launches."""

    path: Path
    _file: Optional[IO[str]] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None

    async def acquire(self) -> None:
        """Acquire the runtime lock asynchronously."""
        if self._file is not None:
            logger.debug("Runtime lock already acquired for %s", self.path)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        self._loop = loop
        try:
            await loop.run_in_executor(None, self._acquire_blocking)
        except RuntimeLockError:
            raise

    async def release(self) -> None:
        """Release the runtime lock asynchronously."""
        if self._file is None:
            return
        loop = self._loop or asyncio.get_running_loop()
        await loop.run_in_executor(None, self._release_blocking)

    def _acquire_blocking(self) -> None:
        try:
            file_handle = self.path.open("w+")
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise RuntimeLockError(f"Cannot open runtime lock file: {self.path}") from exc
        try:
            self._lock_fd(file_handle)
        except Exception as exc:
            file_handle.close()
            raise RuntimeLockError(
                f"Another instance is already running (lock: {self.path})"
            ) from exc
        file_handle.write(f"pid={os.getpid()}\n")
        file_handle.flush()
        self._file = file_handle
        logger.info("Runtime lock acquired at %s", self.path)

    def _release_blocking(self) -> None:
        file_handle = self._file
        self._file = None
        if not file_handle:
            return
        try:
            self._unlock_fd(file_handle)
        finally:
            try:
                file_handle.close()
            finally:
                try:
                    self.path.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass
        logger.info("Runtime lock released at %s", self.path)

    def _lock_fd(self, file_handle: IO[str]) -> None:
        fd = file_handle.fileno()
        if sys.platform == "win32":  # pragma: no cover - windows path
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeLockError("Runtime lock already taken") from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeLockError("Runtime lock already taken") from exc

    def _unlock_fd(self, file_handle: IO[str]) -> None:
        fd = file_handle.fileno()
        if sys.platform == "win32":  # pragma: no cover - windows path
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass

    async def __aenter__(self) -> "RuntimeLock":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.release()


__all__ = ["RuntimeLock", "RuntimeLockError"]
