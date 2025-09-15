"""
@file: test_task_manager_cleanup_smoke.py
@description: smoke test for TaskManager.cleanup
@dependencies: workers.task_manager
@created: 2025-09-17
"""
import pytest

from workers.task_manager import TaskManager

pytest.importorskip("numpy")

pytestmark = pytest.mark.needs_np


def test_cleanup_smoke():
    tm = TaskManager()
    assert tm.cleanup() == 0
