"""Acceso SQLite coordinado con mantenimiento local.

Los clientes mantienen lease compartido; update/migrate requiere exclusivo.
Es cooperativo: NO bloquea programas externos que usen sqlite3 directamente.
POSIX flock probado; Windows rechaza mantenimiento hasta tener backend probado.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import unquote, urlsplit

TOKEN_ENV = 'BIORAG_MAINTENANCE_TOKEN'
_LOCAL_TOKEN = ContextVar('biorag_maintenance_token', default=None)


class MaintenanceError(RuntimeError):
    pass


def _path(database):
    value=str(database)
    if value==':memory:' or (value.startswith('file:') and ('mode=memory' in value or urlsplit(value).path==':memory:')):return None
    if value.startswith('file:'):value=unquote(urlsplit(value).path)
    return Path(value).expanduser().resolve()


def _lock_path(database):
    return database.with_name(database.name+'.maintenance.lock')


def _delegated(database):
    token=_LOCAL_TOKEN.get() or os.environ.get(TOKEN_ENV)
    if not token:return False
    try:
        data=json.loads(_lock_path(database).read_text())
        if not secrets.compare_digest(token,data.get('token','')):return False
        # Un token residual tras muerte del dueño no autoriza saltar el lease.
        if os.name=='posix':
            import fcntl
            with open(_lock_path(database),'r') as probe:
                try:fcntl.flock(probe,fcntl.LOCK_SH|fcntl.LOCK_NB)
                except BlockingIOError:return True
                fcntl.flock(probe,fcntl.LOCK_UN)
            return False
        return False
    except (OSError,ValueError,TypeError,AttributeError):return False


class Lease:
    def __init__(self, database, exclusive=False):
        self.file=None
        if database is None or _delegated(database):return
        if os.name!='posix':
            if exclusive:raise MaintenanceError('MAINTENANCE_PLATFORM_UNSUPPORTED: se requiere backend de bloqueo probado')
            return
        import fcntl
        database.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(_lock_path(database),os.O_RDWR|os.O_CREAT,0o600)
        self.file=os.fdopen(fd,'r+')
        try:fcntl.flock(self.file, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close();self.file=None
            raise MaintenanceError('DATABASE_IN_USE_OR_MAINTENANCE: cerrar clientes y servicios, luego repetir') from exc

    def close(self):
        if self.file is not None:
            self.file.close();self.file=None


@contextmanager
def maintenance(database):
    path=_path(database)
    if path is None:
        yield None;return
    if _delegated(path):
        yield _LOCAL_TOKEN.get() or os.environ[TOKEN_ENV];return
    lease=Lease(path,exclusive=True)
    token=secrets.token_hex(32)
    local_state=_LOCAL_TOKEN.set(token)
    try:
        lease.file.seek(0);lease.file.truncate()
        json.dump({'token':token,'pid':os.getpid()},lease.file)
        lease.file.flush();os.fsync(lease.file.fileno())
        yield token
    finally:
        try:
            if lease.file:
                lease.file.seek(0);lease.file.truncate();lease.file.flush()
        finally:
            _LOCAL_TOKEN.reset(local_state)
            lease.close()
    # No borrar el archivo: cambiar de inode rompe exclusión con procesos en espera.


class ManagedConnection(sqlite3.Connection):
    def __init__(self, database, *args, **kwargs):
        self._lease=Lease(_path(database))
        try:super().__init__(database,*args,**kwargs)
        except Exception:
            self._lease.close();raise

    def close(self):
        try:super().close()
        finally:
            if getattr(self,'_lease',None):self._lease.close()

    def __del__(self):
        try:self.close()
        except Exception:pass


def connect(database, *args, **kwargs):
    kwargs['factory']=ManagedConnection
    return sqlite3.connect(database,*args,**kwargs)
