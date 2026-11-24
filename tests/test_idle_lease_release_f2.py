"""F2 — Idle Lease Release tests.

Verifica que memory_service libera la conexión SQLite + el lease compartido
tras el timeout de inactividad, y la restaura en ~2 ms al llegar el siguiente
request sin reconstruir SQLiteMemoryBioRAG (~11.6 s).

También verifica que si user_version cambió durante la inactividad (update
aplicado), se devuelve RELOADING_SENTINEL y el singleton se descarta limpiamente.
"""
import os
import sqlite3
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Force idle timeout to a short value for tests (overriding env before import).
os.environ.setdefault("BIORAG_IDLE_TIMEOUT_SECONDS", "1")


class IdleLeaseReleaseTests(unittest.TestCase):

    def setUp(self):
        """Each test gets a fresh in-memory singleton bound to a temp DB."""
        import core.memory_service as svc
        # Reset module globals between tests.
        with svc._lock:
            svc._cancel_idle_timer()
            svc._cerebro = None
            svc._path = None
            svc._idle_timer = None
        self._svc = svc

    def tearDown(self):
        import core.memory_service as svc
        with svc._lock:
            svc._cancel_idle_timer()
            if svc._cerebro is not None:
                try:
                    svc._cerebro._persistente = False
                    svc._cerebro.cerrar_sistema()
                except Exception:
                    pass
            svc._cerebro = None
            svc._path = None
            svc._idle_timer = None

    # ------------------------------------------------------------------
    # Helper: build a minimal valid SQLite DB in a tmp path
    # ------------------------------------------------------------------
    def _make_db(self, tmp_dir: Path) -> Path:
        db = tmp_dir / "test.db"
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE t (v TEXT)")
            con.execute("INSERT INTO t VALUES ('hello')")
        return db

    # ------------------------------------------------------------------
    # Test 1: idle timer arms on get_cerebro
    # ------------------------------------------------------------------
    def test_idle_timer_armed_after_get_cerebro(self):
        """An idle timer must be scheduled after every get_cerebro() call."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 60):
                svc.get_cerebro(str(db))
                self.assertIsNotNone(svc._idle_timer, "idle timer should be armed")
                self.assertTrue(svc._idle_timer.is_alive())

    # ------------------------------------------------------------------
    # Test 2: connection is released after idle timeout
    # ------------------------------------------------------------------
    def test_connection_released_after_idle_timeout(self):
        """After idle timeout, _conn_released must be True (lease dropped)."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro = svc.get_cerebro(str(db))
                self.assertFalse(getattr(cerebro, '_conn_released', False))
                # Wait for idle callback to fire.
                time.sleep(1.5)
                self.assertTrue(
                    getattr(cerebro, '_conn_released', False),
                    "_conn_released should be True after idle timeout",
                )

    # ------------------------------------------------------------------
    # Test 3: connection restored on next get_cerebro (no full rebuild)
    # ------------------------------------------------------------------
    def test_connection_restored_without_full_rebuild(self):
        """After idle release, get_cerebro() restores the connection in <50 ms."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro_before = svc.get_cerebro(str(db))
                id_before = id(cerebro_before)
                time.sleep(1.5)  # let idle callback fire
                self.assertTrue(getattr(cerebro_before, '_conn_released', False))

                t0 = time.perf_counter()
                cerebro_after = svc.get_cerebro(str(db))
                elapsed_ms = (time.perf_counter() - t0) * 1000

                self.assertIs(cerebro_after, cerebro_before,
                              "Must be the SAME object (no full rebuild)")
                self.assertEqual(id(cerebro_after), id_before)
                self.assertFalse(getattr(cerebro_after, '_conn_released', False))
                self.assertLess(elapsed_ms, 500,
                                f"Re-open took {elapsed_ms:.1f} ms, expected <500 ms")

    # ------------------------------------------------------------------
    # Test 4: re-opened connection is usable (SQL query works)
    # ------------------------------------------------------------------
    def test_reopened_connection_is_functional(self):
        """After idle release and re-open, the connection must execute queries."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro = svc.get_cerebro(str(db))
                time.sleep(1.5)
                cerebro_restored = svc.get_cerebro(str(db))
                # The connection must be live enough to execute a simple query.
                result = cerebro_restored.conn.execute("SELECT v FROM t").fetchone()
                self.assertEqual(result[0], "hello")

    # ------------------------------------------------------------------
    # Test 5: schema version change detected → BioragBusy
    # ------------------------------------------------------------------
    def test_schema_change_during_idle_raises_biorag_busy(self):
        """If user_version changes during idle, get_cerebro raises BioragBusy for reload."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro = svc.get_cerebro(str(db))
                # Simulate a schema update: bump user_version externally.
                with sqlite3.connect(str(db)) as ext:
                    ext.execute("PRAGMA user_version = 99")
                time.sleep(1.5)  # idle fires, conn released
                with self.assertRaises(svc.BioragBusy) as ctx:
                    svc.get_cerebro(str(db))
                self.assertIn("BioRAG is reloading", str(ctx.exception))
                self.assertEqual(ctx.exception.status, "retry")
                # Singleton must be cleared.
                self.assertIsNone(svc._cerebro)

    # ------------------------------------------------------------------
    # Test 6: _get_cerebro() in _shared propagates BioragBusy to MCP layer
    # ------------------------------------------------------------------
    def test_mcp_shared_get_cerebro_raises_biorag_busy_when_reloading(self):
        """_shared._get_cerebro() raises BioragBusy so call_tool can map it to retry."""
        import tempfile
        svc = self._svc
        from core.mcp_server._shared import _get_cerebro as shared_get
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            with patch.dict(os.environ, {"BIORAG_PATH": str(db)}):
                with patch.object(svc, '_IDLE_TIMEOUT', 1):
                    svc.get_cerebro(str(db))
                    with sqlite3.connect(str(db)) as ext:
                        ext.execute("PRAGMA user_version = 99")
                    time.sleep(1.5)
                    with self.assertRaises(svc.BioragBusy):
                        shared_get()

    # ------------------------------------------------------------------
    # Test 7: idle timer re-armed on each access (extends timeout)
    # ------------------------------------------------------------------
    def test_idle_timer_reset_on_each_access(self):
        """Repeated get_cerebro() calls must reset the idle countdown."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 2):
                svc.get_cerebro(str(db))
                timer_1 = svc._idle_timer
                time.sleep(0.5)
                svc.get_cerebro(str(db))  # re-arm
                timer_2 = svc._idle_timer
                # A new timer should have been created.
                self.assertIsNot(timer_1, timer_2,
                                 "Idle timer should be re-created on each access")
                # After 0.5s more (total 1s), connection should still be open
                # because the second access reset the 2s timer.
                time.sleep(0.6)
                cerebro = svc._cerebro
                self.assertFalse(
                    getattr(cerebro, '_conn_released', False),
                    "Connection must still be open (timer was reset)",
                )

    # ------------------------------------------------------------------
    # Test 8: reset_cerebro() cancels idle timer cleanly
    # ------------------------------------------------------------------
    def test_reset_cerebro_cancels_idle_timer(self):
        """reset_cerebro() must cancel any pending idle timer."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 60):
                svc.get_cerebro(str(db))
                self.assertIsNotNone(svc._idle_timer)
                svc.reset_cerebro()
                self.assertIsNone(svc._idle_timer)
                self.assertIsNone(svc._cerebro)

    # ------------------------------------------------------------------
    # Test 9: IDLE_TIMEOUT=0 disables idle release
    # ------------------------------------------------------------------
    def test_zero_idle_timeout_disables_idle_release(self):
        """BIORAG_IDLE_TIMEOUT_SECONDS=0 must leave the connection open indefinitely."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 0):
                cerebro = svc.get_cerebro(str(db))
                self.assertIsNone(svc._idle_timer, "No timer when timeout=0")
                # Simulate time passing: connection must remain open.
                time.sleep(0.1)
                self.assertFalse(getattr(cerebro, '_conn_released', False))


    # ------------------------------------------------------------------
    # Test 10 (T3): in-flight request prevents idle timer from closing connection
    # ------------------------------------------------------------------
    def test_in_flight_request_prevents_idle_close(self):
        """A request running longer than IDLE_TIMEOUT must NOT have its DB connection closed."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro = svc.get_cerebro(str(db))
                # Start an active request that takes 2.2s (longer than the 1s timeout)
                with svc.active_request():
                    time.sleep(1.5)
                    # Connection must still be open and usable
                    self.assertFalse(getattr(cerebro, '_conn_released', False),
                                     "Connection closed while request was in-flight!")
                    row = cerebro.conn.execute("SELECT v FROM t").fetchone()
                    self.assertEqual(row[0], "hello")
                # Once the request finishes, idle timer should fire after another timeout
                time.sleep(1.5)
                self.assertTrue(getattr(cerebro, '_conn_released', False),
                                "Connection should close after in-flight request finishes and idle period elapses")


    # ------------------------------------------------------------------
    # Test 11 (T2): request arriving during maintenance raises BioragBusy
    # ------------------------------------------------------------------
    def test_reopen_during_maintenance_raises_biorag_busy(self):
        """If maintenance is active in another thread/process when waking from idle, get_cerebro raises BioragBusy."""
        import tempfile
        import threading
        from core.database_access import maintenance
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro = svc.get_cerebro(str(db))
                time.sleep(1.2)  # wait for idle release
                self.assertTrue(getattr(cerebro, '_conn_released', False))

                # Acquire exclusive maintenance lease in a separate thread so it is not delegated
                holder_started = threading.Event()
                holder_stop = threading.Event()

                def hold_maintenance():
                    with maintenance(db):
                        holder_started.set()
                        holder_stop.wait(timeout=5)

                t = threading.Thread(target=hold_maintenance, daemon=True)
                t.start()
                holder_started.wait(timeout=2)

                try:
                    with self.assertRaises(svc.BioragBusy) as ctx:
                        svc.get_cerebro(str(db))
                    self.assertIn("BioRAG is updating", str(ctx.exception))
                    self.assertEqual(ctx.exception.status, "retry")
                finally:
                    holder_stop.set()
                    t.join(timeout=1)

    # ------------------------------------------------------------------
    # Test 12 (T2/T4): MCP call_tool catches BioragBusy and returns structured retry
    # ------------------------------------------------------------------
    def test_mcp_call_tool_catches_biorag_busy_and_returns_structured_retry(self):
        """MCP VersionAwareServer.call_tool must catch BioragBusy and return structured retry JSON."""
        import asyncio
        import json
        from mcp.server.fastmcp import FastMCP
        from core.mcp_server.update_checker import UpdateChecker, version_aware_server_class
        from core.memory_service import BioragBusy

        checker = UpdateChecker()
        ServerCls = version_aware_server_class(FastMCP, checker)
        server = ServerCls("test-server")

        @server.tool()
        def busy_tool() -> str:
            raise BioragBusy("BioRAG is updating, retry in a few seconds", status="retry")

        result = asyncio.run(server.call_tool("busy_tool", {}))
        self.assertTrue(len(result) >= 1)
        data = json.loads(result[0].text)
        self.assertEqual(data["status"], "retry")
        self.assertIn("BioRAG is updating", data["message"])


    # ------------------------------------------------------------------
    # Test 13 (T5): continuous traffic does not starve maintenance (anti-starvation gate)
    # ------------------------------------------------------------------
    def test_continuous_traffic_does_not_starve_maintenance(self):
        """Under continuous query traffic, maintenance must acquire exclusive lock within timeout."""
        import tempfile
        import threading
        from core.database_access import maintenance
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            cerebro = svc.get_cerebro(str(db))

            stop_traffic = threading.Event()
            client_errors = []
            successful_queries = 0
            retried_queries = 0

            def client_loop():
                nonlocal successful_queries, retried_queries
                while not stop_traffic.is_set():
                    try:
                        with svc.active_request():
                            c = svc.get_cerebro(str(db))
                            row = c.conn.execute("SELECT v FROM t").fetchone()
                            if row and row[0] == "hello":
                                successful_queries += 1
                    except svc.BioragBusy:
                        retried_queries += 1
                    except Exception as exc:
                        client_errors.append(exc)
                    time.sleep(0.05)

            # Start continuous background traffic
            traffic_thread = threading.Thread(target=client_loop, daemon=True)
            traffic_thread.start()
            time.sleep(0.2)  # let some queries run

            # Updater attempts to enter maintenance
            maintenance_entered = False
            t0 = time.perf_counter()
            try:
                with maintenance(db, timeout=3):
                    maintenance_entered = True
                    # Hold maintenance briefly while traffic is still trying
                    time.sleep(0.3)
            finally:
                stop_traffic.set()
                traffic_thread.join(timeout=2)

            elapsed = time.perf_counter() - t0
            self.assertTrue(maintenance_entered, "Maintenance timed out: starved by continuous traffic!")
            self.assertEqual(client_errors, [], f"Client encountered unexpected errors: {client_errors}")
            self.assertGreater(successful_queries + retried_queries, 0)
            self.assertLess(elapsed, 3.5, f"Maintenance took too long: {elapsed:.2f}s")


    # ------------------------------------------------------------------
    # Test 14: kill -9 of waiting updater clears pending gate automatically
    # ------------------------------------------------------------------
    def test_kill9_updater_clears_pending_gate_automatically(self):
        """If an updater holding .maintenance.pending dies with SIGKILL, requests must resume without manual cleanup."""
        import signal
        import subprocess
        import sys
        import tempfile
        from core.database_access import connect as managed_connect, is_maintenance_pending

        svc = self._svc
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            # Hold a shared lease in this process so the subprocess updater stays waiting on the gate
            holder_conn = managed_connect(str(db), timeout=5)
            try:
                script = (
                    "import sys; sys.path.insert(0, '.')\n"
                    "from core.database_access import maintenance\n"
                    f"with maintenance({str(db)!r}, timeout=30):\n"
                    "    pass\n"
                )
                proc = subprocess.Popen(
                    [sys.executable, "-c", script],
                    cwd=str(Path(__file__).resolve().parent.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                # Wait until the subprocess activates the pending gate
                deadline = time.monotonic() + 10.0
                while not is_maintenance_pending(db) and time.monotonic() < deadline:
                    if proc.poll() is not None:
                        _, err = proc.communicate()
                        self.fail(f"Subprocess exited prematurely ({proc.returncode}): {err.decode()}")
                    time.sleep(0.05)
                self.assertTrue(is_maintenance_pending(db), "Pending gate was not activated by waiting updater")

                # Kill updater with SIGKILL (kill -9)
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            finally:
                holder_conn.close()

            # Without manual file deletion, gate must report False immediately
            self.assertFalse(
                is_maintenance_pending(db),
                "Pending gate stayed active after SIGKILL of updater!",
            )
            # And requests must succeed normally
            with svc.active_request():
                cerebro = svc.get_cerebro(str(db))
                row = cerebro.conn.execute("SELECT v FROM t").fetchone()
                self.assertEqual(row[0], "hello")

    # ------------------------------------------------------------------
    # Test 15: second maintenance() timeout does not clear first updater's gate
    # ------------------------------------------------------------------
    def test_second_maintenance_timeout_does_not_clear_first_pending_gate(self):
        """A second maintenance() timing out must NOT deactivate the first updater's pending gate."""
        import tempfile
        from core.database_access import MaintenanceError, connect as managed_connect, is_maintenance_pending, maintenance

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            holder_conn = managed_connect(str(db), timeout=5)
            first_done = threading.Event()
            first_error = []

            def run_first():
                try:
                    with maintenance(db, timeout=5):
                        first_done.set()
                except Exception as exc:
                    first_error.append(exc)

            t1 = threading.Thread(target=run_first, daemon=True)
            try:
                t1.start()
                deadline = time.monotonic() + 3.0
                while not is_maintenance_pending(db) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(is_maintenance_pending(db))

                # Second maintenance() times out while first is still waiting
                with self.assertRaises(MaintenanceError):
                    with maintenance(db, timeout=0.2):
                        pass

                # First updater is still waiting -> gate MUST remain active!
                self.assertTrue(
                    is_maintenance_pending(db),
                    "Second maintenance() cleared the first updater's pending gate on timeout!",
                )
            finally:
                holder_conn.close()
                t1.join(timeout=5)

            self.assertEqual(first_error, [])
            self.assertTrue(first_done.is_set())
            self.assertFalse(is_maintenance_pending(db))


    # ------------------------------------------------------------------
    # Test 16: maintenance() emits progress to stderr while waiting
    # ------------------------------------------------------------------
    def test_maintenance_emits_progress_to_stderr_while_waiting(self):
        """maintenance() must print progress messages to stderr during long waits."""
        import io
        import tempfile
        from contextlib import redirect_stderr
        from core.database_access import MaintenanceError, connect as managed_connect, maintenance

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            holder_conn = managed_connect(str(db), timeout=5)
            stderr_buf = io.StringIO()
            try:
                with redirect_stderr(stderr_buf):
                    with self.assertRaises(MaintenanceError):
                        with maintenance(db, timeout=1.2, progress_interval=0.4):
                            pass
            finally:
                holder_conn.close()

            output = stderr_buf.getvalue()
            self.assertIn("Waiting for BioRAG clients to close...", output)


if __name__ == "__main__":
    unittest.main()
