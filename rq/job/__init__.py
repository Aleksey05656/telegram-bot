"""
/**
 * @file: rq/job/__init__.py
 * @description: Minimal RQ Job stub for offline tests.
 * @dependencies: none
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Tuple

__all__ = ["Job"]


@dataclass(slots=True)
class Job:
    func: Callable[..., Any]
    args: Tuple[Any, ...]
    kwargs: dict[str, Any]

