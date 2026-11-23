"""Cross-platform inventory and orderly stop for processes holding a BioRAG DB.

Only processes which both hold this exact database and have an unambiguous BioRAG
entry point are ever stopped. Unknown holders cause a fail-closed update refusal.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import Any


class ProcessInspectionError(RuntimeError):
    pass


def _psutil():
    try:
        import psutil
    except ImportError as exc:
        raise ProcessInspectionError(
            "PROCESS_INSPECTION_UNAVAILABLE: install the declared psutil dependency; "
            "no process will be stopped without an ownership check."
        ) from exc
    return psutil


def _normalized(path: str | os.PathLike[str]) -> str:
    try:
        return os.path.normcase(str(Path(path).resolve(strict=False)))
    except (OSError, RuntimeError):
        return os.path.normcase(os.path.abspath(os.fspath(path)))


def _database_files(database: str | os.PathLike[str]) -> set[str]:
    path = Path(database).expanduser()
    candidates = (path, Path(str(path) + "-wal"), Path(str(path) + "-shm"),
                  path.with_name(path.name + ".maintenance.lock"))
    return {_normalized(item) for item in candidates}


def _classify(cmdline: list[str], cwd: str | None) -> str | None:
    """Recognize only supported BioRAG process entry points, never name substrings alone."""
    tokens = [str(token).replace("\\", "/").lower() for token in cmdline]
    joined = " ".join(tokens)
    if any(token.endswith("/graph_maintenance_daemon.py") for token in tokens):
        return "daemon"
    if any(token.endswith(("/sleep_cycle.py", "/sleep-cycle")) for token in tokens):
        return "worker"
    if any(token.endswith(("/biorag.py", "/biorag")) for token in tokens):
        return "cli"
    if any(token.endswith("/mcp_server.py") for token in tokens):
        return "mcp"
    for index, token in enumerate(tokens[:-1]):
        if token == "-m" and tokens[index + 1] in {
            "mcp_server", "mcp_server:main", "core.mcp_server.server"
        }:
            return "mcp"
    if "biorag-mcp" in joined or "biorag_mcp" in joined:
        return "mcp"
    if cwd and "memorybiorag" in cwd.replace("\\", "/").lower() and any(
        "mcp_server" in token for token in tokens
    ):
        return "mcp"
    return None


def _runtime_candidate(name: str) -> bool:
    value = name.lower()
    return (value.startswith(("python", "biorag")) or "sqlite" in value
            or "dbeaver" in value or "beekeeper" in value or "tableplus" in value)


def inspect_database_processes(
    database: str | os.PathLike[str], *, exclude_pids: set[int] | None = None
) -> dict[str, Any]:
    """List Python/SQLite processes holding this DB, WAL, SHM, or BioRAG lease file.

    This is diagnostic, not the synchronization primitive: the OS lease remains
    authoritative for managed clients. Access-denied candidate processes are scan gaps.
    """
    psutil = _psutil()
    targets = _database_files(database)
    holders: list[dict[str, Any]] = []
    scan_errors: list[str] = []
    excluded = set(exclude_pids or ())
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            pid = int(proc.info["pid"])
            if pid in excluded:
                continue
            name = proc.info.get("name") or "unknown"
            candidate = _runtime_candidate(name)
            try:
                files = proc.open_files()
            except (psutil.AccessDenied, PermissionError):
                if candidate:
                    scan_errors.append(f"pid={pid}: AccessDenied")
                continue
            matching = sorted({_normalized(item.path) for item in files} & targets)
            if not matching:
                continue
            cmdline = proc.info.get("cmdline") or []
            cwd = proc.info.get("cwd")
            holders.append({
                "pid": pid,
                "name": name,
                "kind": _classify(cmdline, cwd) or "unknown",
                "matched_files": matching,
                "creation_time": proc.create_time(),
            })
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, PermissionError) as exc:
            scan_errors.append(f"pid={getattr(proc, 'pid', '?')}: {type(exc).__name__}")
        except (psutil.Error, OSError) as exc:
            scan_errors.append(f"pid={getattr(proc, 'pid', '?')}: {type(exc).__name__}")
    return {
        "status": "complete" if not scan_errors else "partial",
        "database": str(Path(database).expanduser()),
        "holders": holders,
        "scan_errors": scan_errors[:50],
        "automatic_stop_policy": "known-biorag-only; unknown-holder-or-incomplete-scan=refuse",
    }


def stop_known_database_processes(
    database: str | os.PathLike[str], *, timeout: float = 12.0
) -> dict[str, Any]:
    """Terminate exact BioRAG MCP/daemon/CLI/worker DB users after CLI authorization.

    Any unknown holder or incomplete process inventory refuses before stopping anyone.
    Graceful termination is attempted first; only those same verified PIDs are force-killed
    after the deadline. The MCP host may restart its child; callers must still verify the
    final update and report restart-required to the agent.
    """
    psutil = _psutil()
    try:
        current = psutil.Process(os.getpid())
        protected = {os.getpid(), *(parent.pid for parent in current.parents())}
    except (psutil.Error, OSError):
        protected = {os.getpid()}
    inventory = inspect_database_processes(database, exclude_pids=protected)
    holders = inventory["holders"]
    if inventory["status"] != "complete":
        raise ProcessInspectionError(
            "PROCESS_SCAN_INCOMPLETE: refusing to stop processes because at least one "
            "process could not be inspected; details=" + repr(inventory["scan_errors"])
        )
    unknown = [item for item in holders if item["kind"] not in {"mcp", "daemon", "worker", "cli"}]
    if unknown:
        raise ProcessInspectionError(
            "UNKNOWN_DATABASE_CONSUMER: no processes were stopped; close or identify "
            "these database holders first: " + repr(unknown)
        )

    targets = []
    for item in holders:
        try:
            proc = psutil.Process(item["pid"])
            # Defend against PID reuse between scan and signal.
            if abs(proc.create_time() - float(item["creation_time"])) > 0.01:
                continue
            targets.append((proc, item))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    for proc, _ in targets:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass

    _, alive = psutil.wait_procs([proc for proc, _ in targets], timeout=max(0.0, timeout))
    killed: list[int] = []
    for proc in alive:
        try:
            proc.kill()
            killed.append(proc.pid)
        except psutil.NoSuchProcess:
            pass
    if alive:
        _, still_alive = psutil.wait_procs(alive, timeout=3.0)
        if still_alive:
            raise ProcessInspectionError(
                "DATABASE_CONSUMERS_DID_NOT_EXIT: update refused; process IDs still alive="
                + repr([proc.pid for proc in still_alive])
            )
    return {
        "stopped": [item for _, item in targets],
        "force_killed_after_timeout": killed,
        "unknown_processes_stopped": [],
        "restart_required": True,
        "mcp_host_restart_managed_by_client": True,
    }
