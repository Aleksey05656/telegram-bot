"""
@file: rc_summary.py
@description: Release candidate summary generator combining coverage and test status data.
@dependencies: argparse, json, scripts.coverage_utils
@created: 2025-09-22
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

os.environ.setdefault("LOG_LEVEL", "WARNING")

from config import get_settings  # noqa: E402
from scripts.coverage_utils import (  # noqa: E402
    collect_critical_coverages,
    compute_total_coverage,
    load_coverage_data,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RC summary JSON")
    parser.add_argument(
        "--coverage-json",
        default="coverage.json",
        help="Path to coverage.json produced by pytest",
    )
    parser.add_argument(
        "--summary-json",
        default="reports/coverage_summary.json",
        help="Optional coverage summary produced by enforce_coverage",
    )
    parser.add_argument(
        "--tests-passed",
        action="store_true",
        help="Mark tests as passed in the summary",
    )
    parser.add_argument(
        "--docker-image",
        default=None,
        help="Docker image reference to inspect for size",
    )
    parser.add_argument(
        "--output",
        default="reports/rc_summary.json",
        help="Target path for generated JSON",
    )
    return parser.parse_args()


def _load_summary_file(path: str | Path) -> dict[str, Any] | None:
    summary_path = Path(path)
    if not summary_path.is_file():
        return None
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_coverage_metrics(coverage_path: str | Path, summary_path: str | Path) -> tuple[float | None, dict[str, float]]:
    summary = _load_summary_file(summary_path)
    if summary:
        total = summary.get("coverage_total")
        critical = summary.get("coverage_critical_packages", {})
        try:
            total_val = round(float(total), 2) if total is not None else None
        except (TypeError, ValueError):
            total_val = None
        critical_map: dict[str, float] = {}
        if isinstance(critical, dict):
            for key, value in critical.items():
                try:
                    critical_map[key] = round(float(value), 2)
                except (TypeError, ValueError):
                    critical_map[key] = 0.0
        return total_val, critical_map

    try:
        data = load_coverage_data(coverage_path)
    except FileNotFoundError:
        return None, {}

    total = compute_total_coverage(data)
    critical = collect_critical_coverages(data)
    return total, critical


def _get_version_info() -> tuple[str, str]:
    app_version = os.environ.get("APP_VERSION")
    git_sha = os.environ.get("GIT_SHA")
    if app_version and git_sha:
        return app_version, git_sha

    settings = get_settings()
    return app_version or settings.APP_VERSION, git_sha or settings.GIT_SHA


def _inspect_docker_image(image: str | None) -> float | None:
    if not image:
        return None
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{json .}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None

    if isinstance(payload, list):
        total_size = sum(int(item.get("Size", 0)) for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        total_size = int(payload.get("Size", 0))
    else:
        total_size = 0
    if total_size <= 0:
        return None
    return round(total_size / (1024 * 1024), 2)


def main() -> None:
    args = parse_args()
    app_version, git_sha = _get_version_info()
    coverage_total, coverage_critical = _load_coverage_metrics(args.coverage_json, args.summary_json)
    docker_size_mb = _inspect_docker_image(args.docker_image)

    report = {
        "app_version": app_version,
        "git_sha": git_sha,
        "tests_passed": bool(args.tests_passed),
        "coverage_total": coverage_total,
        "coverage_critical_packages": coverage_critical,
        "docker_image_size_mb": docker_size_mb,
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

