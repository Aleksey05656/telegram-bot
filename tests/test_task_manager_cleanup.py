"""
@file: test_task_manager_cleanup.py
@description: Tests for TaskManager cleanup utilities
@dependencies: workers.task_manager
@created: 2025-09-16
"""
import pytest
pytest.importorskip("numpy")

pytestmark = pytest.mark.needs_np

from datetime import datetime, timedelta

from workers.task_manager import TaskManager


def test_cleanup_no_connection():
    tm = TaskManager()
    assert tm.cleanup() == 0


def test_clear_all_with_stubs():
    tm = TaskManager()

    class Q:
        def __init__(self):
            self.count = 2
            self.emptied = False
            self.job_ids = []

        def empty(self):
            self.emptied = True

        def fetch_job(self, job_id):
            return None

    tm.prediction_queue = Q()
    tm.retraining_queue = Q()
    removed = tm.clear_all()
    assert removed == 4
    assert tm.prediction_queue.emptied
    assert tm.retraining_queue.emptied


def test_cleanup_removes_old_jobs(monkeypatch):
    tm = TaskManager()

    class JobStub:
        def __init__(self, age_days):
            self.enqueued_at = datetime.utcnow() - timedelta(days=age_days)
            self.deleted = False

        def delete(self):
            self.deleted = True

    class QueueStub:
        job_ids = ["a", "b"]

        def fetch_job(self, job_id):
            return store[job_id]

    store = {"a": JobStub(age_days=10), "b": JobStub(age_days=1)}

    tm.redis_conn = object()
    tm.prediction_queue = QueueStub()
    tm.retraining_queue = None
    removed = tm.cleanup(days=7)
    assert removed == 1
    assert store["a"].deleted is True
