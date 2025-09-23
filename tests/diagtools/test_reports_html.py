"""
/**
 * @file: tests/diagtools/test_reports_html.py
 * @description: Unit tests for diagnostics HTML dashboard generation.
 * @dependencies: diagtools.reports_html
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

from datetime import UTC, datetime
from diagtools import reports_html


def test_build_dashboard_creates_svg_and_history(tmp_path) -> None:
    diag_dir = tmp_path / "diagnostics"
    diag_dir.mkdir()
    md_path = diag_dir / "DIAGNOSTICS.md"
    md_path.write_text("# md", encoding="utf-8")
    statuses = {
        "Data Quality": {"status": "⚠️", "note": "issues=3"},
        "Golden": {"status": "✅", "note": "baseline ok"},
    }
    metrics = {"data_quality": {"issue_total": 3}, "drift": {"note": "anchor:WARN"}}
    context = {"settings_snapshot": {"REPORTS_DIR": "/tmp/reports"}}
    start = datetime.now(UTC)
    finish = datetime.now(UTC)

    index_path = reports_html.build_dashboard(
        diag_dir=diag_dir,
        statuses=statuses,
        metrics=metrics,
        context=context,
        trigger="manual",
        started_at=start,
        finished_at=finish,
        report_path=md_path,
    )

    contents = index_path.read_text(encoding="utf-8")
    assert "Diagnostics Dashboard" in contents
    assert "anchor:WARN" in contents
    assert (diag_dir / "site" / "status.svg").exists()

    entry = reports_html.append_history(
        diag_dir=diag_dir,
        statuses=statuses,
        trigger="manual",
        keep=5,
        started_at=start,
        finished_at=finish,
        html_path=index_path,
    )
    assert entry.status == "WARN"
    assert (diag_dir / "history" / "history.jsonl").exists()

    loaded = reports_html.load_history(diag_dir, limit=1)
    assert loaded and loaded[0].status == "WARN"
