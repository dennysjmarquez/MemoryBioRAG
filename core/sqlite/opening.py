"""Las dos puertas del motor: `open_writer` y `open_reader`.

Qué problema resuelve: es el único punto por el que el motor abre conexiones.
Tenerlas juntas garantiza que ninguna ruta se salte las comprobaciones: la
pertenencia del par (`pair_guard`), la política de journal (`journal`) y la
anotación de estado tras abrir.

Por qué está aquí y no en otro sitio: es la fachada del paquete. Los
consumidores importan de aquí o de `core.sqlite_runtime`, nunca de los módulos
internos.

Quién lo usa: `core/memory_store.py`, `adn_conceptual`, `dmn_engine`,
`feedback_implicito`, `neocortex_teleologico`, `ppmi_hybrid_search` y el
dashboard.

Medida con la que se aprobó: los tres escenarios de la auditora y las 55
pruebas de la capa.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from core.paths import resolve_db_path
from core.sqlite import constants as _cfg
from core.sqlite import pair_guard as _pair_guard
from core.sqlite.constants import (
    SQLiteSidecarConflictError,
    _DEFAULT_BUSY_TIMEOUT_MS,
    _MAX_BUSY_TIMEOUT_MS,
    _database_existed_before_open,
    logger,
)
from core.sqlite.epoch import _database_route_id
from core.sqlite.journal import configure_writer, connection_diagnostics
from core.sqlite.tracking import _TrackedSQLiteConnection
from core.sqlite.pair_guard import (
    _has_nonempty_wal,
    _save_conflict_forensics,
)


def guard_enabled() -> bool:
    """Reenvío: el interruptor se lee donde se define."""
    return _cfg.guard_enabled()


def force_open_authorized() -> bool:
    """Reenvío: la autorización se lee donde se define."""
    return _cfg.force_open_authorized()


def _pair_can_be_opened(database) -> bool:
    """Reenvío: la decisión del par se toma donde se define.

    Se reenvía en vez de importar por valor para que la comprobación sea
    sustituible en pruebas sin duplicar la lógica.
    """
    return _pair_guard._pair_can_be_opened(database)


def record_pair_state(database) -> None:
    """Reenvío: la anotación del par se hace donde se define."""
    return _pair_guard.record_pair_state(database)

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

    # Comprobación del par ANTES de abrir: abrir con un `-wal` de otra
    # generación presente puede hacer que SQLite lo aplique sobre el archivo
    # bueno. Se decide con los archivos, sin abrirlos con SQLite.
    if guard_enabled() and database_existed and not _pair_can_be_opened(database):
        if force_open_authorized():
            forense = _save_conflict_forensics(database, motivo="apertura_forzada")
            logger.warning(
                "Apertura forzada con un -wal no verificado (%s); constancia en %s",
                consumer, forense,
            )
        else:
            forense = _save_conflict_forensics(database, motivo="par_no_verificado")
            raise SQLiteSidecarConflictError(
                "BioRAG no abrió la base porque hay un -wal que no se puede "
                "atribuir con certeza a este archivo principal (por ejemplo, "
                "tras cambiar de rama con la base versionada, tras una caída "
                "del proceso o si quedó un cliente antiguo abierto). Abrirla "
                "así podría aplicar datos de otra versión sobre los actuales. "
                "No se movió, renombró ni borró ningún archivo; hay una "
                f"constancia con los sha256 en {forense}. Para revisar y "
                "decidir: docs/sqlite_par_no_verificado.md. Para continuar "
                "bajo tu responsabilidad: BIORAG_SQLITE_FORCE_OPEN=1."
            )

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
    # Con el diario vacío el par es coherente por construcción: se anota.
    if guard_enabled() and not _has_nonempty_wal(database):
        record_pair_state(database)
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
