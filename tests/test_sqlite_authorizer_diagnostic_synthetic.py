"""SQLite authorizer probes using only synthetic :memory: databases.

This is diagnostic/test code, not a production search harness. It never imports
or opens the project's memory database and never records SQL, arguments, or rows.
"""
from __future__ import annotations

import collections
import inspect
import json
import multiprocessing
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path


_WRITE_ACTION_NAMES = (
    "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE",
    "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TABLE",
    "SQLITE_CREATE_TEMP_INDEX", "SQLITE_CREATE_TEMP_TABLE",
    "SQLITE_CREATE_TEMP_TRIGGER", "SQLITE_CREATE_TEMP_VIEW",
    "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_VIEW",
    "SQLITE_DROP_INDEX", "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_INDEX", "SQLITE_DROP_TEMP_TABLE",
    "SQLITE_DROP_TEMP_TRIGGER", "SQLITE_DROP_TEMP_VIEW",
    "SQLITE_DROP_TRIGGER", "SQLITE_DROP_VIEW", "SQLITE_ALTER_TABLE",
    "SQLITE_REINDEX", "SQLITE_ANALYZE", "SQLITE_ATTACH", "SQLITE_DETACH",
    "SQLITE_TRANSACTION", "SQLITE_SAVEPOINT", "SQLITE_CREATE_VTABLE",
    "SQLITE_DROP_VTABLE",
)
_AUTHOR_ACTION_NAMES = _WRITE_ACTION_NAMES + (
    "SQLITE_PRAGMA", "SQLITE_READ", "SQLITE_SELECT", "SQLITE_FUNCTION",
)
_ACTION_NAMES = {
    getattr(sqlite3, name): name
    for name in _AUTHOR_ACTION_NAMES
    if hasattr(sqlite3, name)
}
_WRITE_ACTIONS = {
    getattr(sqlite3, name)
    for name in _WRITE_ACTION_NAMES
    if hasattr(sqlite3, name)
}
_REL_TABLES = frozenset({
    "concept_hubs", "concept_hub_bridges", "concept_hub_nodes",
    "corto_plazo", "corto_plazo_dimensiones", "largo_plazo",
    "largo_plazo_dimensiones", "nodo_grupos_semanticos", "sinapsis",
    "log_busquedas", "nodo_accesos_historial",
})


def _database_class(name: str | None) -> str:
    if name in ("main", "temp"):
        return name
    return "none" if name is None else "other"


def _safe_frames(limit: int = 5) -> list[dict[str, object]]:
    """Return callsite metadata only; never inspect locals, args, or source text."""
    frame = inspect.currentframe()
    if frame is not None:
        frame = frame.f_back
    out: list[dict[str, object]] = []
    while frame is not None and len(out) < limit:
        name = frame.f_code.co_name
        if name not in {"_safe_frames", "__call__"}:
            out.append({
                "file": os.path.basename(frame.f_code.co_filename),
                "function": name,
                "line": frame.f_lineno,
            })
        frame = frame.f_back
    return out


def _read_only_pragma_allowed(arg1, arg2, database, source) -> bool:
    """Two exact metadata reads only; all other PRAGMA actions stay denied."""
    if arg1 == "database_list" and arg2 is None and database is None and source is None:
        return True
    return (
        arg1 == "table_info"
        and database == "main"
        and arg2 in _REL_TABLES
        and source is None
    )


class _SyntheticTrace:
    """Permissive observer for disposable view tests; never used on project DBs."""
    def __init__(self):
        self.phase = "setup"
        self.events: list[dict[str, object]] = []

    def __call__(self, action, arg1, arg2, database, source):
        is_catalog = arg1 in {"sqlite_master", "sqlite_temp_master", "sqlite_schema", "sqlite_temp_schema"}
        self.events.append({
            "phase": self.phase,
            "action": _ACTION_NAMES.get(action, f"ACTION_{action}"),
            "database": _database_class(database),
            "catalog_object": bool(is_catalog),
            "frames": _safe_frames(),
        })
        return sqlite3.SQLITE_OK


