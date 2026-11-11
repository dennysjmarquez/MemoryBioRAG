"""Advisory file locks shared by the detached maintenance daemon and MCP."""
from __future__ import annotations

import errno
import os


class FileLock:
    """Small nonblocking-capable advisory lock for Unix and Windows.

    Lock files are deliberately retained after release: unlinking a locked path
    can let another process lock a different inode and run concurrently.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = os.fspath(path)
        self._file = None

    def acquire(self, blocking: bool = True) -> bool:
        if self._file is not None:
            return True
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                try:
                    msvcrt.locking(handle.fileno(), mode, 1)
                except OSError as exc:
                    if exc.errno in (errno.EACCES, errno.EDEADLK, errno.EAGAIN):
                        handle.close()
                        return False
                    raise
            else:
                import fcntl

                flags = fcntl.LOCK_EX
                if not blocking:
                    flags |= fcntl.LOCK_NB
                try:
                    fcntl.flock(handle.fileno(), flags)
                except BlockingIOError:
                    handle.close()
                    return False
            self._file = handle
            return True
        except BaseException:
            if not handle.closed:
                handle.close()
            raise

    def release(self) -> None:
        handle = self._file
        if handle is None:
            return
        self._file = None
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self):
        if not self.acquire(blocking=True):
            raise OSError(f"No se pudo adquirir el lock {self.path!r}")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()


def is_file_lock_held(path: str | os.PathLike[str]) -> bool:
    """Comprueba si otro descriptor/proceso mantiene el advisory lock."""
    value = os.fspath(path)
    if not os.path.exists(value):
        return False
    probe = FileLock(value)
    try:
        acquired = probe.acquire(blocking=False)
    except PermissionError:
        # No poder probar el lock no autoriza a iniciar un duplicado.
        return True
    if not acquired:
        return True
    probe.release()
    return False
