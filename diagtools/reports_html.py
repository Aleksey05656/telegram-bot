"""
/**
 * @file: diagtools/reports_html.py
 * @description: HTML dashboard generator and history keeper for diagnostics suite.
 * @dependencies: csv, json, math, os, pathlib, datetime
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings

try:
    from matplotlib import pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - matplotlib optional
    plt = None  # type: ignore


@dataclass
class HistoryEntry:
    """Structured representation of diagnostics run history."""

    timestamp: str
    trigger: str
    status: str
    duration_sec: float
    warn_sections: list[str]
    fail_sections: list[str]
    html_path: str
    report_path: str


_STATUS_SCORE = {"✅": 1.0, "⚠️": 0.0, "❌": -1.0}


def _status_counts(statuses: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"✅": 0, "⚠️": 0, "❌": 0}
    for payload in statuses.values():
        counts[payload.get("status", "⚠️")] += 1
    return counts


def _status_summary(statuses: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    warn_sections: list[str] = []
    fail_sections: list[str] = []
    for section, payload in statuses.items():
        status = payload.get("status", "⚠️")
        if status == "⚠️":
            warn_sections.append(section)
        elif status == "❌":
            fail_sections.append(section)
    if fail_sections:
        overall = "FAIL"
    elif warn_sections:
        overall = "WARN"
    else:
        overall = "OK"
    return overall, warn_sections, fail_sections


def _render_svg_chart(counts: dict[str, int], path: Path) -> None:
    total = sum(counts.values()) or 1
    width = 360
    height = 200
    bar_width = 80
    spacing = 40
    origin_x = 40
    origin_y = height - 40
    max_height = height - 80
    palette = {"✅": "#16a34a", "⚠️": "#f59e0b", "❌": "#dc2626"}
    svg_lines = [
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{0}\" height=\"{1}\" viewBox=\"0 0 {0} {1}\">".format(
            width, height
        ),
        "  <style>text{font-family:Inter,Arial,sans-serif;font-size:14px;}</style>",
        f"  <rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" fill=\"#0f172a\" rx=\"12\" />",
        "  <g transform=\"translate(0,0)\">",
    ]
    for idx, status in enumerate(["✅", "⚠️", "❌"]):
        value = counts.get(status, 0)
        ratio = value / total
        bar_height = max_height * ratio
        x = origin_x + idx * (bar_width + spacing)
        y = origin_y - bar_height
        svg_lines.append(
            f"    <rect x=\"{x}\" y=\"{y}\" width=\"{bar_width}\" height=\"{bar_height}\" fill=\"{palette[status]}\" rx=\"12\" />"
        )
        svg_lines.append(
            f"    <text x=\"{x + bar_width / 2}\" y=\"{origin_y + 24}\" fill=\"#e2e8f0\" text-anchor=\"middle\">{status}</text>"
        )
        svg_lines.append(
            f"    <text x=\"{x + bar_width / 2}\" y=\"{y - 8}\" fill=\"#e2e8f0\" text-anchor=\"middle\">{value} ({ratio * 100:.0f}%)</text>"
        )
    svg_lines.append("  </g>")
    svg_lines.append("</svg>")
    path.write_text("\n".join(svg_lines), encoding="utf-8")


def _render_png_chart(counts: dict[str, int], path: Path) -> None:
    if plt is None:  # pragma: no cover - fallback when matplotlib unavailable
        path.write_text("PNG rendering unavailable", encoding="utf-8")
        return
    statuses = ["✅", "⚠️", "❌"]
    values = [counts.get(label, 0) for label in statuses]
    colors = ["#16a34a", "#f59e0b", "#dc2626"]
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.bar(statuses, values, color=colors)
    ax.set_facecolor("#0f172a")
    fig.patch.set_facecolor("#0f172a")
    ax.tick_params(colors="#e2e8f0")
    ax.spines["bottom"].set_color("#334155")
    ax.spines["left"].set_color("#334155")
    ax.yaxis.label.set_color("#e2e8f0")
    ax.xaxis.label.set_color("#e2e8f0")
    ax.set_ylabel("Количество", color="#e2e8f0")
    ax.set_title("Диагностика по статусам", color="#e2e8f0")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.1, str(value), ha="center", color="#e2e8f0")
    fig.tight_layout()
    fig.savefig(path, format="png", dpi=160)
    plt.close(fig)


def build_dashboard(
    *,
    diag_dir: Path,
    statuses: dict[str, dict[str, Any]],
    metrics: dict[str, Any],
    context: dict[str, Any],
    trigger: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    report_path: Path | None = None,
) -> Path:
    """Render diagnostics dashboard and return path to index.html."""

    site_dir = diag_dir / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    img_format = os.getenv("REPORTS_IMG_FORMAT", settings.REPORTS_IMG_FORMAT).lower()
    if img_format not in {"svg", "png"}:
        img_format = "svg"
    chart_path = site_dir / f"status.{img_format}"
    counts = _status_counts(statuses)
    if img_format == "svg":
        _render_svg_chart(counts, chart_path)
    else:
        _render_png_chart(counts, chart_path)
    generated_at = (finished_at or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    started_iso = (started_at or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall, warn_sections, fail_sections = _status_summary(statuses)
    rows = []
    for section, payload in statuses.items():
        status_icon = payload.get("status", "⚠️")
        note = payload.get("note", "")
        rows.append(f"<tr><td>{section}</td><td>{status_icon}</td><td>{note}</td></tr>")
    dq_total = metrics.get("data_quality", {}).get("issue_total") if isinstance(metrics, dict) else None
    drift_note = metrics.get("drift", {}).get("note") if isinstance(metrics, dict) else None
    history_links = ""
    history_dir = diag_dir / "history"
    if history_dir.exists():
        jsonl = history_dir / "history.jsonl"
        csv_path = history_dir / "history.csv"
        links: list[str] = []
        if jsonl.exists():
            links.append(f"<a href='../history/{jsonl.name}'>history.jsonl</a>")
        if csv_path.exists():
            links.append(f"<a href='../history/{csv_path.name}'>history.csv</a>")
        history_links = " | ".join(links)
    styles = (
        "body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', Arial, sans-serif; margin: 0; }\n"
        "header { padding: 24px 32px; border-bottom: 1px solid #1e293b; }\n"
        "main { padding: 24px 32px; }\n"
        "table { width: 100%; border-collapse: collapse; margin-top: 16px; }\n"
        "th, td { border-bottom: 1px solid #1e293b; padding: 8px 12px; text-align: left; }\n"
        "th { color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; font-size: 12px; }\n"
        "tr:hover { background: rgba(148, 163, 184, 0.08); }\n"
        ".chip { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 13px; margin-right: 8px; }\n"
        ".ok { background: rgba(22, 163, 74, 0.16); color: #4ade80; }\n"
        ".warn { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }\n"
        ".fail { background: rgba(220, 38, 38, 0.16); color: #f87171; }\n"
        "footer { padding: 24px 32px; border-top: 1px solid #1e293b; font-size: 14px; color: #94a3b8; }\n"
        "code { background: rgba(15, 23, 42, 0.6); padding: 2px 4px; border-radius: 4px; }"
    )
    chips = [f"<span class='chip ok'>OK</span>"]
    if warn_sections:
        chips.append(f"<span class='chip warn'>WARN: {len(warn_sections)}</span>")
    if fail_sections:
        chips.append(f"<span class='chip fail'>FAIL: {len(fail_sections)}</span>")
    history_block = (
        f"<p>History: {history_links}</p>" if history_links else "<p>История будет доступна после первого запуска.</p>"
    )
    meta_list = "".join(
        f"<li><code>{key}</code>: {value}</li>" for key, value in sorted(context.get("settings_snapshot", {}).items())
    )
    metrics_list = []
    if dq_total is not None:
        metrics_list.append(f"<li>Data quality issues: <strong>{dq_total}</strong></li>")
    if drift_note:
        metrics_list.append(f"<li>Drift status: {drift_note}</li>")
    html = f"""
