# /**
#  * @file: coverage_gaps.py
#  * @description: Generate Markdown report with top coverage gaps per package from coverage.xml.
#  * @dependencies: coverage.xml report, reports directory
#  * @created: 2025-09-19
#  */
"""Coverage gaps report builder.

This script parses a Cobertura-style ``coverage.xml`` file, identifies files with
missed lines inside specific project packages, and exports a Markdown report
highlighting the worst offenders.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
import xml.etree.ElementTree as ET

PACKAGE_PREFIXES: dict[str, tuple[str, ...]] = {
    "workers": ("workers/",),
    "database": ("database/",),
    "services": ("services/",),
    "core/services": ("core/services/",),
}
PACKAGE_ORDER: Sequence[str] = ("workers", "database", "services", "core/services")
DETECTION_ORDER: Sequence[str] = ("core/services", "workers", "database", "services")


@dataclass(slots=True)
class CoverageEntry:
    package: str
    path: str
    percent: float
    missed: int
    ranges: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build coverage gaps Markdown report.")
    parser.add_argument(
        "--coverage-xml",
        dest="coverage_xml",
        default="coverage.xml",
        help="Path to coverage.xml (Cobertura format).",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default="reports/coverage_gaps.md",
        help="Destination Markdown file for gaps report.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of entries per package.",
    )
    return parser.parse_args()


def read_coverage(path: Path) -> list[CoverageEntry]:
    tree = ET.parse(path)
    entries: list[CoverageEntry] = []

    for cls in tree.findall(".//class"):
        filename = cls.get("filename")
        if not filename:
            continue

        normalized = normalize_path(filename)
        package = detect_package(normalized)
        if package is None:
            continue

        lines_element = cls.find("lines")
        if lines_element is None:
            continue

        covered = 0
        missed_numbers: list[int] = []

        for line in lines_element.findall("line"):
            number_attr = line.get("number")
            hits_attr = line.get("hits")
            if number_attr is None or hits_attr is None:
                continue

            try:
                number = int(number_attr)
            except ValueError:
                continue

            try:
                hits = int(float(hits_attr))
            except ValueError:
                continue

            if hits > 0:
                covered += 1
            else:
                missed_numbers.append(number)

        total_tracked = covered + len(missed_numbers)
        if total_tracked == 0 or not missed_numbers:
            continue

        percent = (covered / total_tracked) * 100.0
        ranges = format_ranges(missed_numbers)
        entries.append(
            CoverageEntry(
                package=package,
                path=normalized,
                percent=percent,
                missed=len(missed_numbers),
                ranges=ranges,
            )
        )

    return entries


def normalize_path(filename: str) -> str:
    normalized = Path(filename).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def detect_package(path: str) -> str | None:
    for package in DETECTION_ORDER:
        prefixes = PACKAGE_PREFIXES[package]
        for prefix in prefixes:
            if path.startswith(prefix):
                return package
    return None


def format_ranges(numbers: Sequence[int]) -> str:
    if not numbers:
        return ""

    sorted_numbers = sorted(numbers)
    segments: list[str] = []
    start = prev = sorted_numbers[0]

    for number in sorted_numbers[1:]:
        if number == prev + 1:
            prev = number
            continue

        segments.append(_range_repr(start, prev))
        start = prev = number

    segments.append(_range_repr(start, prev))
    return ", ".join(segments)


def _range_repr(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def group_top_entries(entries: Iterable[CoverageEntry], limit: int) -> dict[str, list[CoverageEntry]]:
    grouped: dict[str, list[CoverageEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.package].append(entry)

    for package, items in grouped.items():
        items.sort(key=lambda e: (-e.missed, e.percent, e.path))
        grouped[package] = items[:limit]

    for package in PACKAGE_ORDER:
        grouped.setdefault(package, [])

    return grouped


def write_markdown(entries_by_package: dict[str, list[CoverageEntry]], output: Path) -> None:
    lines: list[str] = ["# Coverage gaps report", ""]

    for package in PACKAGE_ORDER:
        lines.append(f"## {package}")
        package_entries = entries_by_package.get(package, [])
        if not package_entries:
            lines.append("- Нет данных о пропущенных строках.")
        else:
            for entry in package_entries:
                line = (
                    f"- {entry.path} — {entry.percent:.2f}% покрытия, пропущено {entry.missed} строк"
                )
                if entry.ranges:
                    line += f" (строки {entry.ranges})"
                lines.append(line)
        lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    coverage_path = Path(args.coverage_xml)
    if not coverage_path.exists():
        print(f"Не найден файл покрытия: {coverage_path}", file=sys.stderr)
        return 1

    try:
        entries = read_coverage(coverage_path)
    except ET.ParseError as exc:
        print(f"Ошибка разбора XML {coverage_path}: {exc}", file=sys.stderr)
        return 1

    grouped = group_top_entries(entries, args.limit)
    write_markdown(grouped, Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
