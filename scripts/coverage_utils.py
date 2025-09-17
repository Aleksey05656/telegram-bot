"""
@file: coverage_utils.py
@description: Helpers for reading coverage JSON reports and computing package metrics.
@dependencies: json, pathlib
@created: 2025-09-22
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

CRITICAL_PACKAGES: dict[str, tuple[str, ...]] = {
    "workers": ("workers/",),
    "database": ("database/",),
    "services": ("services/",),
    "core/services": ("core/services/",),
}


def load_coverage_data(path: str | Path) -> dict[str, Any]:
    """Read coverage JSON data from path."""

    json_path = Path(path)
    if not json_path.is_file():
        raise FileNotFoundError(f"Coverage report not found: {json_path}")
    return json.loads(json_path.read_text(encoding="utf-8"))


def _iter_matching_files(data: dict[str, Any], prefixes: Iterable[str]):
    files = data.get("files", {})
    normalized_prefixes = tuple(prefix.replace("\\", "/") for prefix in prefixes)
    for filename, payload in files.items():
        normalized_name = str(filename).replace("\\", "/")
        if any(normalized_name.startswith(prefix) for prefix in normalized_prefixes):
            yield payload


def compute_package_coverage(data: dict[str, Any], prefixes: Iterable[str]) -> float:
    """Compute coverage percent for files with matching prefixes."""

    covered = 0
    statements = 0
    for payload in _iter_matching_files(data, prefixes):
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        covered += int(summary.get("covered_lines", 0))
        statements += int(summary.get("num_statements", 0))

    if statements == 0:
        return 100.0
    percent = (covered / statements) * 100.0
    return round(percent, 2)


def compute_total_coverage(data: dict[str, Any]) -> float:
    """Return total coverage percent from coverage JSON."""

    totals = data.get("totals", {})
    if isinstance(totals, dict) and "percent_covered" in totals:
        return round(float(totals["percent_covered"]), 2)
    covered = 0
    statements = 0
    for payload in data.get("files", {}).values():
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        covered += int(summary.get("covered_lines", 0))
        statements += int(summary.get("num_statements", 0))
    if statements == 0:
        return 100.0
    percent = (covered / statements) * 100.0
    return round(percent, 2)


def collect_critical_coverages(data: dict[str, Any]) -> dict[str, float]:
    """Return coverage percentage for predefined critical packages."""

    return {
        name: compute_package_coverage(data, prefixes)
        for name, prefixes in CRITICAL_PACKAGES.items()
    }

