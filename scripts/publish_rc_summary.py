"""
@file: publish_rc_summary.py
@description: Build release candidate summary from changelog and run summary.
@dependencies: docs/changelog.md, reports/RUN_SUMMARY.md
@created: 2025-09-15
"""

from pathlib import Path


def main() -> None:
    changelog = Path("docs/changelog.md").read_text(encoding="utf-8")
    run_summary = Path("reports/RUN_SUMMARY.md").read_text(encoding="utf-8")
    artifacts = (
        "reports/metrics/**/*.md\n"
        "reports/metrics/**/*.png\n"
        "artifacts/**/*\n"
        "var/predictions.sqlite\n"
    )
    content = (
        "# Release Notes RC\n\n"
        "## Changelog\n" + changelog + "\n"
        "## Run Summary\n" + run_summary + "\n"
        "## Artifacts\n" + artifacts + "\n"
    )
    Path("reports").mkdir(exist_ok=True)
    Path("reports/RELEASE_NOTES_RC.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
