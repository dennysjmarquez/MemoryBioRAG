"""Configuración, versión y errores de la capa SQLite.

Qué problema resuelve: había un solo archivo de 1.091 líneas que mezclaba
cinco responsabilidades distintas (Constitución, Pilar 9: "nada monolítico").
Este módulo guarda lo que todos los demás necesitan y nadie más produce:
las constantes, el interruptor de la capa, la versión del motor enlazado y
los tres errores propios.

Por qué está aquí y no en otro sitio: no importa a ningún otro módulo del
paquete salvo `logger` y lo mínimo, así que puede ser la base del paquete.

Quién lo usa: `pair_guard`, `journal`, `opening` y, desde `core.sqlite_runtime`,
los consumidores del motor.

Medida con la que se aprobó: la división no cambia comportamiento; las 55
pruebas de `test_sqlite_generation.py` y `test_sqlite_runtime.py` siguen
verdes antes y después, y `core.sqlite_runtime` conserva la misma API pública.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("BioRAG.SQLiteRuntime")

logger = logging.getLogger("BioRAG.SQLiteRuntime")

_FIRST_WAL_RELEASE = (3, 7, 0)

_DEFAULT_BUSY_TIMEOUT_MS = 30_000

_GUARD_ENV = "BIORAG_SQLITE_GUARD"

_FORCE_OPEN_ENV = "BIORAG_SQLITE_FORCE_OPEN"

def guard_enabled() -> bool:
    """¿Está activa la capa de protección del par SQLite?"""
    return (os.environ.get(_GUARD_ENV, "1") or "1").strip().lower() not in {
        "0", "false", "no", "off",
    }

def force_open_authorized() -> bool:
    """¿El operador autorizó explícitamente abrir un par no verificado?"""
    return (os.environ.get(_FORCE_OPEN_ENV, "0") or "0").strip().lower() in {
        "1", "true", "yes", "on",
    }

_MAX_BUSY_TIMEOUT_MS = 300_000

class SQLiteSidecarConflictError(sqlite3.OperationalError):
    """No se puede probar que el `-wal` presente pertenezca a este archivo.

    Se lanza ANTES de abrir el par real, porque abrir con un diario ajeno
    presente puede hacer que SQLite lo aplique y la base termine con datos de
    otra versión. Nunca se mueve, renombra ni borra nada: la recuperación es
    una decisión explícita del operador.

    Para continuar hay una autorización explícita:
    `BIORAG_SQLITE_FORCE_OPEN=1` (se registra en el log y reanota el estado).
    """

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
    """Versión efectiva del motor enlazado al módulo sqlite3 de este proceso.

    Se consulta siempre en `core.sqlite.config` (no se importa por valor en los
    demás módulos) para que una prueba pueda simular otra versión parcheando
    un solo nombre. Sin esto, cada módulo tendría su propia copia y la simulación
    surtiría efecto en unos sitios y no en otros.
    """
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
    """True si la ruta es una base en memoria (`:memory:`) o una URI `file:`."""
    value = str(database)
    return value == ":memory:" or (
        value.startswith("file:") and "mode=memory" in value.lower()
    )

def _database_existed_before_open(database: str | Path) -> bool:
    """True si el archivo principal ya existía antes de abrir. Ninguna base nueva necesita comprobación de pertenencia: no hay diario que aplicar."""
    value = str(database)
    if _is_memory_database(database):
        return False
    # URI SQLite no se interpreta como ruta de filesystem aquí. Tratarlo como
    # existente evita cambiar journal en una URI cuyo archivo no podemos resolver.
    if value.startswith("file:"):
        return True
    return Path(os.path.expanduser(value)).exists()

def _raw_execute(conn: sqlite3.Connection, sql: str, parameters: Any = ()):
    """Run an internal runtime statement without the user-facing cursor tracking.

    Runtime probes and journal-policy changes are not user commits, so they must
    not publish a commit epoch. Bypassing the tracked cursor also avoids keeping
    an untracked cursor alive in a traceback when a journal transition fails,
    which used to defer sqlite3_close and leave a WAL read lock behind.

    The class is looked up at call time on purpose: the tracked connection is
    defined further down this module, and a direct reference here would be an
    UnboundLocalError raised during ``configure_writer`` (inside the very
    ``except`` handler that builds the actionable journal error) instead of the
    real SQLite failure.
    """
    tracked = globals().get("_TrackedSQLiteConnection")
    if tracked is not None and isinstance(conn, tracked):
        return sqlite3.Connection.execute(conn, sql, parameters)
    return conn.execute(sql, parameters)

def _journal_mode(conn: sqlite3.Connection) -> str:
    """Modo de diario efectivo de una conexión ya abierta (`delete`, `wal`, `off`...). Solo para diagnóstico: no cambia nada."""
    row = _raw_execute(conn, "PRAGMA journal_mode").fetchone()
    if not row or not row[0]:
        raise sqlite3.OperationalError("SQLite no devolvió el journal mode efectivo")
    return str(row[0]).lower()

def _sqlite_source_id(conn: sqlite3.Connection) -> str:
    """Identificador de compilación de SQLite. Permite saber si dos procesos corren exactamente el mismo motor."""
    try:
        row = conn.execute("SELECT sqlite_source_id()").fetchone()
        return str(row[0]) if row else "desconocido"
    except sqlite3.Error:
        return "no disponible"
