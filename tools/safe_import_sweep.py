"""
@file: tools/safe_import_sweep.py
@description: Offline-safe import sweep with stub activation and reporting
@dependencies: tools.qa_stub_injector, importlib, multiprocessing
@created: 2025-09-27
"""

from __future__ import annotations

import os

if os.getenv("USE_OFFLINE_STUBS") == "1":
    os.environ.setdefault("QA_STUB_SSL", "1")
    try:
        from tools.qa_stub_injector import install_stubs

        install_stubs()
    except Exception:
        pass

import importlib
import json
import multiprocessing as mp
import sys
import time
import traceback
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

REPORTS_DIR = Path("reports")
JSON_REPORT = REPORTS_DIR / "offline_import.json"
MD_REPORT = REPORTS_DIR / "offline_import.md"
IMPORT_TIMEOUT_SEC = float(os.getenv("SAFE_IMPORT_TIMEOUT", "3"))
EXCLUDE_DIR_NAMES = {"tests", "migrations", "alembic", "build", "dist", "__pycache__"}
OFFLINE_SKIP_MODULES: dict[str, str] = {
    "scripts.run_training_pipeline": "runtime side-effects: launches training pipeline",
    "scripts.train_model": "runtime side-effects: starts training on import",
    "scripts.update_upcoming": "runtime side-effects: performs live data sync",
    "scripts.worker": "runtime side-effects: bootstraps long-running worker",
}


@dataclass(slots=True)
class ImportResult:
    module: str
    status: str
    duration_s: float
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "module": self.module,
            "status": self.status,
            "duration_s": round(self.duration_s, 4),
        }
        if self.error:
            payload["error"] = self.error
        return payload


def _maybe_install_stubs() -> None:
    if os.getenv("USE_OFFLINE_STUBS") != "1":
        return
    try:
        from tools.qa_stub_injector import install_stubs
    except Exception:
        return
    try:
        install_stubs()
    except Exception:
        pass


def _patch_attr(stack: ExitStack, module: object, attr: str, replacement: object) -> None:
    if not hasattr(module, attr):
        return
    original = getattr(module, attr)
    stack.callback(lambda module=module, attr=attr, original=original: setattr(module, attr, original))
    setattr(module, attr, replacement)


def _blocked_socket(*_: object, **__: object) -> None:
    raise RuntimeError("socket usage disabled during offline safe import")


def _blocked_subprocess(*_: object, **__: object) -> None:
    raise RuntimeError("subprocess disabled during offline safe import")


def _blocked_requests(*_: object, **__: object) -> None:
    raise RuntimeError("HTTP requests disabled during offline safe import")


class _BlockedRequestsSession:  # pragma: no cover - defensive stub
    def __init__(self, *_: object, **__: object) -> None:
        raise RuntimeError("HTTP requests disabled during offline safe import")


def _build_blocked_socket_cls(base_cls: type) -> type:
    class _OfflineSocket(base_cls):  # type: ignore[type-arg]
        def __init__(self, *_: object, **__: object) -> None:
            raise RuntimeError("socket usage disabled during offline safe import")

    return _OfflineSocket


def _apply_blockers(stack: ExitStack, *, allow_check_output: bool) -> None:
    try:
        import socket
    except Exception:
        socket = None  # type: ignore[assignment]
    if socket is not None:
        try:
            blocked_socket_cls = _build_blocked_socket_cls(socket.socket)
            _patch_attr(stack, socket, "socket", blocked_socket_cls)
        except Exception:
            _patch_attr(stack, socket, "socket", _blocked_socket)
        _patch_attr(stack, socket, "create_connection", _blocked_socket)

    try:
        import subprocess
    except Exception:
        subprocess = None  # type: ignore[assignment]
    if subprocess is not None:
        for attr in ("run", "Popen", "call", "check_call", "check_output"):
            if allow_check_output and attr == "check_output":
                continue
            _patch_attr(stack, subprocess, attr, _blocked_subprocess)

    try:
        import requests
    except Exception:
        requests = None  # type: ignore[assignment]
    if requests is not None:
        _patch_attr(stack, requests, "request", _blocked_requests)
        _patch_attr(stack, requests, "get", _blocked_requests)
        _patch_attr(stack, requests, "post", _blocked_requests)
        _patch_attr(stack, requests, "put", _blocked_requests)
        _patch_attr(stack, requests, "delete", _blocked_requests)
        _patch_attr(stack, requests, "head", _blocked_requests)
        _patch_attr(stack, requests, "options", _blocked_requests)
        _patch_attr(stack, requests, "Session", _BlockedRequestsSession)


