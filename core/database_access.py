"""Cross-process SQLite leases for BioRAG clients and exclusive maintenance.

Every managed SQLite connection holds a shared OS lock. Updates/migrations require
an exclusive lock; the kernel releases a process's lock on exit/crash. This does not
lock out programs that bypass BioRAG and open SQLite directly.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from urllib.parse import unquote, urlsplit

TOKEN_ENV = 'BIORAG_MAINTENANCE_TOKEN'
_LOCAL_TOKEN = ContextVar('biorag_maintenance_token', default=None)


class MaintenanceError(RuntimeError):
    pass


def _path(database):
    value = str(database)
    if value == ':memory:' or (value.startswith('file:') and ('mode=memory' in value or urlsplit(value).path == ':memory:')):
        return None
    if value.startswith('file:'):
        parsed = urlsplit(value)
        value = unquote(parsed.path)
        if os.name == 'nt' and len(value) >= 3 and value[0] == '/' and value[2] == ':':
            value = value[1:]
    return Path(value).expanduser().resolve()


def _lock_path(database):
    return database.with_name(database.name + '.maintenance.lock')


def _pending_path(database):
    return database.with_name(database.name + '.maintenance.pending')


def is_maintenance_pending(database):
    path = _path(database)
    if path is None:
        return False
    return _pending_path(path).exists()


def _windows_lock(file, *, exclusive):
    """Acquire one byte with Win32 LockFileEx (shared readers, exclusive writer)."""
    import msvcrt

    class OVERLAPPED(ctypes.Structure):
        _fields_ = [
            ('Internal', ctypes.c_size_t),
            ('InternalHigh', ctypes.c_size_t),
            ('Offset', ctypes.c_uint32),
            ('OffsetHigh', ctypes.c_uint32),
            ('hEvent', ctypes.c_void_p),
        ]

    handle = msvcrt.get_osfhandle(file.fileno())
    overlapped = OVERLAPPED()
    flags = 0x00000001  # LOCKFILE_FAIL_IMMEDIATELY
    if exclusive:
        flags |= 0x00000002  # LOCKFILE_EXCLUSIVE_LOCK
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    lock = kernel32.LockFileEx
    lock.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                     ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(OVERLAPPED)]
    lock.restype = ctypes.c_int
    if not lock(handle, flags, 0, 1, 0, ctypes.byref(overlapped)):
        code = ctypes.get_last_error()
        if code in (32, 33):  # ERROR_SHARING_VIOLATION / ERROR_LOCK_VIOLATION
            raise BlockingIOError(code, 'database maintenance lease is held')
        raise OSError(code, ctypes.FormatError(code))
    return overlapped


def _unlock(file, overlapped):
    if os.name == 'nt':
        import msvcrt

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        unlock = kernel32.UnlockFileEx
        unlock.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                           ctypes.c_uint32, ctypes.c_void_p]
        unlock.restype = ctypes.c_int
        if not unlock(msvcrt.get_osfhandle(file.fileno()), 0, 1, 0, ctypes.byref(overlapped)):
            code = ctypes.get_last_error()
            raise OSError(code, ctypes.FormatError(code))
    else:
        import fcntl
        fcntl.flock(file, fcntl.LOCK_UN)


def _shared_lock_conflicts(path):
    """Return true only when another process owns an exclusive maintenance lease."""
    try:
        probe = open(path, 'r+')
    except OSError:
        return False
    try:
        if os.name == 'nt':
            overlap = _windows_lock(probe, exclusive=False)
            _unlock(probe, overlap)
            return False
        import fcntl
        try:
            fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(probe, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _delegated(database):
    token = _LOCAL_TOKEN.get() or os.environ.get(TOKEN_ENV)
    if not token:
        return False
    path = _lock_path(database)
    try:
        data = json.loads(path.read_text())
        if not secrets.compare_digest(token, data.get('token', '')):
            return False
        # A residual token after owner death is never enough to bypass the lease.
        return _shared_lock_conflicts(path)
    except (OSError, ValueError, TypeError, AttributeError):
        return False


class Lease:
    def __init__(self, database, exclusive=False):
        self.file = None
        self._overlapped = None
        if database is None or _delegated(database):
            return
        database.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(_lock_path(database), os.O_RDWR | os.O_CREAT, 0o600)
        self.file = os.fdopen(fd, 'r+')
        try:
            if os.name == 'posix':
                import fcntl
                operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(self.file, operation | fcntl.LOCK_NB)
            elif os.name == 'nt':
                self._overlapped = _windows_lock(self.file, exclusive=exclusive)
            elif exclusive:
                raise MaintenanceError('MAINTENANCE_PLATFORM_UNSUPPORTED: no tested OS lock backend')
        except (OSError, BlockingIOError) as exc:
            self.file.close()
            self.file = None
            self._overlapped = None
            code = 'DATABASE_IN_USE_OR_MAINTENANCE'
            raise MaintenanceError(code + ': close active BioRAG clients or wait for maintenance, then retry') from exc
        except Exception:
            self.file.close()
            self.file = None
            self._overlapped = None
            raise

    def close(self):
        if self.file is not None:
            try:
                _unlock(self.file, self._overlapped)
            finally:
                self.file.close()
                self.file = None
                self._overlapped = None


@contextmanager
def maintenance(database, timeout=30):
    path = _path(database)
    if path is None:
        yield None
        return
    if _delegated(path):
        yield _LOCAL_TOKEN.get() or os.environ[TOKEN_ENV]
        return

    # Signal to active readers/MCP that maintenance is pending (writer-priority gate)
    pending = _pending_path(path)
    pending_created = False
    try:
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps({'pid': os.getpid(), 'time': time.time()}))
        pending_created = True
    except OSError:
        pass

    deadline = time.monotonic() + max(0.1, timeout)
    lease = None
    try:
        while True:
            try:
                lease = Lease(path, exclusive=True)
                break
            except MaintenanceError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

        token = secrets.token_hex(32)
        local_state = _LOCAL_TOKEN.set(token)
        try:
            lease.file.seek(0)
            lease.file.truncate()
            json.dump({'token': token, 'pid': os.getpid()}, lease.file)
            lease.file.flush()
            os.fsync(lease.file.fileno())
            yield token
        finally:
            try:
                if lease.file:
                    lease.file.seek(0)
                    lease.file.truncate()
                    lease.file.flush()
            finally:
                _LOCAL_TOKEN.reset(local_state)
                lease.close()
    finally:
        if pending_created:
            try:
                pending.unlink(missing_ok=True)
            except OSError:
                pass
    # Keep the inode: deleting/recreating the lock file breaks exclusion.


class ManagedConnection(sqlite3.Connection):
    def __init__(self, database, *args, **kwargs):
        self._lease = Lease(_path(database))
        try:
            super().__init__(database, *args, **kwargs)
        except Exception:
            self._lease.close()
            raise

    def close(self):
        try:
            super().close()
        finally:
            if getattr(self, '_lease', None):
                self._lease.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def connect(database, *args, **kwargs):
    kwargs['factory'] = ManagedConnection
    return sqlite3.connect(database, *args, **kwargs)


def connect_readonly(database, *args, **kwargs):
    """Open a read-only SQLite connection while holding the same shared DB lease."""
    path = Path(database).expanduser().resolve()
    kwargs['uri'] = True
    kwargs.setdefault('timeout', 10)
    return connect(path.as_uri() + '?mode=ro', *args, **kwargs)
