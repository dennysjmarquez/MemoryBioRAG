"""Apertura y política de journal para conexiones escritoras BioRAG.

La versión se consulta en el proceso que crea cada conexión: la versión del
SQLite del shell, otro Python o un daemon distinto no es intercambiable.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.paths import resolve_db_path

logger = logging.getLogger("BioRAG.SQLiteRuntime")

# Releases con corrección publicada por SQLite para el WAL-reset bug.
_FIRST_WAL_RELEASE = (3, 7, 0)
_DEFAULT_BUSY_TIMEOUT_MS = 30_000
_MAX_BUSY_TIMEOUT_MS = 300_000


class UnsafeSQLiteJournalModeError(sqlite3.OperationalError):
    """La conexión no puede abrirse para escribir en un journal seguro."""


class SQLiteDatabaseIdentityChangedError(sqlite3.OperationalError):
    """El path canónico apunta a un archivo SQLite distinto del que abrió el motor."""


def database_file_identity(database: str | os.PathLike[str]) -> tuple[int, int] | None:
    """Devuelve `(device, inode)` del archivo, sin inspeccionar su contenido.

    Los identificadores no aplican a bases `:memory:` ni a URI SQLite. Para un
    path de archivo inexistente propaga `OSError`: el caller decide si eso
    representa una generación desaparecida.
    """
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return None
    st = os.stat(value)
    return int(st.st_dev), int(st.st_ino)


def _effective_sqlite_version() -> tuple[int, int, int]:
    """Versión efectiva del motor enlazado al módulo sqlite3 de este proceso."""
    return tuple(sqlite3.sqlite_version_info[:3])


def is_wal_reset_vulnerable(version: tuple[int, ...] | None = None) -> bool:
    """Indica si la versión puede sufrir el WAL-reset bug documentado por SQLite.

    Se aplican los releases fijos publicados (3.51.3, 3.50.7 y 3.44.6), no
    inferencias basadas solo en el número de Python ni en una versión reportada
    por otro proceso.
    """
    version = tuple(version or _effective_sqlite_version())
    if version < _FIRST_WAL_RELEASE:
        return False  # este motor aún no tenía WAL
    if version >= (3, 51, 3):
        return False
    if (3, 50, 7) <= version < (3, 51, 0):
        return False
    if (3, 44, 6) <= version < (3, 45, 0):
        return False
    return True


def _is_memory_database(database: str | Path) -> bool:
    value = str(database)
    return value == ":memory:" or (
        value.startswith("file:") and "mode=memory" in value.lower()
    )


def _database_existed_before_open(database: str | Path) -> bool:
    value = str(database)
    if _is_memory_database(database):
        return False
    # URI SQLite no se interpreta como ruta de filesystem aquí. Tratarlo como
    # existente evita cambiar journal en una URI cuyo archivo no podemos resolver.
    if value.startswith("file:"):
        return True
    return Path(os.path.expanduser(value)).exists()


def _journal_mode(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA journal_mode").fetchone()
    if not row or not row[0]:
        raise sqlite3.OperationalError("SQLite no devolvió el journal mode efectivo")
    return str(row[0]).lower()


def _sqlite_source_id(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("SELECT sqlite_source_id()").fetchone()
        return str(row[0]) if row else "desconocido"
    except sqlite3.Error:
        return "no disponible"


def _database_route_id(database: str | Path) -> str:
    """Huella estable de la ruta efectiva; evita revelar rutas en logs normales."""
    try:
        value = resolve_db_path(database)
    except (TypeError, ValueError, OSError):
        value = os.fsdecode(os.fspath(database))
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


_COMMIT_EPOCH_LOCK = threading.Lock()
_COMMIT_EPOCHS: dict[str, int] = {}


def database_commit_epoch(database: str | Path) -> int:
    key = _database_route_id(database)
    with _COMMIT_EPOCH_LOCK:
        return _COMMIT_EPOCHS.get(key, 0)


def note_database_commit(database: str | Path) -> int:
    key = _database_route_id(database)
    with _COMMIT_EPOCH_LOCK:
        epoch = _COMMIT_EPOCHS.get(key, 0) + 1
        _COMMIT_EPOCHS[key] = epoch
        return epoch


class _TrackedSQLiteConnection(sqlite3.Connection):
    """Tags commits by connections opened through the shared writer factory."""

    def __init__(self, database, *args, **kwargs):
        super().__init__(database, *args, **kwargs)
        self._biorag_database = database

    def commit(self):
        had_transaction = self.in_transaction
        result = super().commit()
        if had_transaction:
            note_database_commit(self._biorag_database)
        return result

    def __exit__(self, exc_type, exc_value, traceback):
        had_transaction = self.in_transaction
        result = super().__exit__(exc_type, exc_value, traceback)
        if had_transaction and exc_type is None:
            note_database_commit(self._biorag_database)
        return result


def connection_diagnostics(
    conn: sqlite3.Connection,
    database: str | Path,
    *,
    role: str,
    consumer: str,
) -> dict[str, Any]:
    """Devuelve y registra runtime efectivo sin incluir ruta ni datos de la DB."""
    row = conn.execute("PRAGMA busy_timeout").fetchone()
    busy_timeout_ms = int(row[0]) if row else -1
    details = {
        "consumer": str(consumer),
        "role": str(role),
        "runtime": ".".join(map(str, _effective_sqlite_version())),
        "source_id": _sqlite_source_id(conn),
        "journal_mode": _journal_mode(conn),
        "busy_timeout_ms": busy_timeout_ms,
        "route_id": _database_route_id(database),
    }
    logger.debug(
        "SQLite connection: consumer=%s role=%s runtime=%s source_id=%s "
        "journal=%s busy_timeout_ms=%d route_id=%s",
        details["consumer"], details["role"], details["runtime"],
        details["source_id"], details["journal_mode"], busy_timeout_ms,
        details["route_id"],
    )
    return details


@dataclass(frozen=True)
class SQLiteWriterRuntime:
    version: tuple[int, int, int]
    source_id: str
    journal_mode: str
    wal_reset_vulnerable: bool
    transition_applied: bool


def configure_writer(
    conn: sqlite3.Connection,
    database: str | Path,
    *,
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    database_existed: bool = True,
    allow_existing_journal_transition: bool = False,
) -> SQLiteWriterRuntime:
    """Configura una conexión escritora sin cambiar journal existente en silencio.

    Bases preexistentes conservan el journal actual. Un runtime vulnerable que
    encuentre WAL falla cerrado por defecto; la migración de una base existente
    requiere opt-in explícito y SQLite debe conceder el lock exclusivo requerido.
    Una base nueva puede iniciar en WAL si el runtime tiene la corrección.
    """
    if not isinstance(busy_timeout_ms, int) or not 0 <= busy_timeout_ms <= _MAX_BUSY_TIMEOUT_MS:
        raise ValueError(
            f"busy_timeout_ms debe ser un entero entre 0 y {_MAX_BUSY_TIMEOUT_MS}"
        )

    version = _effective_sqlite_version()
    vulnerable = is_wal_reset_vulnerable(version)
    source_id = _sqlite_source_id(conn)
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    current = _journal_mode(conn)

    # Una base :memory: usa el journal interno `memory`, nunca WAL/DELETE.
    if _is_memory_database(database) or current == "memory":
        return SQLiteWriterRuntime(version, source_id, current, vulnerable, False)

    if vulnerable and current == "wal" and database_existed and not allow_existing_journal_transition:
        raise UnsafeSQLiteJournalModeError(
            "BioRAG rechazó la escritura sin modificar el journal: este proceso "
            f"usa SQLite {'.'.join(map(str, version))}, vulnerable al WAL-reset bug, "
            "y la base existente está en journal_mode='wal'. No se intentó cambiar "
            "ni borrar la base o sus sidecars. Cierre de forma ordenada los "
            "consumidores y autorice/ejecute una migración explícita del journal, "
            "o use en todos los escritores un runtime corregido (3.51.3+, 3.50.7 o "
            "3.44.6 con el arreglo aplicado)."
        )

    # Solo se elige un journal al crear un archivo nuevo, o ante una migración
    # explícitamente autorizada. En una base existente normal se respeta su modo.
    may_transition = not database_existed or allow_existing_journal_transition
    target = "delete" if vulnerable else "wal"
    transition_applied = False
    actual = current
    if may_transition and current != target:
        conn.execute("PRAGMA busy_timeout=0")
        transition_error: sqlite3.Error | None = None
        try:
            row = conn.execute(f"PRAGMA journal_mode={target}").fetchone()
            actual = str(row[0]).lower() if row and row[0] else _journal_mode(conn)
            transition_applied = actual == target
        except sqlite3.OperationalError as exc:
            transition_error = exc
            actual = _journal_mode(conn)

        if vulnerable and actual != "delete":
            conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            reason = f"; error SQLite: {transition_error}" if transition_error else ""
            raise UnsafeSQLiteJournalModeError(
                "BioRAG rechazó la escritura: no se pudo confirmar el cambio "
                f"exclusivo de journal a DELETE (modo efectivo: {actual!r}{reason}). "
                "Cierre los consumidores que mantienen la base abierta y reintente "
                "solo con autorización explícita. No se borraron ni repararon la "
                "base o sus sidecars."
            ) from transition_error

        if not vulnerable and actual not in {"wal", "delete", "truncate", "persist"}:
            conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            raise sqlite3.OperationalError(
                f"No se pudo establecer un journal compatible; journal_mode={actual!r}"
            ) from transition_error

        if not transition_applied:
            logger.info(
                "SQLite %s: no se cambió journal %s→%s (modo efectivo %s); "
                "se conserva el modo existente",
                ".".join(map(str, version)), current, target, actual,
            )

    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    actual = _journal_mode(conn)
    if vulnerable and actual == "wal":
        raise UnsafeSQLiteJournalModeError(
            "BioRAG rechazó la escritura porque el runtime SQLite vulnerable "
            "no puede escribir sobre una base WAL existente sin migración autorizada."
        )

    return SQLiteWriterRuntime(version, source_id, actual, vulnerable, transition_applied)


def open_writer(
    database: str | Path,
    *,
    timeout: float = _DEFAULT_BUSY_TIMEOUT_MS / 1000,
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    allow_existing_journal_transition: bool = False,
    consumer: str = "unspecified",
    **connect_kwargs: Any,
) -> sqlite3.Connection:
    """Abre una conexión BioRAG escritora con política version-aware.

    La transición de journal de una DB existente está desactivada por defecto y
    requiere `allow_existing_journal_transition=True` explícito por el operador.
    """
    database_existed = _database_existed_before_open(database)
    if "factory" in connect_kwargs:
        raise TypeError("open_writer administra la subclase de conexión")
    conn = sqlite3.connect(
        database, timeout=timeout, factory=_TrackedSQLiteConnection,
        **connect_kwargs,
    )
    try:
        policy = configure_writer(
            conn,
            database,
            busy_timeout_ms=busy_timeout_ms,
            database_existed=database_existed,
            allow_existing_journal_transition=allow_existing_journal_transition,
        )
    except BaseException:
        conn.close()
        raise

    logger.debug(
        "SQLite connection: consumer=%s role=writer runtime=%s source_id=%s "
        "journal=%s busy_timeout_ms=%d wal_reset_vulnerable=%s "
        "transition_applied=%s route_id=%s",
        consumer, ".".join(map(str, policy.version)), policy.source_id,
        policy.journal_mode, busy_timeout_ms, policy.wal_reset_vulnerable,
        policy.transition_applied, _database_route_id(database),
    )
    return conn


def open_reader(
    database: str | Path,
    *,
    timeout: float = _DEFAULT_BUSY_TIMEOUT_MS / 1000,
    consumer: str = "unspecified",
    **connect_kwargs: Any,
) -> sqlite3.Connection:
    """Abre una conexión read-only por path canónico y registra el runtime efectivo.

    Se rechazan SQLite URI y `:memory:` intencionalmente: esta interfaz recibe
    rutas de archivos para evitar combinaciones de URI/query no validadas.
    """
    if not isinstance(timeout, (int, float)) or not 0 <= timeout <= _MAX_BUSY_TIMEOUT_MS / 1000:
        raise ValueError(
            f"timeout debe estar entre 0 y {_MAX_BUSY_TIMEOUT_MS / 1000} segundos"
        )
    canonical = resolve_db_path(database)
    if canonical == ":memory:" or canonical.startswith("file:"):
        raise ValueError("open_reader requiere una ruta de archivo, no memory/SQLite URI")
    if "uri" in connect_kwargs:
        raise TypeError("open_reader administra el parámetro uri internamente")

    timeout_ms = int(round(timeout * 1000))
    uri = Path(canonical).as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, **connect_kwargs)
    try:
        conn.execute(f"PRAGMA busy_timeout={timeout_ms}")
        conn.execute("PRAGMA query_only=ON")
        connection_diagnostics(
            conn, canonical, role="read-only", consumer=consumer
        )
    except BaseException:
        conn.close()
        raise
    return conn
