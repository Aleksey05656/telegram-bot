"""
/**
 * @file: tests/diagtools/test_auto_ref_update.py
 * @description: Tests for drift reference auto-update helper CLI.
 * @dependencies: diagtools.drift_ref_update
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
import sys

from config import settings
from diagtools import drift_ref_update


def _build_reference_dir(tmp_path):
    reference_dir = tmp_path / "diagnostics" / "drift" / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "anchor": {"start": "2024-01-01", "end": "2024-03-01", "rows": 100, "source": "file"},
        "rolling": {"start": "2024-02-01", "end": "2024-03-01", "rows": 90, "source": "rolling"},
    }
    (reference_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (reference_dir / "anchor.parquet").write_text("data", encoding="utf-8")
    (reference_dir / "anchor.sha256").write_text("deadbeef\n", encoding="utf-8")
    return reference_dir


def test_auto_ref_update_guard(monkeypatch, tmp_path, capsys) -> None:
    reference_dir = _build_reference_dir(tmp_path)
    monkeypatch.setattr(settings, "AUTO_REF_UPDATE", "off")
    monkeypatch.setattr(sys, "argv", ["drift_ref_update", "--reports-dir", str(tmp_path)])
    drift_ref_update.main()
    captured = capsys.readouterr()
    assert "AUTO_REF_UPDATE=off" in captured.out
    # ensure no snapshot created
    assert len(list(reference_dir.iterdir())) == 3


def test_auto_ref_update_creates_snapshot(monkeypatch, tmp_path, capsys) -> None:
    reference_dir = _build_reference_dir(tmp_path)
    monkeypatch.setattr(settings, "AUTO_REF_UPDATE", "approved")
    tag = "20240101"
    monkeypatch.setattr(
        sys,
        "argv",
        ["drift_ref_update", "--reports-dir", str(tmp_path), "--tag", tag],
    )
    drift_ref_update.main()
    payload = json.loads(capsys.readouterr().out)
    target = tmp_path / "diagnostics" / "drift" / "reference" / tag
    assert target.exists()
    assert (target / "meta.json").exists()
    assert (reference_dir / f"changelog_{tag}.md").exists()
    assert payload["target"] == str(target)
