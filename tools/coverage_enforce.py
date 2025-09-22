"""
@file: coverage_enforce.py
@description: Enforce Cobertura XML coverage thresholds for critical packages.
@created: 2025-09-23
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from xml.etree import ElementTree as ET

DEFAULT_TOTAL_MIN = 80.0
DEFAULT_PACKAGE_MIN: dict[str, float] = {
    "workers": 90.0,
    "database": 90.0,
    "services": 90.0,
    "core/services": 90.0,
}
PACKAGE_PREFIXES: dict[str, tuple[str, ...]] = {
    "workers": ("workers/",),
    "database": ("database/",),
    "services": ("services/",),
    "core/services": ("core/services/",),
}


@dataclass(frozen=True)
class FileCoverage:
    covered: int
    statements: int

    @property
    def percent(self) -> float:
        if self.statements == 0:
            return 100.0
        return round((self.covered / self.statements) * 100.0, 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate coverage.xml against project thresholds")
    parser.add_argument("--coverage-xml", default="coverage.xml", help="Path to Cobertura XML produced by pytest-cov")
    parser.add_argument("--total-min", type=float, default=None, help="Minimum total coverage percent required to pass")
    parser.add_argument("--pkg-min", action="append", default=[], metavar="name=value", help="Per-package minimum coverage (repeatable)")
    parser.add_argument("--print-top", type=int, default=0, help="Print top N files with the most missed statements")
    parser.add_argument("--summary-json", default=None, help="Optional path to write computed coverage summary")
    return parser.parse_args()
def _collect_file_coverages(root: ET.Element) -> dict[str, FileCoverage]:
    totals: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for class_node in root.findall(".//class"):
        filename = class_node.get("filename")
        if not filename:
            continue
        filename = filename.replace("\\", "/")
        for line in class_node.findall(".//line"):
            hits = line.get("hits")
            if hits is None:
                continue
            try:
                hit_count = int(float(hits))
            except ValueError:
                hit_count = 0
            totals[filename][1] += 1
            if hit_count > 0:
                totals[filename][0] += 1
    return {
        name: FileCoverage(covered, statements)
        for name, (covered, statements) in totals.items()
    }


def _aggregate_for_prefixes(files: dict[str, FileCoverage], prefixes: Iterable[str]) -> FileCoverage:
    covered = 0
    statements = 0
    normalized_prefixes = tuple(prefix.replace("\\", "/") for prefix in prefixes)
    for path, metrics in files.items():
        if any(path.startswith(prefix) for prefix in normalized_prefixes):
            covered += metrics.covered
            statements += metrics.statements
    return FileCoverage(covered, statements)


def _compute_total_from_root(root: ET.Element, files: dict[str, FileCoverage]) -> FileCoverage:
    covered_attr = root.get("lines-covered")
    valid_attr = root.get("lines-valid")
    try:
        covered = int(float(covered_attr)) if covered_attr is not None else None
    except ValueError:
        covered = None
    try:
        statements = int(float(valid_attr)) if valid_attr is not None else None
    except ValueError:
        statements = None
    if covered is not None and statements is not None:
        return FileCoverage(covered, statements)
    return FileCoverage(
        sum(item.covered for item in files.values()),
        sum(item.statements for item in files.values()),
    )


def _parse_package_thresholds(raw: Sequence[str]) -> dict[str, float]:
    thresholds = dict(DEFAULT_PACKAGE_MIN)
    for item in raw:
        if "=" not in item:
            raise ValueError(f"Invalid package threshold '{item}', expected name=value")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid package threshold '{item}', package name is empty")
        try:
            thresholds[name] = float(value)
        except ValueError as exc:
            raise ValueError(f"Invalid threshold for '{name}': {value}") from exc
    return thresholds


def _build_summary_payload(
    total: FileCoverage,
    packages: dict[str, FileCoverage],
    top: Sequence[tuple[str, FileCoverage]],
) -> dict[str, object]:
    def serialize(metrics: FileCoverage) -> dict[str, float]:
        missed = metrics.statements - metrics.covered
        return {
            "percent": metrics.percent,
            "covered": metrics.covered,
            "missed": missed,
        }

    return {
        "totals": serialize(total),
        "packages": {name: serialize(data) for name, data in packages.items()},
        "top_offenders": [
            {
                "path": path,
                "missed": metrics.statements - metrics.covered,
                "percent": metrics.percent,
            }
            for path, metrics in top
        ],
    }


def _compute_top_offenders(
    files: dict[str, FileCoverage],
    limit: int,
) -> list[tuple[str, FileCoverage]]:
    if limit <= 0:
        return []
    ranked = sorted(
        (
            (path, metrics)
            for path, metrics in files.items()
            if metrics.statements > 0
        ),
        key=lambda item: (
            -(item[1].statements - item[1].covered),
            item[1].percent,
            item[0],
        ),
    )
    return ranked[:limit]


def _print_top_offenders(entries: Sequence[tuple[str, FileCoverage]]) -> None:
    if not entries:
        return
    print("Top missed files:")
    for path, metrics in entries:
        missed = metrics.statements - metrics.covered
        print(f"  {path}: missed {missed} statements ({metrics.percent:.2f}% covered)")


def main() -> None:
    args = parse_args()
    xml_path = Path(args.coverage_xml)
    if not xml_path.is_file():
        print("coverage.xml not found", file=sys.stderr)
        sys.exit(1)
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        print(f"Failed to parse coverage XML: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        package_thresholds = _parse_package_thresholds(args.pkg_min)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    files = _collect_file_coverages(root)
    total_metrics = _compute_total_from_root(root, files)
    package_metrics: dict[str, FileCoverage] = {}
    package_names = sorted(set(PACKAGE_PREFIXES) | set(package_thresholds))
    for package in package_names:
        prefixes = PACKAGE_PREFIXES.get(package, (f"{package}/",))
        package_metrics[package] = _aggregate_for_prefixes(files, prefixes)

    total_threshold = args.total_min if args.total_min is not None else DEFAULT_TOTAL_MIN
    failures: list[str] = []
    if total_metrics.percent < total_threshold:
        failures.append(
            f"total {total_metrics.percent:.2f}% < {total_threshold:.2f}%"
        )
    for package, metrics in package_metrics.items():
        threshold = package_thresholds.get(package)
        if threshold is None:
            continue
        if metrics.percent < threshold:
            failures.append(
                f"{package} {metrics.percent:.2f}% < {threshold:.2f}%"
            )

    top_entries = _compute_top_offenders(files, args.print_top)

    print("Coverage summary (statements):")
    print(
        f"  total: {total_metrics.percent:.2f}% (required {total_threshold:.2f}%)"
    )
    for package, metrics in package_metrics.items():
        threshold = package_thresholds.get(package)
        suffix = f" (required {threshold:.2f}%)" if threshold is not None else ""
        print(f"  {package}: {metrics.percent:.2f}%{suffix}")

    _print_top_offenders(top_entries)

    if args.summary_json:
        payload = _build_summary_payload(total_metrics, package_metrics, top_entries)
        target = Path(args.summary_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if failures:
        print("coverage enforcement failed: " + "; ".join(failures), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
