"""Process inventory tests use fake process tables; never signal a real process."""
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from core import process_inspection as inspection


class FakeProcess:
    def __init__(self, pid, name, command, path, *, access_error=False):
        self.pid = pid
        self.info = {"pid": pid, "name": name, "cmdline": command, "cwd": "/tmp"}
        self.path = path
        self.access_error = access_error
        self.terminated = False
        self.killed = False
        self._creation_time = 1000.0 + pid

    def open_files(self):
        if self.access_error:
            raise FakePsutil.AccessDenied(self.pid)
        return [SimpleNamespace(path=self.path)]

    def create_time(self):
        return self._creation_time

    def parents(self):
        return []

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class FakePsutil:
    class Error(Exception):
        pass

    class NoSuchProcess(Error):
        pass

    class AccessDenied(Error):
        pass

    def __init__(self, processes):
        self.items = {p.pid: p for p in processes}

    def process_iter(self, attrs):
        return list(self.items.values())

    def Process(self, pid):
        return self.items[pid]

    @staticmethod
    def wait_procs(processes, timeout):
        return ([p for p in processes if p.terminated or p.killed],
                [p for p in processes if not p.terminated and not p.killed])


class ProcessInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = __import__('tempfile').TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'memory.db'
        self.lock = Path(str(self.db) + '.maintenance.lock')
        self.lock.touch()

    def tearDown(self):
        self.tmp.cleanup()

    def test_inventory_identifies_only_exact_db_holders_and_masks_command(self):
        holder = FakeProcess(991001, 'python', ['python', '/repo/mcp_server.py', '--secret', 'do-not-show'], str(self.lock))
        non_holder = FakeProcess(991002, 'python', ['python', '/other.py'], str(self.db) + '.elsewhere')
        fake = FakePsutil([holder, non_holder])
        with patch.object(inspection, '_psutil', return_value=fake):
            report = inspection.inspect_database_processes(self.db)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual([item['pid'] for item in report['holders']], [991001])
        self.assertEqual(report['holders'][0]['kind'], 'mcp')
        self.assertNotIn('do-not-show', repr(report))

    def test_unknown_consumer_refuses_before_stopping_any_process(self):
        holder = FakeProcess(991003, 'python', ['python', '/tmp/custom_reader.py'], str(self.lock))
        fake = FakePsutil([holder, FakeProcess(__import__('os').getpid(), 'python', [], str(self.db) + '.other')])
        with patch.object(inspection, '_psutil', return_value=fake):
            with self.assertRaisesRegex(inspection.ProcessInspectionError, 'UNKNOWN_DATABASE_CONSUMER'):
                inspection.stop_known_database_processes(self.db)
        self.assertFalse(holder.terminated)
        self.assertFalse(holder.killed)

    def test_known_mcp_is_terminated_only_after_identity_recheck(self):
        holder = FakeProcess(991004, 'python', ['python', '/repo/mcp_server.py'], str(self.lock))
        current = FakeProcess(991005, 'python', ['python', '-m', 'core.updater'], str(self.db) + '.not-open')
        fake = FakePsutil([holder, current])
        with patch.object(inspection, '_psutil', return_value=fake), \
             patch('os.getpid', return_value=991005):
            report = inspection.stop_known_database_processes(self.db, timeout=0)
        self.assertEqual([item['pid'] for item in report['stopped']], [991004])
        self.assertTrue(holder.terminated)
        self.assertFalse(holder.killed)
        self.assertEqual(report['unknown_processes_stopped'], [])

    def test_incomplete_scan_fails_closed(self):
        holder = FakeProcess(991006, 'python', ['python', '/repo/mcp_server.py'], str(self.lock), access_error=True)
        current = FakeProcess(991007, 'python', ['python', '-m', 'core.updater'], str(self.db) + '.not-open')
        fake = FakePsutil([holder, current])
        with patch.object(inspection, '_psutil', return_value=fake), \
             patch('os.getpid', return_value=991007):
            with self.assertRaisesRegex(inspection.ProcessInspectionError, 'PROCESS_SCAN_INCOMPLETE'):
                inspection.stop_known_database_processes(self.db)
        self.assertFalse(holder.terminated)

    def test_managed_daemon_status_needs_only_biorag_pid_file(self):
        with patch('core.daemon_lifecycle._leer_pid', return_value=None), \
             patch.object(inspection, '_psutil', side_effect=AssertionError('must not scan')):
            self.assertEqual(inspection.managed_daemon_status('/repo'), {'status':'not_running'})

    def test_managed_daemon_stops_only_verified_pid_and_waits(self):
        root=Path(self.tmp.name)/'checkout'
        script=str(root/'graph_maintenance_daemon.py')
        class Managed:
            pid=991008
            def __init__(self):self.stopped=False;self.waited=False
            def cmdline(self):return [sys.executable,script]
            def cwd(self):return str(root)
            def uids(self):return SimpleNamespace(real=os.getuid())
            def terminate(self):self.stopped=True
            def wait(self,timeout):self.waited=True
            def kill(self):raise AssertionError('graceful stop should finish')
        managed=Managed()
        fake=SimpleNamespace(Process=lambda pid:managed,
                             NoSuchProcess=type('NoSuchProcess',(Exception,),{}),
                             AccessDenied=type('AccessDenied',(Exception,),{}),
                             TimeoutExpired=type('TimeoutExpired',(Exception,),{}))
        with patch('core.daemon_lifecycle._leer_pid',return_value=managed.pid), \
             patch('core.daemon_lifecycle._borrar_pid') as clear_pid, \
             patch.object(inspection,'_psutil',return_value=fake):
            result=inspection.stop_managed_daemon(root,timeout=1)
        self.assertEqual(result['status'],'stopped')
        self.assertTrue(managed.stopped);self.assertTrue(managed.waited)
        clear_pid.assert_called_once_with()

    def test_managed_daemon_identity_mismatch_is_never_signaled(self):
        root=Path(self.tmp.name)/'checkout'
        class WrongProcess:
            pid=991009
            def cmdline(self):return [sys.executable,'/tmp/unrelated.py']
            def cwd(self):return '/tmp'
            def terminate(self):raise AssertionError('must not signal')
        fake=SimpleNamespace(Process=lambda pid:WrongProcess(),
                             NoSuchProcess=type('NoSuchProcess',(Exception,),{}),
                             AccessDenied=type('AccessDenied',(Exception,),{}))
        with patch('core.daemon_lifecycle._leer_pid',return_value=991009), \
             patch.object(inspection,'_psutil',return_value=fake):
            with self.assertRaisesRegex(inspection.ProcessInspectionError,'IDENTITY_MISMATCH'):
                inspection.stop_managed_daemon(root)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'live process-handle test currently runs on Linux only')
    def test_linux_inventory_and_stop_use_only_synthetic_mcp_process(self):
        script = Path(self.tmp.name) / 'mcp_server.py'
        script.write_text(
            'import sys, time\n'
            'from core.database_access import connect\n'
            'db = connect(sys.argv[1])\n'
            'db.execute("CREATE TABLE IF NOT EXISTS sample (value TEXT)")\n'
            'print("ready", flush=True)\n'
            'time.sleep(60)\n'
        )
        env = dict(os.environ)
        repo = str(Path(__file__).resolve().parents[1])
        env['PYTHONPATH'] = repo + os.pathsep + env.get('PYTHONPATH', '')
        proc = subprocess.Popen([sys.executable, str(script), str(self.db)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            self.assertEqual(proc.stdout.readline().decode().strip(), 'ready')
            # Keep the live-handle assertion deterministic across CI hosts that may
            # have unrelated permission-restricted Python processes.
            real_psutil=inspection._psutil()
            class IsolatedPsutil:
                def process_iter(self, attrs):
                    return [item for item in real_psutil.process_iter(attrs) if item.pid==proc.pid]
                def __getattr__(self, name):
                    return getattr(real_psutil, name)
            with patch.object(inspection,'_psutil',return_value=IsolatedPsutil()):
                report = inspection.inspect_database_processes(self.db)
                matches = [item for item in report['holders'] if item['pid'] == proc.pid]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0]['kind'], 'mcp')
                stop_report = inspection.stop_known_database_processes(self.db, timeout=3)
                self.assertIn(proc.pid, [item['pid'] for item in stop_report['stopped']])
                self.assertIsNotNone(proc.wait(timeout=3))
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == '__main__':
    unittest.main()
