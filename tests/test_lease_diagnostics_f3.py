"""F3 — Lease Diagnostic Registry tests.

Verifica que cada cliente con conexión administrada registra un archivo con
lock exclusivo del SO en `<db>.leases/<pid>.json` con metadata (pid, command,
role, started_at), que los procesos muertos (kill -9) son ignorados por el
lock del kernel, y que si maintenance() o `biorag update` agotan el timeout,
reportan con claridad humana el PID y comando de quien bloquea.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import database_access as da


class LeaseDiagnosticsF3Tests(unittest.TestCase):
    def _make_db(self, tmp_dir: Path) -> Path:
        db = tmp_dir / "diag_test.db"
        conn = da.connect(str(db))
        conn.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")
        conn.commit()
        conn.close()
        return db

    def test_client_creates_os_locked_lease_metadata_and_cleans_on_close(self):
        """connect() registers <db>.leases/<pid>.json and refcounts multiple connections in-process."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            leases_dir = db.with_name(db.name + ".leases")
            lease_file = leases_dir / f"{os.getpid()}.json"

            c1 = da.connect(str(db))
            try:
                self.assertTrue(lease_file.exists(), "Diagnostic lease file was not created")
                data = json.loads(lease_file.read_text(encoding="utf-8"))
                self.assertEqual(data["pid"], os.getpid())
                self.assertIn("command", data)
                self.assertIn("role", data)
                self.assertIn("started_at", data)

                holders = da.active_lease_holders(db)
                self.assertEqual(len(holders), 1)
                self.assertEqual(holders[0]["pid"], os.getpid())

                # Second connection in same process keeps lease alive after first closes
                c2 = da.connect(str(db))
                c1.close()
                holders_mid = da.active_lease_holders(db)
                self.assertEqual(len(holders_mid), 1)
                c2.close()
            finally:
                try:
                    c1.close()
                except Exception:
                    pass

            self.assertEqual(da.active_lease_holders(db), [])

    def test_dead_process_lease_ignored_even_if_file_remains(self):
        """After kill -9, kernel releases the OS lock so active_lease_holders() ignores the stale file."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            script = (
                "import sys, time; sys.path.insert(0, '.')\n"
                "from core.database_access import connect\n"
                f"c = connect({repr(str(db))})\n"
                "print('READY', flush=True)\n"
                "time.sleep(30)\n"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            try:
                line = proc.stdout.readline().strip()
                self.assertEqual(line, "READY")
                holders = da.active_lease_holders(db)
                self.assertEqual([h["pid"] for h in holders], [proc.pid])

                # Kill -9: file remains on disk, lock is released by kernel
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)

                self.assertEqual(da.active_lease_holders(db), [])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)

    def test_maintenance_timeout_reports_active_holders_pid_and_command(self):
        """When maintenance() times out, MaintenanceError must include blocking PID and command."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            script = (
                "import sys, time; sys.path.insert(0, '.')\n"
                "from core.database_access import connect\n"
                f"c = connect({repr(str(db))})\n"
                "print('READY', flush=True)\n"
                "time.sleep(30)\n"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            try:
                line = proc.stdout.readline().strip()
                self.assertEqual(line, "READY")

                with self.assertRaises(da.MaintenanceError) as ctx:
                    with da.maintenance(db, timeout=0.2, progress_interval=10.0):
                        pass

                msg = str(ctx.exception)
                self.assertIn("DATABASE_IN_USE_OR_MAINTENANCE", msg)
                self.assertIn(str(proc.pid), msg)
                self.assertIn("Active clients:", msg)
            finally:
                proc.kill()
                proc.wait(timeout=5)

    def test_updater_cli_timeout_reports_active_holders(self):
        """updater.main() surfaces active client PIDs when MaintenanceError includes Active clients."""
        import io
        from contextlib import redirect_stderr
        from core import updater

        err = da.MaintenanceError(
            "DATABASE_IN_USE_OR_MAINTENANCE: close active BioRAG clients. "
            "Active clients: PID 42424 (mcp: python3 mcp_server.py)"
        )
        stderr_buf = io.StringIO()
        with patch.object(updater, "apply", side_effect=err):
            with redirect_stderr(stderr_buf):
                rc = updater.main(["--db", "/tmp/dummy.db", "--wait", "0"])
        self.assertEqual(rc, 1)
        payload = json.loads(stderr_buf.getvalue().strip())
        self.assertEqual(payload["status"], "error")
        self.assertIn("42424", payload["message"])
        self.assertIn("mcp_server.py", payload["message"])

    def test_lease_metadata_does_not_store_full_sys_argv(self):
        """Diagnostic lease metadata must only record program basename and role, not full argv."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            lease_file = db.with_name(db.name + ".leases") / f"{os.getpid()}.json"
            with patch.object(sys, "argv", ["/usr/bin/mcp_server.py", "--secret-token", "super_secret_123"]):
                conn = da.connect(str(db))
                try:
                    data = json.loads(lease_file.read_text(encoding="utf-8"))
                    self.assertEqual(data["command"], "mcp_server.py")
                    self.assertNotIn("super_secret_123", json.dumps(data))
                finally:
                    conn.close()

    def test_maintenance_timeout_falls_back_to_process_inspection_for_legacy_holder(self):
        """A legacy process holding DB + maintenance.lock without .leases/ must still be reported via process_inspection."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._make_db(Path(tmp))
            lock_path = db.with_name(db.name + ".maintenance.lock")
            script = (
                "import fcntl, os, sqlite3, time\n"
                f"con = sqlite3.connect({repr(str(db))})\n"
                f"fd = os.open({repr(str(lock_path))}, os.O_RDWR | os.O_CREAT, 0o600)\n"
                "fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)\n"
                "print('READY', flush=True)\n"
                "time.sleep(30)\n"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            try:
                line = proc.stdout.readline().strip()
                self.assertEqual(line, "READY")
                self.assertEqual(da.active_lease_holders(db), [])

                with self.assertRaises(da.MaintenanceError) as ctx:
                    with da.maintenance(db, timeout=0.2, progress_interval=10.0):
                        pass

                msg = str(ctx.exception)
                self.assertIn("Active clients:", msg)
                self.assertIn(str(proc.pid), msg)
            finally:
                proc.kill()
                proc.wait(timeout=5)

    def test_gc_reentrancy_during_acquire_does_not_deadlock(self):
        """Re-entering _release_diagnostic_lease (e.g. via __del__ during GC) inside _acquire_diagnostic_lease must not deadlock."""
        import threading
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db1 = self._make_db(Path(tmp) / "a")
            db2 = Path(tmp) / "b" / "diag_test.db"
            c1 = da.connect(str(db1))
            c1.close()

            # Simulate GC __del__ triggering _release_diagnostic_lease on the same thread inside _acquire_diagnostic_lease
            orig_client_role = da._client_role

            def reentrant_role():
                da._release_diagnostic_lease(db1)
                return orig_client_role()

            finished = threading.Event()
            errors = []

            def run_acquire():
                try:
                    with patch.object(da, "_client_role", side_effect=reentrant_role):
                        c2 = da.connect(str(db2))
                        c2.close()
                except Exception as exc:
                    errors.append(exc)
                finally:
                    finished.set()

            t = threading.Thread(target=run_acquire, daemon=True)
            t.start()
            self.assertTrue(finished.wait(timeout=2.0), "Deadlock detected in _DIAG_LOCK on same-thread reentrancy!")
            self.assertEqual(errors, [])

    def test_process_inspection_classifies_relative_entry_points_and_updater_action(self):
        """Relative entry points in same directory (e.g. 'python3 mcp_server.py') classify properly and updater suggests action."""
        import io
        from contextlib import redirect_stderr
        from core import process_inspection, updater

        self.assertEqual(process_inspection._classify(["python3", "mcp_server.py"], "/tmp/other"), "mcp")
        self.assertEqual(process_inspection._classify(["python3", "biorag.py", "buscar"], "/tmp/other"), "cli")

        err = da.MaintenanceError(
            "DATABASE_IN_USE_OR_MAINTENANCE: close active BioRAG clients. "
            "Active clients: PID 42424 (mcp: mcp_server.py)"
        )
        stderr_buf = io.StringIO()
        with patch.object(updater, "apply", side_effect=err):
            with redirect_stderr(stderr_buf):
                rc = updater.main(["--db", "/tmp/dummy.db", "--wait", "0"])
        self.assertEqual(rc, 1)
        payload = json.loads(stderr_buf.getvalue().strip())
        self.assertIn("Close or restart", payload["message"])


if __name__ == "__main__":
    unittest.main()
