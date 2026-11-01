"""SQLite authorizer + supervisor probes using synthetic :memory: databases only.

Diagnostic/test code, not a production search harness. It never imports or opens
the project's memory database and never records SQL, arguments, locals, or rows.
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
_GUARD_EXIT = 86


def _database_class(name: str | None) -> str:
    if name in ("main", "temp"):
        return name
    return "none" if name is None else "other"


def _safe_frames(limit: int = 5) -> list[dict[str, object]]:
    """Callsite metadata only; never inspect locals, args, or source text."""
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
    """Exact metadata reads; all other PRAGMA actions remain denied."""
    if arg1 == "database_list" and arg2 is None and database is None and source is None:
        return True
    return (
        arg1 == "table_info"
        and database == "main"
        and arg2 in _REL_TABLES
        and source is None
    )


def _persist_first_event(event: dict[str, object], destination: Path) -> None:
    """Exclusive 0600 write + fsync, completed before the supervisor signals."""
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


def _load_event(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


class _SyntheticTrace:
    """Permissive observer for disposable view tests; never used on project DBs."""
    def __init__(self):
        self.phase = "setup"
        self.events: list[dict[str, object]] = []

    def __call__(self, action, arg1, arg2, database, source):
        is_catalog = arg1 in {
            "sqlite_master", "sqlite_temp_master", "sqlite_schema", "sqlite_temp_schema"
        }
        self.events.append({
            "phase": self.phase,
            "action": _ACTION_NAMES.get(action, f"ACTION_{action}"),
            "database": _database_class(database),
            "catalog_object": bool(is_catalog),
            "frames": _safe_frames(),
        })
        return sqlite3.SQLITE_OK


class _FirstViolationRecorder:
    """Record one sanitized event, notify supervisor, and deny the SQLite action."""
    def __init__(self, phase, notify_conn, worker_event_path=None, fail_worker_save=False,
                 fail_communication=False):
        self.phase = phase
        self.notify_conn = notify_conn
        self.worker_event_path = Path(worker_event_path) if worker_event_path else None
        self.fail_worker_save = fail_worker_save
        self.fail_communication = fail_communication
        self.first_sent = False
        self.lock = threading.Lock()

    def __call__(self, action, arg1, arg2, database, source):
        is_pragma = action == getattr(sqlite3, "SQLITE_PRAGMA", -1)
        allowed_pragma = is_pragma and _read_only_pragma_allowed(
            arg1, arg2, database, source
        )
        denied = action in _WRITE_ACTIONS or (is_pragma and not allowed_pragma)
        if not denied:
            return sqlite3.SQLITE_OK

        event = {
            "phase": self.phase,
            "action": _ACTION_NAMES.get(action, f"ACTION_{action}"),
            "database": _database_class(database),
            "frames": _safe_frames(),
        }
        with self.lock:
            if not self.first_sent:
                self.first_sent = True
                worker_saved = False
                if self.worker_event_path is not None and not self.fail_worker_save:
                    try:
                        _persist_first_event(event, self.worker_event_path)
                        worker_saved = True
                    except OSError:
                        worker_saved = False
                message = dict(event, worker_event_saved=worker_saved)
                try:
                    if self.fail_communication:
                        self.notify_conn.close()
                    self.notify_conn.send_bytes(
                        json.dumps(message, sort_keys=True).encode("utf-8")
                    )
                except (BrokenPipeError, EOFError, OSError):
                    # Fail closed if the supervisor channel is unavailable.
                    os._exit(_GUARD_EXIT)
        return sqlite3.SQLITE_DENY


def _synthetic_worker(notify_conn, worker_event_path, mode):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE synthetic_rows(value INTEGER)")
    recorder = _FirstViolationRecorder(
        "synthetic_search", notify_conn,
        worker_event_path=worker_event_path,
        fail_worker_save=(mode == "event_save_failure"),
        fail_communication=(mode == "communication_failure"),
    )
    con.set_authorizer(recorder)
    try:
        # Synthetic only: capture the denial as ordinary engine code may do.
        con.execute("INSERT INTO synthetic_rows VALUES (1)")
    except sqlite3.DatabaseError:
        pass
    time.sleep(30)


def _stop_worker(proc) -> bool:
    """Request termination, wait a bounded grace, then escalate; no instant claim."""
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=1.0)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=1.0)
    return not proc.is_alive()


def _supervise_synthetic_attempt(ctx, mode, root: Path, primary_writer, fallback_writer):
    worker_event_path = root / f"worker_event_{mode}.json"
    supervisor_event_path = root / f"supervisor_event_{mode}.json"
    fallback_event_path = root / f"fallback_event_{mode}.json"
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_synthetic_worker,
        args=(child_conn, str(worker_event_path), mode),
    )
    proc.start()
    child_conn.close()
    event = None
    message_received = False
    try:
        if parent_conn.poll(5.0):
            try:
                event = json.loads(parent_conn.recv_bytes().decode("utf-8"))
                message_received = True
            except (EOFError, OSError, json.JSONDecodeError):
                message_received = False

        saved_to = None
        if message_received:
            try:
                primary_writer(event, supervisor_event_path)
                saved_to = "primary"
            except OSError:
                try:
                    fallback_writer(event, fallback_event_path)
                    saved_to = "fallback"
                except OSError:
                    saved_to = None
            stopped = _stop_worker(proc)
            status = "guard_event" if saved_to else "event_save_failed"
        else:
            # The child saves first; if IPC fails, inspect that private file and
            # still abort. A missing event is recorded as incomplete evidence.
            proc.join(timeout=1.0)
            event = _load_event(worker_event_path)
            if event is not None:
                try:
                    fallback_writer(event, supervisor_event_path)
                    saved_to = "supervisor_after_ipc_failure"
                except OSError:
                    saved_to = "worker_only"
            stopped = _stop_worker(proc)
            status = "communication_failure"
        return {
            "status": status,
            "message_received": message_received,
            "event_saved_to": saved_to,
            "worker_stopped": stopped,
            "worker_exitcode": proc.exitcode,
            "worker_event_exists": worker_event_path.exists(),
            "supervisor_event_exists": supervisor_event_path.exists(),
            "fallback_event_exists": fallback_event_path.exists(),
        }
    finally:
        parent_conn.close()
        if proc.is_alive():
            _stop_worker(proc)


def _run_synthetic_batch(modes, root: Path, primary_writer, fallback_writer):
    started = []
    outcomes = []
    for mode in modes:
        started.append(mode)
        outcome = _supervise_synthetic_attempt(
            multiprocessing.get_context("fork"), mode, root,
            primary_writer, fallback_writer,
        )
        outcomes.append(outcome)
        # Any violation, communication failure, or evidence-save failure aborts
        # the batch. No next worker/search is created.
        if outcome["status"] != "clean":
            break
    return started, outcomes


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
    @classmethod
    def setUpClass(cls):
        if "fork" not in multiprocessing.get_all_start_methods():
            raise unittest.SkipTest("synthetic supervisor probe requires POSIX fork")

    def test_first_event_saved_before_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            started, outcomes = _run_synthetic_batch(
                ["normal_violation", "must_not_start"], root,
                _persist_first_event, _persist_first_event,
            )
            outcome = outcomes[0]
            self.assertEqual(started, ["normal_violation"])
            self.assertTrue(outcome["message_received"])
            self.assertTrue(outcome["worker_stopped"])
            self.assertTrue(outcome["supervisor_event_exists"])
            saved = _load_event(root / "supervisor_event_normal_violation.json")
            self.assertEqual(saved["action"], "SQLITE_INSERT")
            self.assertTrue(saved["frames"])
            print({
                "probe": "first event + supervisor stop",
                "workers_started": len(started),
                "next_worker_started": False,
                "event_saved_before_termination": True,
                "worker_stopped": outcome["worker_stopped"],
                "instant_interruption_claimed": False,
            })

    def test_ipc_failure_stops_worker_and_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            started, outcomes = _run_synthetic_batch(
                ["communication_failure", "must_not_start"], root,
                _persist_first_event, _persist_first_event,
            )
            outcome = outcomes[0]
            self.assertEqual(started, ["communication_failure"])
            self.assertEqual(outcome["status"], "communication_failure")
            self.assertTrue(outcome["worker_stopped"])
            self.assertTrue(outcome["worker_event_exists"])
            self.assertTrue(outcome["supervisor_event_exists"])
            print({
                "probe": "IPC failure",
                "workers_started": len(started),
                "next_worker_started": False,
                "worker_event_preserved": True,
                "worker_stopped": outcome["worker_stopped"],
                "instant_interruption_claimed": False,
            })

    def test_event_save_failure_uses_fallback_and_aborts_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)

            def fail_primary(_event, _destination):
                raise OSError("synthetic primary event-save failure")

            started, outcomes = _run_synthetic_batch(
                ["event_save_failure", "must_not_start"], root,
                fail_primary, _persist_first_event,
            )
            outcome = outcomes[0]
            self.assertEqual(started, ["event_save_failure"])
            self.assertEqual(outcome["event_saved_to"], "fallback")
            self.assertTrue(outcome["worker_stopped"])
            self.assertTrue(outcome["fallback_event_exists"])
            self.assertFalse(outcome["worker_event_exists"])
            print({
                "probe": "event-save failure + fallback",
                "workers_started": len(started),
                "next_worker_started": False,
                "fallback_event_saved": outcome["fallback_event_exists"],
                "worker_stopped": outcome["worker_stopped"],
                "instant_interruption_claimed": False,
            })


if __name__ == "__main__":
    unittest.main(verbosity=2)
