"""
@file: test_predictions_store.py
@description: Test SQLitePredictionsStore read/write operations.
@dependencies: sqlite3, numpy
@created: 2025-09-15
"""
import sqlite3
from pathlib import Path

import pytest

from storage.persistence import SQLitePredictionsStore


@pytest.mark.needs_np
def test_bulk_write_and_upsert(tmp_path: Path):
    db = tmp_path / "preds.sqlite"
    store = SQLitePredictionsStore(db_path=str(db))
    records = [
        ("m1", "1x2", "1", 0.5, {"ts": "t", "season": "s", "extra": {}}),
        ("m1", "1x2", "x", 0.3, {"ts": "t", "season": "s", "extra": {}}),
    ]
    store.bulk_write(records)
    store.bulk_write(records)  # upsert
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT COUNT(*) FROM predictions")
    assert cur.fetchone()[0] == 2
    conn.close()