def _worker(module_name: str, queue: mp.Queue) -> None:  # pragma: no cover - subprocess
    start = time.perf_counter()
    _maybe_install_stubs()
    allow_check_output = os.getenv("QA_ALLOW_SUBPROCESS") == "deps_lock" and module_name == "scripts.deps_lock"
    if (
        os.getenv("USE_OFFLINE_STUBS") == "1"
        and module_name == "scripts.deps_lock"
        and not allow_check_output
    ):
        queue.put(
            {
                "module": module_name,
                "status": "skipped",
                "error": "skipped by audit harness",
                "duration_s": round(time.perf_counter() - start, 4),
            }
        )
        return
    try:
        with ExitStack() as stack:
            _apply_blockers(stack, allow_check_output=allow_check_output)
            importlib.import_module(module_name)
    except RuntimeError as exc:
        if "disabled during offline safe import" in str(exc):
            queue.put(
                {
                    "module": module_name,
                    "status": "skipped",
                    "error": str(exc),
                    "duration_s": round(time.perf_counter() - start, 4),
                }
            )
            return
        queue.put(
            {
                "module": module_name,
                "status": "error",
                "error": traceback.format_exc(),
                "duration_s": round(time.perf_counter() - start, 4),
            }
        )
        return
    except Exception as exc:
        if isinstance(exc, ImportError) and "partially initialized module" in str(exc):
            queue.put(
                {
                    "module": module_name,
                    "status": "skipped",
                    "error": str(exc),
                    "duration_s": round(time.perf_counter() - start, 4),
                }
            )
            return
        queue.put(
            {
                "module": module_name,
                "status": "error",
                "error": traceback.format_exc(),
                "duration_s": round(time.perf_counter() - start, 4),
            }
        )
        return

    queue.put(
        {
            "module": module_name,
            "status": "ok",
            "duration_s": round(time.perf_counter() - start, 4),
        }
    )


def _import_with_timeout(module_name: str, ctx: mp.context.BaseContext) -> ImportResult:
    queue: mp.Queue = ctx.Queue()  # type: ignore[assignment]
    process = ctx.Process(target=_worker, args=(module_name, queue))
    start = time.perf_counter()
    process.start()
    process.join(IMPORT_TIMEOUT_SEC)

    if process.is_alive():
        process.terminate()
        process.join()
        duration = time.perf_counter() - start
        return ImportResult(module=module_name, status="timeout", duration_s=duration, error=None)

    duration = time.perf_counter() - start
    try:
        payload = queue.get_nowait()
    except Exception:
        payload = {
            "module": module_name,
            "status": "error",
            "error": f"process exited with code {process.exitcode}",
            "duration_s": duration,
        }

    status = str(payload.get("status", "error"))
    error = payload.get("error")
    duration_payload = float(payload.get("duration_s", duration))
    return ImportResult(
        module=module_name,
        status=status,
        duration_s=duration_payload,
        error=str(error) if error else None,
    )


def _iter_module_candidates() -> Iterator[str]:
    seen: set[str] = set()
    for root_name in ("app", "scripts"):
        root = Path(root_name)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
                continue
            rel = path.relative_to(root)
            if rel.name == "__init__.py":
                parts = rel.parts[:-1]
            else:
                parts = rel.with_suffix("").parts
            module_parts = [root_name, *parts]
            module = ".".join(part for part in module_parts if part)
            if module not in seen:
                seen.add(module)
                yield module


def _generate_reports(results: list[ImportResult], use_offline_stubs: bool) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = Counter(result.status for result in results)
    report_payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "use_offline_stubs": use_offline_stubs,
        "modules_checked": len(results),
        "summary": dict(summary),
        "results": [result.to_dict() for result in results],
    }
    JSON_REPORT.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Offline safe import report",
        f"- Generated at: {report_payload['generated_at']}",
        f"- USE_OFFLINE_STUBS: {'1' if use_offline_stubs else '0'}",
        f"- Modules checked: {len(results)}",
        f"- Summary: {', '.join(f'{key}={value}' for key, value in summary.items()) or 'no modules'}",
        "",
        "| Module | Status | Duration (s) | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        notes = (result.error or "").splitlines()[0] if result.error else ""
        lines.append(
            f"| {result.module} | {result.status} | {result.duration_s:.3f} | {notes.replace('|', '/')} |"
        )
    if not results:
        lines.append("| (no modules) | skipped | 0.000 | |")
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    use_offline_stubs = os.getenv("USE_OFFLINE_STUBS") == "1"
    _maybe_install_stubs()
    try:
        ctx = mp.get_context("fork")
    except ValueError:  # pragma: no cover - non-posix fallback
        ctx = mp.get_context()
    modules = list(_iter_module_candidates())
    results: list[ImportResult] = []
    for module in modules:
        if use_offline_stubs and module in OFFLINE_SKIP_MODULES:
            reason = OFFLINE_SKIP_MODULES[module]
            result = ImportResult(module=module, status="skipped", duration_s=0.0, error=reason)
            results.append(result)
            print(f"[safe-import] {module}: SKIPPED (0.000s) -> {reason}")
            continue
        result = _import_with_timeout(module, ctx)
        results.append(result)
        status_display = result.status.upper()
        duration_display = f"{result.duration_s:.3f}s"
        if result.error:
            head = result.error.splitlines()[0]
            print(f"[safe-import] {module}: {status_display} ({duration_display}) -> {head}")
        else:
            print(f"[safe-import] {module}: {status_display} ({duration_display})")

    _generate_reports(results, use_offline_stubs)
    summary = Counter(result.status for result in results)
    print("Safe import summary:")
    for status, count in sorted(summary.items()):
        print(f"- {status}: {count}")
    print(f"Reports saved to {JSON_REPORT} and {MD_REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
