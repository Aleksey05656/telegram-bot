"""
@file: runtime_state.py
@description: Shared runtime readiness state flags.
@dependencies: time
@created: 2025-09-30
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeState:
    """In-memory readiness flags tracking critical components."""

    db_ready: bool = False
    polling_ready: bool = False
    scheduler_ready: bool = False
    started_at: float = field(default_factory=time.time)


STATE = RuntimeState()


__all__ = ["RuntimeState", "STATE"]
