"""Win32 lock wrapper tests run on every OS using mocked kernel32; live Windows CI is still needed."""
import ctypes
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from core import database_access


class WindowsLockWrapperTests(unittest.TestCase):
    def setUp(self):
        self.kernel = types.SimpleNamespace(
            LockFileEx=Mock(return_value=1),
            UnlockFileEx=Mock(return_value=1),
        )
        self.msvcrt = types.SimpleNamespace(get_osfhandle=lambda fd: fd + 1000)
        self.modules = patch.dict(sys.modules, {'msvcrt': self.msvcrt})
        self.modules.start()
        self.win_dll = patch.object(ctypes, 'WinDLL', return_value=self.kernel, create=True)
        self.win_dll.start()
        self.temp = tempfile.TemporaryFile(mode='w+')

    def tearDown(self):
        self.temp.close()
        self.win_dll.stop()
        self.modules.stop()

    def test_shared_and_exclusive_flags_and_unlock(self):
        shared = database_access._windows_lock(self.temp, exclusive=False)
        self.assertEqual(self.kernel.LockFileEx.call_args.args[1], 0x00000001)
        with patch.object(database_access.os, 'name', 'nt'):
            database_access._unlock(self.temp, shared)
        self.assertEqual(self.kernel.UnlockFileEx.call_count, 1)

        self.kernel.LockFileEx.reset_mock(return_value=True)
        exclusive = database_access._windows_lock(self.temp, exclusive=True)
        self.assertEqual(self.kernel.LockFileEx.call_args.args[1], 0x00000003)
        with patch.object(database_access.os, 'name', 'nt'):
            database_access._unlock(self.temp, exclusive)
        self.assertEqual(self.kernel.UnlockFileEx.call_count, 2)

    def test_windows_lock_contention_is_a_blocking_io_error(self):
        self.kernel.LockFileEx.return_value = 0
        with patch.object(ctypes, 'get_last_error', return_value=33, create=True):
            with self.assertRaises(BlockingIOError):
                database_access._windows_lock(self.temp, exclusive=True)

    def test_updater_lock_windows_flow(self):
        from core import updater
        from pathlib import Path
        import os
        with tempfile.TemporaryDirectory() as td:
            gitdir = Path(td)
            with patch.object(updater.os, 'name', 'nt'):
                with updater.update_lock(gitdir):
                    self.assertTrue((gitdir / 'biorag-update.lock').exists())
                    # Intentar adquirir concurrentemente simulando contention en Windows (error 33)
                    self.kernel.LockFileEx.return_value = 0
                    with patch.object(ctypes, 'get_last_error', return_value=33, create=True):
                        with self.assertRaisesRegex(updater.UpdateError, "UPDATE_LOCKED"):
                            with updater.update_lock(gitdir):
                                pass
            self.assertFalse((gitdir / 'biorag-update.lock').exists())



if __name__ == '__main__':
    unittest.main()