class _FirstViolationRecorder:
    """Fail-closed authorizer: persist/notify the first event, then deny it."""
    def __init__(self, phase, notify_conn):
        self.phase = phase
        self.notify_conn = notify_conn
        self.first_sent = False
        self.counts = collections.Counter()
        self.lock = threading.Lock()

    def __call__(self, action, arg1, arg2, database, source):
        is_pragma = action == getattr(sqlite3, "SQLITE_PRAGMA", -1)
        allowed_pragma = is_pragma and _read_only_pragma_allowed(
            arg1, arg2, database, source
        )
        denied_write = action in _WRITE_ACTIONS
        denied_pragma = is_pragma and not allowed_pragma
        if denied_write or denied_pragma:
            action_name = _ACTION_NAMES.get(action, f"ACTION_{action}")
            event = {
                "phase": self.phase,
                "action": action_name,
                "database": _database_class(database),
                "frames": _safe_frames(),
            }
            with self.lock:
                self.counts[(action_name, event["database"])] += 1
                if not self.first_sent:
                    # The supervisor persists this first-event message privately
                    # before terminating the worker. No SQL or values are sent.
                    self.notify_conn.send_bytes(json.dumps(event, sort_keys=True).encode("utf-8"))
                    self.first_sent = True
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK


def _synthetic_worker(notify_conn):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE synthetic_rows(value INTEGER)")
    recorder = _FirstViolationRecorder("synthetic_search", notify_conn)
    con.set_authorizer(recorder)
    try:
        # This is deliberately synthetic. The worker catches the denial just as
        # application code can, then waits so the parent supervisor can stop it.
        con.execute("INSERT INTO synthetic_rows VALUES (1)")
    except sqlite3.DatabaseError:
        pass
    time.sleep(30)


def _persist_first_event(event: dict[str, object], destination: Path) -> None:
    """Exclusive 0600 write + fsync, completed by supervisor before SIGTERM."""
    payload = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    dir_fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


