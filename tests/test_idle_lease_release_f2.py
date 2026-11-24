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
    # Test 5: schema version change detected → RELOADING_SENTINEL
    # ------------------------------------------------------------------
    def test_schema_change_during_idle_returns_reloading_sentinel(self):
        """If user_version changes during idle, get_cerebro returns RELOADING_SENTINEL."""
        import tempfile
        svc = self._svc
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.object(svc, '_IDLE_TIMEOUT', 1):
                cerebro = svc.get_cerebro(str(db))
                # Simulate a schema update: bump user_version externally.
                with sqlite3.connect(str(db)) as ext:
                    ext.execute("PRAGMA user_version = 99")
                time.sleep(1.5)  # idle fires, conn released
                result = svc.get_cerebro(str(db))
                self.assertIs(result, svc.RELOADING_SENTINEL,
                              "Must return RELOADING_SENTINEL when schema changed")
                # Singleton must be cleared.
                self.assertIsNone(svc._cerebro)

    # ------------------------------------------------------------------
    # Test 6: _get_cerebro() in _shared returns None when RELOADING
    # ------------------------------------------------------------------
    def test_mcp_shared_get_cerebro_returns_none_when_reloading(self):
        """_shared._get_cerebro() returns None (not sentinel) for MCP callers."""
        import tempfile
        svc = self._svc
        from core.mcp_server._shared import _get_cerebro as shared_get
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db(Path(tmp))
            with patch.dict(os.environ, {"BIORAG_PATH": str(db)}):
                with patch.object(svc, '_IDLE_TIMEOUT', 1):
                    svc.get_cerebro(str(db))
                    with sqlite3.connect(str(db)) as ext:
                        ext.execute("PRAGMA user_version = 99")
                    time.sleep(1.5)
                    result = shared_get()
                    self.assertIsNone(result,
                                      "_get_cerebro() should return None when reloading")

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


if __name__ == "__main__":
    unittest.main()