<!DOCTYPE html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\" />
  <title>Diagnostics Dashboard</title>
  <style>{styles}</style>
</head>
<body>
  <header>
    <h1>Diagnostics Dashboard</h1>
    <p>Trigger: <strong>{trigger}</strong> · Started: <strong>{started_iso}</strong> · Finished: <strong>{generated_at}</strong></p>
    <div>{''.join(chips)}</div>
  </header>
  <main>
    <section>
      <h2>Sections</h2>
      <img src=\"{chart_path.name}\" alt=\"Diagnostics status chart\" style=\"margin-top:16px;max-width:420px;width:100%;border-radius:12px;box-shadow:0 10px 40px rgba(15,23,42,0.6);\" />
      <table>
        <thead><tr><th>Section</th><th>Status</th><th>Note</th></tr></thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
    <section>
      <h2>Context snapshot</h2>
      <ul>{meta_list}</ul>
      <ul>{''.join(metrics_list) if metrics_list else '<li>No metric deltas captured.</li>'}</ul>
    </section>
    <section>
      <h2>Artifacts</h2>
      <ul>
        <li><a href="../DIAGNOSTICS.md">Markdown summary</a></li>
        <li><a href="../diagnostics_report.json">JSON summary</a></li>
        {f'<li><a href="{report_path.name}">Rendered report</a></li>' if report_path else ''}
      </ul>
    </section>
    <section>
      <h2>History</h2>
      {history_block}
    </section>
  </main>
  <footer>
    Generated at {generated_at} · Overall status: {overall}
  </footer>
