"""Cross-process SQLite leases for BioRAG clients and exclusive maintenance.

Every managed SQLite connection holds a shared OS lock. Updates/migrations require
an exclusive lock; the kernel releases a process's lock on exit/crash. This does not
lock out programs that bypass BioRAG and open SQLite directly.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

TOKEN_ENV = 'BIORAG_MAINTENANCE_TOKEN'
_LOCAL_TOKEN = ContextVar('biorag_maintenance_token', default=None)
_DIAG_LOCK = threading.RLock()
_DIAG_LEASES: dict[str, dict] = {}


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


def _leases_dir(database):
    return database.with_name(database.name + '.leases')


def _client_role():
    try:
        from core.process_inspection import _classify
        return _classify(sys.argv, os.getcwd()) or 'client'
    except Exception:
        return 'client'


def _acquire_diagnostic_lease(database):
    """Register an OS-locked diagnostic metadata file in <db>.leases/<pid>.json."""
    key = str(database)
    with _DIAG_LOCK:
        entry = _DIAG_LEASES.get(key)
        if entry is not None:
            entry['count'] += 1
            return
        leases_dir = _leases_dir(database)
        lease_path = leases_dir / f'{os.getpid()}.json'
        try:
            leases_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(lease_path, os.O_RDWR | os.O_CREAT, 0o600)
            lease_file = os.fdopen(fd, 'r+')
        except OSError:
            return
        overlapped = None
        try:
            if os.name == 'posix':
                import fcntl
                fcntl.flock(lease_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            elif os.name == 'nt':
                overlapped = _windows_lock(lease_file, exclusive=True)
            payload = {
                'pid': os.getpid(),
                'command': Path(sys.argv[0]).name if sys.argv and sys.argv[0] else 'python',
                'role': _client_role(),
                'started_at': datetime.now(timezone.utc).isoformat(),
            }
            lease_file.seek(0)
            lease_file.truncate()
            json.dump(payload, lease_file, ensure_ascii=False)
            lease_file.flush()
            _DIAG_LEASES[key] = {
                'count': 1,
                'file': lease_file,
                'overlapped': overlapped,
                'path': lease_path,
            }
        except (OSError, BlockingIOError):
            lease_file.close()


def _release_diagnostic_lease(database):
    """Release diagnostic lease for this process when its last managed connection closes."""
    key = str(database)
    with _DIAG_LOCK:
        entry = _DIAG_LEASES.get(key)
        if entry is None:
            return
        entry['count'] -= 1
        if entry['count'] > 0:
            return
        _DIAG_LEASES.pop(key, None)
        try:
            _unlock(entry['file'], entry['overlapped'])
        except OSError:
            pass
        finally:
            try:
                entry['file'].close()
            except OSError:
                pass
        try:
            entry['path'].unlink()
        except OSError:
            pass


def active_lease_holders(database):
    """Return metadata for live processes currently holding a diagnostic OS lease."""
    path = _path(database)
    if path is None:
        return []
    leases_dir = _leases_dir(path)
    if not leases_dir.is_dir():
        return []
    holders = []
    for entry in sorted(leases_dir.glob('*.json')):
        if entry.is_symlink():
            continue
        if not _shared_lock_conflicts(entry):
            # Process exited or was killed; OS released the lock -> clean up stale file.
            try:
                entry.unlink()
            except OSError:
                pass
            continue
        fallback_pid = int(entry.stem) if entry.stem.isdigit() else None
        meta = {'pid': fallback_pid, 'command': 'unknown', 'role': 'client'}
        try:
            raw = entry.read_text(encoding='utf-8').strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    meta.update(parsed)
        except (OSError, ValueError, TypeError):
            pass
        holders.append(meta)
    holders.sort(key=lambda item: (item.get('pid') is None, item.get('pid') or 0))
    return holders


def format_lease_holders(holders):
    """Format active lease holders into a concise human-readable string."""
    parts = []
    for h in holders:
        pid = h.get('pid', '?')
        role = h.get('role', 'client')
        cmd = h.get('command', 'unknown')
        parts.append(f'PID {pid} ({role}: {cmd})')
    return ', '.join(parts)


def _inspect_fallback_holders(database):
    """Fallback to psutil process inspection for legacy holders without .leases/."""
    try:
        from core.process_inspection import inspect_database_processes
        inv = inspect_database_processes(database, exclude_pids={os.getpid()})
        return [
            {
                'pid': item.get('pid'),
                'role': item.get('kind', 'unknown'),
                'command': item.get('name', 'unknown'),
            }
            for item in inv.get('holders', [])
        ]
    except Exception:
        return []


def is_maintenance_pending(database):
    path = _path(database)
    if path is None:
        return False
    return _shared_lock_conflicts(_pending_path(path))


def _try_acquire_pending_gate(database):
    """Acquire an exclusive OS lock on the pending gate file, preserving its inode.

    Returns (file, overlapped) if acquired, or (None, None) if another process
    already holds the pending gate. Never unlinks the file.
    """
    pending = _pending_path(database)
    try:
        pending.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(pending, os.O_RDWR | os.O_CREAT, 0o600)
        gate_file = os.fdopen(fd, 'r+')
    except OSError:
        return None, None
    overlapped = None
    try:
        if os.name == 'posix':
            import fcntl
            fcntl.flock(gate_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        elif os.name == 'nt':
            overlapped = _windows_lock(gate_file, exclusive=True)
        return gate_file, overlapped
    except (OSError, BlockingIOError):
        gate_file.close()
        return None, None
    except Exception:
        gate_file.close()
        raise


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
        self._diag_db = None
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
        if not exclusive:
            _acquire_diagnostic_lease(database)
            self._diag_db = database

    def close(self):
        if self.file is not None:
            try:
                _unlock(self.file, self._overlapped)
            finally:
                self.file.close()
                self.file = None
                self._overlapped = None
        if self._diag_db is not None:
            try:
                _release_diagnostic_lease(self._diag_db)
            finally:
                self._diag_db = None


@contextmanager
def maintenance(database, timeout=30, progress_interval=5.0):
    """Acquire exclusive maintenance lease, waiting up to ``timeout`` seconds.

    Note: older MCP server versions that do not check ``is_maintenance_pending``
    ignore the pending gate and continue holding their shared lease until idle
    timeout or shutdown.
    """
    path = _path(database)
    if path is None:
        yield None
        return
    if _delegated(path):
        yield _LOCAL_TOKEN.get() or os.environ[TOKEN_ENV]
        return

    # Signal to active readers/MCP that maintenance is pending (OS-locked gate, inode preserved)
    gate_file, gate_overlapped = _try_acquire_pending_gate(path)

    start = time.monotonic()
    deadline = start + max(0.0, timeout)
    last_progress = start
    lease = None
    try:
        while True:
            try:
                lease = Lease(path, exclusive=True)
                break
            except MaintenanceError as exc:
                now = time.monotonic()
                if now >= deadline:
                    holders = active_lease_holders(path)
                    seen_pids = {h.get('pid') for h in holders if h.get('pid') is not None}
                    for fb in _inspect_fallback_holders(path):
                        if fb.get('pid') not in seen_pids:
                            holders.append(fb)
                    if holders:
                        summary = format_lease_holders(holders)
                        raise MaintenanceError(f'{exc}. Active clients: {summary}') from exc
                    raise
                if progress_interval > 0 and (now - last_progress) >= progress_interval:
                    elapsed = int(round(now - start))
                    print(
                        f"Waiting for BioRAG clients to close... {elapsed} s",
                        file=sys.stderr,
                        flush=True,
                    )
                    last_progress = now
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
        if gate_file is not None:
            try:
                _unlock(gate_file, gate_overlapped)
            finally:
                gate_file.close()
    # Keep the inode: deleting/recreating the lock or gate file breaks exclusion.


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
