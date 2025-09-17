"""
@file: enforce_coverage.py
@description: CLI utility enforcing coverage thresholds for CI and Makefile targets.
@dependencies: argparse, json, scripts.coverage_utils
@created: 2025-09-22
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.coverage_utils import (
    collect_critical_coverages,
    compute_total_coverage,
    load_coverage_data,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce coverage thresholds")
    parser.add_argument(
        "--coverage-json",
        default="coverage.json",
        help="Path to coverage JSON report (default: coverage.json)",
    )
    parser.add_argument(
        "--total-threshold",
        type=float,
        default=80.0,
        help="Minimum total coverage percent",
    )
    parser.add_argument(
        "--critical-threshold",
        type=float,
        default=90.0,
        help="Minimum coverage percent for critical packages",
    )
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Optional path to write computed coverage summary",
    )
    return parser.parse_args()


def write_summary(path: str | Path, summary: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    data = load_coverage_data(args.coverage_json)
    total = compute_total_coverage(data)
    critical = collect_critical_coverages(data)

    summary = {
        "coverage_total": total,
        "coverage_critical_packages": critical,
    }
    if args.summary_json:
        write_summary(args.summary_json, summary)

    failures: list[str] = []
    if total < args.total_threshold:
        failures.append(
            f"Total coverage {total:.2f}% is below threshold {args.total_threshold:.2f}%"
        )
    for name, value in critical.items():
        if value < args.critical_threshold:
            failures.append(
                f"Coverage for {name} {value:.2f}% is below threshold {args.critical_threshold:.2f}%"
            )

    for line in failures:
        print(f"::error::{line}")

    print("Coverage summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

