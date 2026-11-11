"""Política de journal y diagnóstico de la conexión.

Qué problema resuelve: SQLite 3.7–3.51.2 tiene el WAL-reset bug, que corrompe
la base si dos procesos tocan el WAL sin coordinación. Este módulo decide en
qué modo puede abrirse la conexión y aplica los PRAGMA de seguridad, y describe
el estado real del motor en un diagnóstico legible.

Por qué está aquí y no en otro sitio: es la política del *modo de diario*, una
decisión distinta de la de pertenencia del par (`pair_guard`) y de la de
apertura (`opening`).

Quién lo usa: `opening.open_writer` y `opening.open_reader`.

Medida con la que se aprobó: `UnsafeSQLiteJournalModeError` se dispara en las
pruebas de runtime con versión vulnerable simulada.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.sqlite import config as _cfg
from core.sqlite.config import (
    UnsafeSQLiteJournalModeError,
    _DEFAULT_BUSY_TIMEOUT_MS,
    _MAX_BUSY_TIMEOUT_MS,
    _is_memory_database,
    _journal_mode,
    _raw_execute,
    _sqlite_source_id,
    logger,
)
from core.sqlite.epoch import _database_route_id


def _effective_sqlite_version() -> tuple[int, int, int]:
    """Reenvío: la versión se lee donde se define, no se copia al importar."""
    return _cfg._effective_sqlite_version()


def is_wal_reset_vulnerable(version=None) -> bool:
    """Reenvío: misma razón que `_effective_sqlite_version`."""
    return _cfg.is_wal_reset_vulnerable(version)

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
    """Foto de lo que se aplicó al abrir: versión del motor, modo de diario efectivo y si se hizo la transición. Se registra en el log."""
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
    _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
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
        _raw_execute(conn, "PRAGMA busy_timeout=0")
        transition_error: sqlite3.Error | None = None
        try:
            row = _raw_execute(conn, f"PRAGMA journal_mode={target}").fetchone()
            actual = str(row[0]).lower() if row and row[0] else _journal_mode(conn)
            transition_applied = actual == target
        except sqlite3.OperationalError as exc:
            transition_error = exc
            actual = _journal_mode(conn)

        if vulnerable and actual != "delete":
            _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
            reason = f"; error SQLite: {transition_error}" if transition_error else ""
            raise UnsafeSQLiteJournalModeError(
                "BioRAG rechazó la escritura: no se pudo confirmar el cambio "
                f"exclusivo de journal a DELETE (modo efectivo: {actual!r}{reason}). "
                "Cierre los consumidores que mantienen la base abierta y reintente "
                "solo con autorización explícita. No se borraron ni repararon la "
                "base o sus sidecars."
            ) from transition_error

        if not vulnerable and actual not in {"wal", "delete", "truncate", "persist"}:
            _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
            raise sqlite3.OperationalError(
                f"No se pudo establecer un journal compatible; journal_mode={actual!r}"
            ) from transition_error

        if not transition_applied:
            logger.info(
                "SQLite %s: no se cambió journal %s→%s (modo efectivo %s); "
                "se conserva el modo existente",
                ".".join(map(str, version)), current, target, actual,
            )

    _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
    actual = _journal_mode(conn)
    if vulnerable and actual == "wal":
        raise UnsafeSQLiteJournalModeError(
            "BioRAG rechazó la escritura porque el runtime SQLite vulnerable "
            "no puede escribir sobre una base WAL existente sin migración autorizada."
        )

    return SQLiteWriterRuntime(version, source_id, actual, vulnerable, transition_applied)