class SyntheticTempViewTests(unittest.TestCase):
    def test_create_and_resolve_temp_view_catalog_actions(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE source_rows(k INTEGER, v TEXT)")
        con.execute("INSERT INTO source_rows VALUES (1, 'synthetic')")
        trace = _SyntheticTrace()
        con.set_authorizer(trace)

        def create_temp_view():
            trace.phase = "create_temp_view"
            con.execute("CREATE TEMP VIEW synthetic_view AS SELECT k, v FROM main.source_rows")

        def resolve_temp_view():
            trace.phase = "resolve_temp_view"
            return con.execute("SELECT k, v FROM temp.synthetic_view").fetchall()

        create_temp_view()
        resolved_rows = resolve_temp_view()
        create_events = [e for e in trace.events if e["phase"] == "create_temp_view"]
        resolve_events = [e for e in trace.events if e["phase"] == "resolve_temp_view"]
        create_actions = collections.Counter(
            (e["action"], e["database"], e["catalog_object"]) for e in create_events
        )
        resolve_catalog_dml = [
            e for e in resolve_events
            if e["catalog_object"] and e["action"] in {"SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE"}
        ]

        self.assertEqual(len(resolved_rows), 1)
        self.assertEqual(create_actions[("SQLITE_CREATE_TEMP_VIEW", "temp", False)], 1)
        self.assertEqual(resolve_catalog_dml, [])
        self.assertTrue(all("frames" in e and e["frames"] for e in create_events + resolve_events))
        print({
            "probe": "TEMP view create/resolve",
            "sqlite_version": sqlite3.sqlite_version,
            "create_catalog_dml": {
                f"{action}@{db}": count
                for (action, db, catalog), count in create_actions.items()
                if catalog and action in {"SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE"}
            },
            "create_temp_view_action_count": create_actions[("SQLITE_CREATE_TEMP_VIEW", "temp", False)],
            "resolve_catalog_dml_count": len(resolve_catalog_dml),
            "call_frames_captured": True,
            "synthetic_rows_resolved": len(resolved_rows),
        })
        con.close()


class SyntheticPragmaPolicyTests(unittest.TestCase):
    def test_exact_database_list_exception_and_other_pragmas_denied(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE concept_hubs(hub_id TEXT)")
        counters = collections.Counter()
        def auth(action, arg1, arg2, database, source):
            is_pragma = action == getattr(sqlite3, "SQLITE_PRAGMA", -1)
            if is_pragma and _read_only_pragma_allowed(arg1, arg2, database, source):
                counters[("allowed", arg1)] += 1
                return sqlite3.SQLITE_OK
            if is_pragma:
                counters[("denied", arg1)] += 1
                return sqlite3.SQLITE_DENY
            if action in _WRITE_ACTIONS:
                counters[("denied_write", _ACTION_NAMES.get(action, str(action)))] += 1
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        con.set_authorizer(auth)

        database_list = con.execute("PRAGMA database_list").fetchall()
        table_info = con.execute("PRAGMA main.table_info('concept_hubs')").fetchall()
        denied_names = (
            "foreign_keys=ON", "journal_mode=MEMORY", "data_version",
            "query_only=ON", "temp.table_info('concept_hubs')",
        )
        for pragma in denied_names:
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute(f"PRAGMA {pragma}").fetchall()

        self.assertGreaterEqual(len(database_list), 1)
        self.assertTrue(table_info)
        self.assertEqual(counters[("allowed", "database_list")], 1)
        self.assertEqual(counters[("allowed", "table_info")], 1)
        self.assertEqual(sum(v for (kind, _), v in counters.items() if kind == "denied"), len(denied_names))
        print({
            "probe": "strict PRAGMA allowlist",
            "allowed_exact_metadata_reads": ["database_list(no args)", "main.table_info(listed table)"],
            "other_pragmas_denied": len(denied_names),
            "denied_categories": ["foreign_keys", "journal_mode", "data_version", "query_only", "temp.table_info"],
            "database_list_returned_rows_disclosed": False,
        })
        con.close()


class SyntheticSupervisorTests(unittest.TestCase):
    def test_first_event_persisted_before_supervisor_terminates_worker(self):
        if "fork" not in multiprocessing.get_all_start_methods():
            self.skipTest("synthetic supervisor probe requires POSIX fork")
        ctx = multiprocessing.get_context("fork")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            os.chmod(directory, 0o700)
            event_path = directory / "first_guard_event.json"
            parent_conn, child_conn = ctx.Pipe(duplex=False)
            proc = ctx.Process(target=_synthetic_worker, args=(child_conn,))
            proc.start()
            child_conn.close()
            try:
                self.assertTrue(parent_conn.poll(5), "no violation notification from synthetic worker")
                event = json.loads(parent_conn.recv_bytes().decode("utf-8"))
                # Persist the event before sending termination; no fixed/instant
                # interruption latency is asserted or claimed by this test.
                _persist_first_event(event, event_path)
                proc.terminate()
                proc.join(timeout=2)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=2)
                self.assertFalse(proc.is_alive())
                self.assertTrue(event_path.exists())
                self.assertEqual(event_path.stat().st_mode & 0o777, 0o600)
                saved = json.loads(event_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["action"], "SQLITE_INSERT")
                self.assertEqual(saved["phase"], "synthetic_search")
                self.assertTrue(saved["frames"])
                self.assertFalse(set(saved) & {"sql", "arg1", "arg2", "query", "values", "locals"})
                print({
                    "probe": "synthetic supervisor",
                    "first_event_durable_before_termination": True,
                    "event_mode": "0600",
                    "worker_stopped_by_supervisor": True,
                    "call_frames_captured": True,
                    "sql_or_values_recorded": False,
                    "instant_interruption_claimed": False,
                })
            finally:
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=2)
                parent_conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
