"""Private-harness SQLite authorizer event and subprocess supervisor helpers.

This module is not imported by the memory engine. It records only sanitized
SQLite action metadata and callsite frames; no SQL, arguments, locals, or rows.
"""
from __future__ import annotations

import inspect
import json
import os
import select
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

GUARD_CHANNEL_FAILURE = 86
MAX_EVENT_BYTES = 2048


def database_class(name: str | None) -> str:
    if name in ("main", "temp"):
        return name
    return "none" if name is None else "other"


def safe_call_frames(limit: int = 5) -> list[dict[str, object]]:
    """Capture basename/function/line only; never inspect locals or arguments."""
    frame = inspect.currentframe()
    if frame is not None:
        frame = frame.f_back
    frames: list[dict[str, object]] = []
    while frame is not None and len(frames) < limit:
        if frame.f_code.co_name not in {"safe_call_frames", "__call__"}:
            frames.append({
                "file": os.path.basename(frame.f_code.co_filename),
                "function": frame.f_code.co_name,
                "line": frame.f_lineno,
            })
        frame = frame.f_back
    return frames


def readonly_pragma_allowed(action: int, arg1: Any, arg2: Any,
                            database: str | None, source: str | None,
                            relation_tables: set[str] | frozenset[str]) -> bool:
    """Exact allowlist: database_list(no args) and listed main.table_info only."""
    if action != getattr(sqlite3, "SQLITE_PRAGMA", -1):
        return False
    if arg1 == "database_list" and arg2 is None and database is None and source is None:
        return True
    return (
        arg1 == "table_info"
        and database == "main"
        and arg2 in relation_tables
        and source is None
    )


def sanitize_guard_event(event: dict[str, Any]) -> dict[str, object]:
    """Whitelist fields rather than trying to redact arbitrary callback data."""
    raw_frames = event.get("frames")
    frames = []
    if isinstance(raw_frames, list):
        for item in raw_frames[:5]:
            if not isinstance(item, dict):
                continue
            try:
                line = int(item.get("line", 0))
            except (TypeError, ValueError):
                line = 0
            frames.append({
                "file": os.path.basename(str(item.get("file", "")))[:120],
                "function": str(item.get("function", ""))[:80],
                "line": line,
            })
    action = str(event.get("action", "unknown"))[:80]
    phase = str(event.get("phase", "unknown"))[:40]
    db = event.get("database")
    return {
        "phase": phase,
        "action": action,
        "database": db if db in {"main", "temp", "none", "other"} else "other",
        "frames": frames,
    }


def persist_event_exclusive(event: dict[str, Any], destination: str | os.PathLike[str]) -> None:
    """Create a private event file exactly once, then fsync file and directory."""
    path = Path(destination)
    payload = json.dumps(sanitize_guard_event(event), sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def notify_first_event(event_fd: int, event: dict[str, Any],
                       worker_event_path: str | os.PathLike[str]) -> bool:
    """Persist locally first, then notify parent; exit code 86 if IPC fails."""
    safe = sanitize_guard_event(event)
    worker_saved = False
    try:
        persist_event_exclusive(safe, worker_event_path)
        worker_saved = True
    except OSError:
        worker_saved = False
    message = dict(safe, worker_event_saved=worker_saved)
    payload = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(payload) > MAX_EVENT_BYTES:
        os._exit(GUARD_CHANNEL_FAILURE)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(event_fd, view):]
    except OSError:
        # The worker-local event, if saved, survives; the parent treats this
        # nonzero exit as fatal and never advances to another worker.
        os._exit(GUARD_CHANNEL_FAILURE)
    return worker_saved


def _load_event(path: str | os.PathLike[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return sanitize_guard_event(value) if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _stop_subprocess(proc: subprocess.Popen, grace: float) -> bool:
    """Terminate, wait, then kill if needed; this does not claim zero latency."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                return False
    return proc.poll() is not None


def supervise_subprocess(proc: subprocess.Popen, event_read_fd: int,
                         worker_event_path: str | os.PathLike[str],
                         primary_event_path: str | os.PathLike[str],
                         fallback_event_path: str | os.PathLike[str],
                         timeout: float, grace: float = 1.0) -> dict[str, Any]:
    """Watch one worker. Any event/IPC failure/timeout aborts; never retries."""
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stopped = _stop_subprocess(proc, grace)
            return {"status": "worker_timeout", "worker_stopped": stopped,
                    "returncode": proc.poll(), "event_saved_to": None}

        ready, _, _ = select.select([event_read_fd], [], [], min(0.1, remaining))
        if ready:
            chunk = os.read(event_read_fd, MAX_EVENT_BYTES)
            if not chunk:
                # EOF without a frame is a channel failure. Recover a worker-local
                # first event if present, then stop regardless of process state.
                code = proc.poll()
                event = _load_event(worker_event_path)
                saved_to = "worker_only" if event is not None else None
                if event is not None:
                    try:
                        persist_event_exclusive(event, primary_event_path)
                        saved_to = "primary_after_channel_eof"
                    except OSError:
                        try:
                            persist_event_exclusive(event, fallback_event_path)
                            saved_to = "fallback_after_channel_eof"
                        except OSError:
                            saved_to = "worker_only"
                stopped = _stop_subprocess(proc, grace)
                return {"status": "worker_channel_failure", "worker_stopped": stopped,
                        "returncode": code if code is not None else proc.poll(),
                        "event_saved_to": saved_to, "event": event}
            buf.extend(chunk)
            if len(buf) > MAX_EVENT_BYTES:
                stopped = _stop_subprocess(proc, grace)
                return {"status": "oversized_guard_event", "worker_stopped": stopped,
                        "returncode": proc.poll(), "event_saved_to": None}
            if b"\n" in buf:
                raw = bytes(buf.split(b"\n", 1)[0])
                try:
                    event = sanitize_guard_event(json.loads(raw.decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                    stopped = _stop_subprocess(proc, grace)
                    return {"status": "malformed_guard_event", "worker_stopped": stopped,
                            "returncode": proc.poll(), "event_saved_to": None}
                try:
                    persist_event_exclusive(event, primary_event_path)
                    saved_to = "primary"
                except OSError:
                    try:
                        persist_event_exclusive(event, fallback_event_path)
                        saved_to = "fallback"
                    except OSError:
                        saved_to = "worker_only" if _load_event(worker_event_path) else None
                stopped = _stop_subprocess(proc, grace)
                status = "guard_event" if saved_to else "event_save_failure"
                return {"status": status, "worker_stopped": stopped,
                        "returncode": proc.poll(), "event_saved_to": saved_to,
                        "event": event}

        code = proc.poll()
        if code is not None:
            # A worker that exits without an event is not accepted as a clean
            # search result here; caller still checks its private result record.
            event = _load_event(worker_event_path)
            if code != 0 or event is not None:
                saved_to = "worker_only" if event is not None else None
                if event is not None:
                    try:
                        persist_event_exclusive(event, primary_event_path)
                        saved_to = "primary_after_worker_exit"
                    except OSError:
                        try:
                            persist_event_exclusive(event, fallback_event_path)
                            saved_to = "fallback_after_worker_exit"
                        except OSError:
                            saved_to = "worker_only"
                return {"status": "worker_exit_without_clean_completion",
                        "worker_stopped": True, "returncode": code,
                        "event_saved_to": saved_to}
            return {"status": "worker_exit", "worker_stopped": True,
                    "returncode": code, "event_saved_to": None}
