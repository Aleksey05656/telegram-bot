"""
/**
 * @file: coverage_gaps.py
 * @description: Generate Markdown report with top coverage gaps from coverage.xml.
 * @dependencies: coverage.xml report, reports directory
 * @created: 2025-09-25
 */
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
import xml.etree.ElementTree as ET

TARGET_PREFIXES: Sequence[str] = (
    "core/services/",
    "workers/",
    "database/",
    "services/",
)
DEFAULT_LIMIT = 20

@dataclass(slots=True)
class CoverageEntry:
    path: str
    percent: float
    missed: int
    ranges: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Markdown report with top coverage gaps.",
    )
    parser.add_argument(
        "--coverage-xml",
        dest="coverage_xml",
        default="coverage.xml",
        help="Path to Cobertura coverage.xml file.",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default="reports/coverage_gaps.md",
        help="Destination Markdown report path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of files in the report.",
    )
    return parser.parse_args()


def read_coverage(path: Path) -> list[CoverageEntry]:
    tree = ET.parse(path)
    entries: list[CoverageEntry] = []

    for class_el in tree.findall(".//class"):
        filename = class_el.get("filename")
        if not filename:
            continue

        normalized = normalize_path(filename)
        if not any(normalized.startswith(prefix) for prefix in TARGET_PREFIXES):
            continue

        lines_el = class_el.find("lines")
        if lines_el is None:
            continue

        covered = 0
        missed_numbers: list[int] = []
        for line_el in lines_el.findall("line"):
            number_attr = line_el.get("number")
            hits_attr = line_el.get("hits")
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

        if not missed_numbers:
            continue

        total = covered + len(missed_numbers)
        if total == 0:
            continue

        percent = (covered / total) * 100.0
        entries.append(
            CoverageEntry(
                path=normalized,
                percent=percent,
                missed=len(missed_numbers),
                ranges=format_ranges(missed_numbers),
            )
        )
    return entries


def normalize_path(filename: str) -> str:
    normalized = Path(filename).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


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


def select_top(entries: Iterable[CoverageEntry], limit: int) -> list[CoverageEntry]:
    sorted_entries = sorted(
        entries,
        key=lambda entry: (-entry.missed, entry.percent, entry.path),
    )
    return sorted_entries[:max(limit, 0)]


def build_markdown(entries: Sequence[CoverageEntry], limit: int) -> str:
    lines: list[str] = ["# Coverage gaps report", ""]
    if not entries:
        lines.append("Нет данных о пропущенных строках в выбранных пакетах.")
    else:
        lines.append(f"ТОП-{min(limit, len(entries))} файлов с пропущенными строками:")
        lines.append("")
        for entry in entries:
            line = (
                f"- {entry.path} — {entry.percent:.2f}% покрытия, пропущено {entry.missed} строк"
            )
            if entry.ranges:
                line += f" (строки {entry.ranges})"
            lines.append(line)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(content: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


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

    limited_entries = select_top(entries, args.limit)
    report = build_markdown(limited_entries, args.limit)
    write_report(report, Path(args.output))
    return 0

if __name__ == "__main__":
    sys.exit(main())
