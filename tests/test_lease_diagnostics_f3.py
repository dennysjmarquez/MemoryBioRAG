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


if __name__ == "__main__":
    unittest.main()
