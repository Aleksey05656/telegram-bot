"""
/**
 * @file: diagtools/scheduler.py
 * @description: Diagnostics scheduler orchestrating CLI runs, history and Chat-Ops hooks.
 * @dependencies: subprocess, json, urllib, threading, metrics.metrics, diagtools.reports_html
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from config import settings
from logger import logger
from metrics.metrics import record_diag_run_event

from diagtools import reports_html

_SECRET_PATTERN = re.compile(r"(?:_TOKEN|_KEY|PASSWORD)$")


@dataclass
class CommandExecution:
    """Result of a single diagnostics sub-command."""

    name: str
    command: list[str]
    returncode: int
    duration_sec: float
    stdout: str
    stderr: str


@dataclass
class DiagnosticsRunResult:
    """Aggregated result for diagnostics suite execution."""

    trigger: str
    started_at: datetime
    finished_at: datetime
    statuses: dict[str, dict[str, Any]]
    commands: list[CommandExecution]
    log_path: Path
    html_path: Path | None
    alerts_sent: bool


def _log_line(log_path: Path, message: str) -> None:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _secret_values(env: dict[str, str]) -> list[str]:
    values: list[str] = []
    for key, value in env.items():
        if _SECRET_PATTERN.search(key) and value:
            values.append(value)
    return values


def _mask(text: str, secrets: Iterable[str]) -> str:
    masked = text
    for secret in secrets:
        if not secret or secret == "" or secret.isspace():
            continue
        masked = masked.replace(secret, "<redacted>")
    return masked


def _run_command(
    name: str,
    command: list[str],
    env: dict[str, str],
    log_path: Path,
    secrets: Iterable[str],
) -> CommandExecution:
    start = time.perf_counter()
    _log_line(log_path, f"$ {' '.join(command)}")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    duration = time.perf_counter() - start
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    masked_stdout = _mask(stdout, secrets)
    masked_stderr = _mask(stderr, secrets)
    if masked_stdout.strip():
        _log_line(log_path, masked_stdout.strip())
    if masked_stderr.strip():
        _log_line(log_path, masked_stderr.strip())
    _log_line(log_path, f"exit {completed.returncode} duration={duration:.2f}s")
    return CommandExecution(
        name=name,
        command=command,
        returncode=int(completed.returncode),
        duration_sec=round(duration, 2),
        stdout=masked_stdout,
        stderr=masked_stderr,
    )


def _load_statuses(diag_dir: Path) -> dict[str, dict[str, Any]]:
    report_path = diag_dir / "diagnostics_report.json"
    if not report_path.exists():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return dict(payload.get("statuses", {}))


def _send_alert(trigger: str, statuses: dict[str, dict[str, Any]], html_path: Path | None) -> bool:
    if not getattr(settings, "ALERTS_ENABLED", False):
        return False
    chat_id = getattr(settings, "ALERTS_CHAT_ID", None)
    if not chat_id:
        logger.warning("Alerts enabled but ALERTS_CHAT_ID not configured")
        return False
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("Alerts enabled but TELEGRAM_BOT_TOKEN missing")
        return False
    warn_sections = [s for s, payload in statuses.items() if payload.get("status") == "⚠️"]
    fail_sections = [s for s, payload in statuses.items() if payload.get("status") == "❌"]
    if fail_sections:
        severity = "FAIL"
    elif warn_sections:
        severity = "WARN"
    else:
        severity = "OK"
    min_level = getattr(settings, "ALERTS_MIN_LEVEL", "WARN")
    if severity == "OK":
        return False
    if min_level == "FAIL" and severity != "FAIL":
        return False
    parts = [f"Diagnostics {severity}", f"trigger={trigger}"]
    if warn_sections:
        parts.append("warn=" + ",".join(warn_sections))
    if fail_sections:
        parts.append("fail=" + ",".join(fail_sections))
    if html_path and html_path.exists():
        parts.append(f"html={html_path}")
    message = " | ".join(parts)
    payload = json.dumps({"chat_id": chat_id, "text": message})
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    request = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            logger.info("Diagnostics alert sent: severity=%s trigger=%s", severity, trigger)
            return True
    except urllib.error.URLError as exc:
        logger.warning("Failed to deliver diagnostics alert: %s", exc)
    return False


def run_suite(
    *,
    trigger: str = "manual",
    reports_dir: str | None = None,
    command_runner: Callable[[str, list[str], dict[str, str], Path, Iterable[str]], CommandExecution] | None = None,
    time_provider: Callable[[], float] | None = None,
) -> DiagnosticsRunResult:
    """Execute full diagnostics suite orchestrating all sub-commands."""

    reports_root = Path(reports_dir or settings.REPORTS_DIR)
    diag_dir = reports_root / "diagnostics"
    log_path = Path(settings.LOG_DIR) / "diag.log"
    command_runner = command_runner or _run_command
    time_provider = time_provider or time.perf_counter
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("SPORTMONKS_STUB", "1")
    env.setdefault("ODDS_API_KEY", env.get("ODDS_API_KEY", "stub-odds"))
    env.setdefault("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    env["DIAG_TRIGGER"] = trigger
    reports_root.mkdir(parents=True, exist_ok=True)
    diag_dir.mkdir(parents=True, exist_ok=True)
    (diag_dir / "drift").mkdir(parents=True, exist_ok=True)
    (diag_dir / "bench").mkdir(parents=True, exist_ok=True)
    secrets = _secret_values(env)
    iterations = os.getenv("BENCH_ITER", "30")
    commands: list[CommandExecution] = []
    commands_plan = [
        ("diag-run", ["diag-run", "--all", "--reports-dir", str(reports_root)]),
        (
            "diag-drift",
            [
                "diag-drift",
                "--reports-dir",
                str(diag_dir / "drift"),
                "--ref-days",
                os.getenv("DRIFT_REF_DAYS", "90"),
                "--ref-rolling-days",
                os.getenv("DRIFT_ROLLING_DAYS", "30"),
            ],
        ),
        (
            "golden-regression",
            [
                "python",
                "-m",
                "diagtools.golden_regression",
                "--check",
                "--reports-dir",
                str(reports_root),
            ],
        ),
        (
            "bench",
            [
                "python",
                "-m",
                "diagtools.bench",
                "--iterations",
                iterations,
                "--reports-dir",
                str(diag_dir / "bench"),
            ],
        ),
    ]
    start_ts = datetime.now(UTC)
    start = time_provider()
    _log_line(log_path, f"Diagnostics trigger={trigger} started")
    max_runtime = getattr(settings, "DIAG_MAX_RUNTIME_MIN", 25) * 60
    for name, command in commands_plan:
        execution = command_runner(name, command, env, log_path, secrets)
        commands.append(execution)
        if time_provider() - start > max_runtime:
            _log_line(log_path, "Diagnostics runtime budget exceeded, aborting queue")
            break
    statuses = _load_statuses(diag_dir)
    html_path = diag_dir / "site" / "index.html"
    alerts_sent = _send_alert(trigger, statuses, html_path if html_path.exists() else None)
    record_diag_run_event(trigger, statuses)
    finished_ts = datetime.now(UTC)
    return DiagnosticsRunResult(
        trigger=trigger,
        started_at=start_ts,
        finished_at=finished_ts,
        statuses=statuses,
        commands=commands,
        log_path=log_path,
        html_path=html_path if html_path.exists() else None,
        alerts_sent=alerts_sent,
    )


def run_drift(
    *,
    trigger: str = "manual",
    reports_dir: str | None = None,
    command_runner: Callable[[str, list[str], dict[str, str], Path, Iterable[str]], CommandExecution] | None = None,
) -> CommandExecution:
    """Execute only drift diagnostics and return execution details."""

    reports_root = Path(reports_dir or settings.REPORTS_DIR)
    diag_dir = reports_root / "diagnostics"
    log_path = Path(settings.LOG_DIR) / "diag.log"
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("SPORTMONKS_STUB", "1")
    env["DIAG_TRIGGER"] = trigger
    diag_dir.mkdir(parents=True, exist_ok=True)
    (diag_dir / "drift").mkdir(parents=True, exist_ok=True)
    secrets = _secret_values(env)
    runner = command_runner or _run_command
    command = [
        "diag-drift",
        "--reports-dir",
        str(diag_dir / "drift"),
        "--ref-days",
        os.getenv("DRIFT_REF_DAYS", "90"),
        "--ref-rolling-days",
        os.getenv("DRIFT_ROLLING_DAYS", "30"),
    ]
    _log_line(log_path, f"Drift run trigger={trigger}")
    return runner("diag-drift", command, env, log_path, secrets)


def register_jobs(register: Callable[[str, Callable[[], None]], None]) -> None:
    """Register diagnostics job in runtime scheduler."""

    cron_expr = getattr(settings, "DIAG_SCHEDULE_CRON", "0 6 * * *")
    logger.info("Registering diagnostics job cron=%s", cron_expr)

    def _job() -> None:
        try:
            run_suite(trigger="cron")
        except Exception as exc:  # pragma: no cover - background job safety
            logger.exception("Diagnostics scheduled run failed: %s", exc)

    register(cron_expr, _job)
    if getattr(settings, "DIAG_ON_START", False):
        thread = threading.Thread(target=lambda: run_suite(trigger="startup"), daemon=True)
        thread.start()
        logger.info("Diagnostics on-start trigger scheduled")


def load_history(limit: int = 1, reports_dir: str | None = None) -> list[reports_html.HistoryEntry]:
    """Expose diagnostics history entries from storage."""

    reports_root = Path(reports_dir or settings.REPORTS_DIR)
    diag_dir = reports_root / "diagnostics"
    return reports_html.load_history(diag_dir, limit)
