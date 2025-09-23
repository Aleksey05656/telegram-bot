"""
/**
 * @file: diagtools/drift_ref_update.py
 * @description: CLI utility to snapshot drift references and prepare changelog snippet.
 * @dependencies: argparse, json, shutil, pathlib, datetime
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from config import settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare drift reference snapshot")
    parser.add_argument(
        "--reports-dir",
        default=settings.REPORTS_DIR,
        help="Base reports directory containing diagnostics artefacts",
    )
    parser.add_argument(
        "--tag",
        default=datetime.now(UTC).strftime("%Y%m%d"),
        help="Tag or date to use for snapshot directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass AUTO_REF_UPDATE guard",
    )
    return parser.parse_args()


def _copy_reference(reference_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in reference_dir.iterdir():
        if item.is_dir():
            continue
        if item.name.startswith("changelog_"):
            continue
        shutil.copy2(item, target_dir / item.name)


def _build_changelog(meta_path: Path, tag: str) -> str:
    lines = [f"## Drift reference refresh ({tag})", ""]
    if not meta_path.exists():
        lines.append("- meta.json missing, manual verification required")
        return "\n".join(lines) + "\n"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        lines.append("- meta.json unreadable")
        return "\n".join(lines) + "\n"
    for name, payload in sorted(meta.items()):
        start = payload.get("start") or "n/a"
        end = payload.get("end") or "n/a"
        rows = payload.get("rows") or "?"
        source = payload.get("source") or "unknown"
        lines.append(f"- **{name}** ({source}): {start} → {end}, rows={rows}")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = _parse_args()
    mode = getattr(settings, "AUTO_REF_UPDATE", "off")
    if mode != "approved" and not args.force:
        print("AUTO_REF_UPDATE=off; use --force to override")
        return
    base_reports = Path(args.reports_dir)
    reference_dir = base_reports / "diagnostics" / "drift" / "reference"
    if not reference_dir.exists():
        raise SystemExit(f"Reference directory not found: {reference_dir}")
    tag = args.tag
    target_dir = reference_dir / tag
    _copy_reference(reference_dir, target_dir)
    changelog = _build_changelog(target_dir / "meta.json", tag)
    changelog_path = reference_dir / f"changelog_{tag}.md"
    changelog_path.write_text(changelog, encoding="utf-8")
    print(json.dumps({"target": str(target_dir), "changelog": str(changelog_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