</body>
</html>
"""
    index_path = site_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def append_history(
    *,
    diag_dir: Path,
    statuses: dict[str, dict[str, Any]],
    trigger: str,
    keep: int,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    html_path: Path | None = None,
) -> HistoryEntry:
    """Append run metadata to history files and return structured entry."""

    history_dir = diag_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    started = started_at or datetime.now(UTC)
    finished = finished_at or datetime.now(UTC)
    duration = max(0.0, (finished - started).total_seconds())
    timestamp = finished.strftime("%Y-%m-%dT%H:%M:%SZ")
    overall, warn_sections, fail_sections = _status_summary(statuses)
    entry_dict = {
        "timestamp": timestamp,
        "trigger": trigger,
        "status": overall,
        "duration_sec": round(duration, 2),
        "warn_sections": warn_sections,
        "fail_sections": fail_sections,
        "html_path": str(html_path) if html_path else "",
    }
    jsonl_path = history_dir / "history.jsonl"
    items: list[dict[str, Any]] = []
    if jsonl_path.exists():
        for raw in jsonl_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                items.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    items.append(entry_dict)
    items = items[-keep:]
    json_payload = "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
    if json_payload:
        jsonl_path.write_text(json_payload + "\n", encoding="utf-8")
    else:
        jsonl_path.write_text("", encoding="utf-8")
    csv_path = history_dir / "history.csv"
    fieldnames = ["timestamp", "trigger", "status", "duration_sec", "warn_sections", "fail_sections", "html_path"]
    with csv_path.open("w", encoding="utf-8", newline="") as f_obj:
        writer = csv.DictWriter(f_obj, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = item.copy()
            row["warn_sections"] = ",".join(item.get("warn_sections", []))
            row["fail_sections"] = ",".join(item.get("fail_sections", []))
            writer.writerow(row)
    return HistoryEntry(
        timestamp=timestamp,
        trigger=trigger,
        status=overall,
        duration_sec=round(duration, 2),
        warn_sections=warn_sections,
        fail_sections=fail_sections,
        html_path=str(html_path) if html_path else "",
        report_path=str((diag_dir / "diagnostics_report.json")),
    )


def load_history(diag_dir: Path, limit: int = 1) -> list[HistoryEntry]:
    """Load history entries from disk (newest first)."""

    history_dir = diag_dir / "history"
    jsonl_path = history_dir / "history.jsonl"
    if not jsonl_path.exists():
        return []
    entries: list[HistoryEntry] = []
    for raw in reversed(jsonl_path.read_text(encoding="utf-8").splitlines()):
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        entries.append(
            HistoryEntry(
                timestamp=str(payload.get("timestamp", "")),
                trigger=str(payload.get("trigger", "")),
                status=str(payload.get("status", "")),
                duration_sec=float(payload.get("duration_sec", 0.0)),
                warn_sections=list(payload.get("warn_sections", [])),
                fail_sections=list(payload.get("fail_sections", [])),
                html_path=str(payload.get("html_path", "")),
                report_path=str((diag_dir / "diagnostics_report.json")),
            )
        )
        if len(entries) >= limit:
            break
    return entries


def status_score(status_icon: str) -> float:
    """Expose numeric score for status icons (for tests)."""

    return _STATUS_SCORE.get(status_icon, math.nan)
