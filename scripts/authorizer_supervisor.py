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
import stat
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


def _private_result_is_valid(path: str | os.PathLike[str]) -> bool:
    """Accept only a private, regular JSON result record explicitly marked ok."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return False
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or info.st_size > 1024 * 1024):
            return False
        chunks = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                return False
            chunks.append(chunk)
            remaining -= len(chunk)
        value = json.loads(b"".join(chunks).decode("utf-8"))
        return isinstance(value, dict) and value.get("status") == "ok"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    finally:
        os.close(fd)


def _drain_exited_channel(fd: int) -> tuple[bytes, bool, bool]:
    """Nonblocking drain after poll observes exit: bytes, EOF-seen, oversized."""
    was_blocking = os.get_blocking(fd)
    if was_blocking:
        os.set_blocking(fd, False)
    chunks = bytearray()
    eof = False
    oversized = False
    try:
        while True:
            try:
                chunk = os.read(fd, MAX_EVENT_BYTES + 1)
            except BlockingIOError:
                break
            if not chunk:
                eof = True
                break
            chunks.extend(chunk)
            if len(chunks) > MAX_EVENT_BYTES:
                oversized = True
                break
    finally:
        if was_blocking:
            os.set_blocking(fd, True)
    return bytes(chunks), eof, oversized


def _parse_event_frame(buf: bytes) -> tuple[dict[str, Any] | None, str | None]:
    if not buf.endswith(b"\n") or buf.count(b"\n") != 1:
        return None, "partial_guard_event"
    try:
        value = json.loads(buf[:-1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "malformed_guard_event"
    if not isinstance(value, dict):
        return None, "malformed_guard_event"
    return sanitize_guard_event(value), None


def _save_event(event: dict[str, Any], primary_event_path: str | os.PathLike[str],
                fallback_event_path: str | os.PathLike[str],
                worker_event_path: str | os.PathLike[str]) -> str | None:
    try:
        persist_event_exclusive(event, primary_event_path)
        return "primary"
    except OSError:
        try:
            persist_event_exclusive(event, fallback_event_path)
            return "fallback"
        except OSError:
            return "worker_only" if _load_event(worker_event_path) is not None else None


def _guard_outcome(proc: subprocess.Popen, event: dict[str, Any],
                   worker_event_path: str | os.PathLike[str],
                   primary_event_path: str | os.PathLike[str],
                   fallback_event_path: str | os.PathLike[str],
                   grace: float) -> dict[str, Any]:
    saved_to = _save_event(event, primary_event_path, fallback_event_path,
                           worker_event_path)
    stopped = _stop_subprocess(proc, grace)
    return {"status": "guard_event" if saved_to else "event_save_failure",
            "worker_stopped": stopped, "returncode": proc.poll(),
            "event_saved_to": saved_to, "event": event}


def supervise_subprocess(proc: subprocess.Popen, event_read_fd: int,
                         worker_event_path: str | os.PathLike[str],
                         primary_event_path: str | os.PathLike[str],
                         fallback_event_path: str | os.PathLike[str],
                         private_result_path: str | os.PathLike[str],
                         timeout: float, grace: float = 1.0) -> dict[str, Any]:
    """Watch one worker; clean exit requires EOF, no event, and a private ok result."""
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
            chunk = os.read(event_read_fd, MAX_EVENT_BYTES + 1)
            if not chunk:
                code = proc.poll()
                if code is None:
                    try:
                        code = proc.wait(timeout=min(remaining, grace))
                    except subprocess.TimeoutExpired:
                        stopped = _stop_subprocess(proc, grace)
                        event = _load_event(worker_event_path)
                        saved_to = (_save_event(event, primary_event_path,
                                                fallback_event_path, worker_event_path)
                                    if event is not None else None)
                        return {"status": "worker_channel_failure", "worker_stopped": stopped,
                                "returncode": proc.poll(), "event_saved_to": saved_to,
                                "event": event}
                # EOF is normal only after a clean process exit and with an empty channel.
                if buf:
                    event, error = _parse_event_frame(bytes(buf))
                    if event is not None:
                        return _guard_outcome(proc, event,
                                              worker_event_path, primary_event_path,
                                              fallback_event_path, grace)
                    return {"status": error, "worker_stopped": True,
                            "returncode": code, "event_saved_to": None}
                if code != 0:
                    event = _load_event(worker_event_path)
                    saved_to = (_save_event(event, primary_event_path,
                                            fallback_event_path, worker_event_path)
                                if event is not None else None)
                    return {"status": "worker_channel_failure", "worker_stopped": True,
                            "returncode": code, "event_saved_to": saved_to,
                            "event": event}
                event = _load_event(worker_event_path)
                if event is not None:
                    return _guard_outcome(proc, event,
                                          worker_event_path, primary_event_path,
                                          fallback_event_path, grace)
                if Path(worker_event_path).exists() or not _private_result_is_valid(private_result_path):
                    return {"status": "worker_result_invalid", "worker_stopped": True,
                            "returncode": code, "event_saved_to": None}
                return {"status": "worker_exit", "worker_stopped": True,
                        "returncode": code, "event_saved_to": None,
                        "channel_closed": True, "private_result_valid": True}

            buf.extend(chunk)
            if len(buf) > MAX_EVENT_BYTES:
                stopped = _stop_subprocess(proc, grace)
                return {"status": "oversized_guard_event", "worker_stopped": stopped,
                        "returncode": proc.poll(), "event_saved_to": None}
            if b"\n" in buf:
                event, error = _parse_event_frame(bytes(buf))
                if event is None:
                    stopped = _stop_subprocess(proc, grace)
                    return {"status": error, "worker_stopped": stopped,
                            "returncode": proc.poll(), "event_saved_to": None}
                return _guard_outcome(proc, event, worker_event_path,
                                      primary_event_path, fallback_event_path, grace)

        code = proc.poll()
        if code is not None:
            # select() can miss bytes that became readable as the process exited.
            # Drain directly after poll; process exit guarantees no future writes.
            drained, eof, oversized = _drain_exited_channel(event_read_fd)
            buf.extend(drained)
            if oversized or len(buf) > MAX_EVENT_BYTES:
                return {"status": "oversized_guard_event", "worker_stopped": True,
                        "returncode": code, "event_saved_to": None}
            if b"\n" in buf:
                event, error = _parse_event_frame(bytes(buf))
                if event is None:
                    return {"status": error, "worker_stopped": True,
                            "returncode": code, "event_saved_to": None}
                return _guard_outcome(proc, event, worker_event_path,
                                      primary_event_path, fallback_event_path, grace)
            if buf:
                return {"status": "partial_guard_event", "worker_stopped": True,
                        "returncode": code, "event_saved_to": None}
            if not eof:
                return {"status": "worker_channel_not_closed", "worker_stopped": True,
                        "returncode": code, "event_saved_to": None}
            if code != 0:
                event = _load_event(worker_event_path)
                saved_to = (_save_event(event, primary_event_path, fallback_event_path,
                                        worker_event_path)
                            if event is not None else None)
                return {"status": "worker_channel_failure", "worker_stopped": True,
                        "returncode": code, "event_saved_to": saved_to,
                        "event": event}
            event = _load_event(worker_event_path)
            if event is not None:
                return _guard_outcome(proc, event, worker_event_path,
                                      primary_event_path, fallback_event_path, grace)
            if Path(worker_event_path).exists() or not _private_result_is_valid(private_result_path):
                return {"status": "worker_result_invalid", "worker_stopped": True,
                        "returncode": code, "event_saved_to": None}
            return {"status": "worker_exit", "worker_stopped": True,
                    "returncode": code, "event_saved_to": None,
                    "channel_closed": True, "private_result_valid": True}
