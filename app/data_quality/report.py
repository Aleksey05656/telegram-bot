"""
/**
 * @file: app/data_quality/report.py
 * @description: Persistence helpers for data quality summaries and artifacts.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .runner import DataQualityIssue


@dataclass
class DataQualityReport:
    summary_path: Path
    summary_rows: list[dict[str, str]]
    csv_artifacts: dict[str, Path]
    overall_status: str
    issue_counts: dict[str, int]


def _status_order(status: str) -> int:
    if status == "❌":
        return 2
    if status == "⚠️":
        return 1
    return 0


def persist_report(issues: Iterable[DataQualityIssue], output_dir: Path) -> DataQualityReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_lines = ["# Data Quality Summary", "", "| Check | Status | Summary |", "| --- | --- | --- |"]
    summary_rows: list[dict[str, str]] = []
    csv_artifacts: dict[str, Path] = {}
    issue_counts: dict[str, int] = {}
    worst_status = "✅"

    for issue in issues:
        worst_status = max(worst_status, issue.status, key=_status_order)
        summary_rows.append({"check": issue.name, "status": issue.status, "summary": issue.summary})
        summary_lines.append(f"| {issue.name} | {issue.status} | {issue.summary} |")
        if issue.has_violations():
            csv_path = output_dir / f"{issue.name}.csv"
            assert issue.violations is not None
            issue.violations.to_csv(csv_path, index=False)
            csv_artifacts[issue.name] = csv_path
            issue_counts[issue.name] = len(issue.violations)
        else:
            issue_counts[issue.name] = 0
    summary_text = "\n".join(summary_lines) + "\n"
    summary_path = output_dir / "summary.md"
    summary_path.write_text(summary_text, encoding="utf-8")

    return DataQualityReport(
        summary_path=summary_path,
        summary_rows=summary_rows,
        csv_artifacts=csv_artifacts,
        overall_status=worst_status,
        issue_counts=issue_counts,
    )
