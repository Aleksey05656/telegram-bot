"""
@file: publish_rc_summary.py
@description: Build release candidate summary from changelog and run summary.
@dependencies: docs/changelog.md, reports/RUN_SUMMARY.md
@created: 2025-09-15
"""

import os
from pathlib import Path


def main() -> None:
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    reports_root = Path(os.getenv("REPORTS_DIR", str(data_root / "reports")))
    registry_root = Path(os.getenv("MODEL_REGISTRY_PATH", str(data_root / "artifacts")))
    changelog = Path("docs/changelog.md").read_text(encoding="utf-8")
    run_summary = (reports_root / "RUN_SUMMARY.md").read_text(encoding="utf-8")
    artifacts = (
        f"{reports_root}/metrics/**/*.md\n"
        f"{reports_root}/metrics/**/*.png\n"
        f"{registry_root}/**/*\n"
        f"{os.getenv('DB_PATH', str(data_root / 'bot.sqlite3'))}\n"
    )
    content = (
        "# Release Notes RC\n\n"
        "## Changelog\n" + changelog + "\n"
        "## Run Summary\n" + run_summary + "\n"
        "## Artifacts\n" + artifacts + "\n"
    )
    reports_root.mkdir(parents=True, exist_ok=True)
    (reports_root / "RELEASE_NOTES_RC.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
