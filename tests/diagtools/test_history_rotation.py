"""
/**
 * @file: tests/diagtools/test_history_rotation.py
 * @description: Tests ensuring diagnostics history rotation obeys DIAG_HISTORY_KEEP.
 * @dependencies: diagtools.reports_html
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from diagtools import reports_html


def test_history_rotation_keeps_latest_entries(tmp_path) -> None:
    diag_dir = tmp_path / "diagnostics"
    diag_dir.mkdir()
    start = datetime.now(UTC)
    for idx in range(3):
        status = {"Section": {"status": "✅", "note": str(idx)}}
        reports_html.append_history(
            diag_dir=diag_dir,
            statuses=status,
            trigger="cron",
            keep=2,
            started_at=start + timedelta(seconds=idx),
            finished_at=start + timedelta(seconds=idx, milliseconds=500),
            html_path=None,
        )
    jsonl = (diag_dir / "history" / "history.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl) == 2
    entries = reports_html.load_history(diag_dir, limit=2)
    assert len(entries) == 2
    assert entries[0].timestamp >= entries[1].timestamp
