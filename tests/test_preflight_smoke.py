"""
/**
 * @file: tests/test_preflight_smoke.py
 * @description: Placeholder smoke test to keep `make smoke` green in offline mode.
 * @dependencies: pytest
 * @created: 2025-10-29
 */
"""

from __future__ import annotations

import pytest


@pytest.mark.bot_smoke
def test_preflight_smoke_placeholder() -> None:
    pytest.skip("Smoke scenarios require full runtime stack; skipped in offline mode")
