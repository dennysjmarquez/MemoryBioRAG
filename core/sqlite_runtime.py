"""Apertura y política de journal para conexiones escritoras BioRAG.

**Este archivo es una fachada.** La implementación vive en `core/sqlite/`,
dividida por responsabilidad (Constitución, Pilar 9). Aquí solo se reexporta,
para que ningún consumidor tenga que cambiar sus imports.

Qué problema resuelve: el motor necesita un único punto por el que se abran
conexiones, y ese punto se llama `open_writer`. Mantener aquí la API pública
permite dividir la implementación sin tocar los siete archivos que la usan.

Por qué está aquí y no en otro sitio: un archivo de fachada de 60 líneas es
barato y deja la puerta única bien visible.

Quién lo usa: `core/memory_store.py`, `core/adn_conceptual.py`,
`core/dmn_engine.py`, `core/feedback_implicito.py`,
`core/neocortex_teleologico.py`, `core/ppmi_hybrid_search.py` y
`dashboard-neuro-visor/backend/server.py`.

**Si añades una función a `core/sqlite/`, reexpórtala aquí solo si es pública.**
Lo que empieza por `_` es interno y los consumidores no deben usarlo.

Medida con la que se aprobó: `tests/test_sqlite_generation.py` (30) y
`tests/test_sqlite_runtime.py` (25) verdes antes y después de la división, más
la suite completa sin cambios (729 passed).
"""
from __future__ import annotations

# --- config: constantes, interruptores, versión y errores -------------------
from core.sqlite.constants import (
    SQLiteDatabaseIdentityChangedError,
    SQLiteLfsPointerError,
    SQLiteSidecarConflictError,
    UnsafeSQLiteJournalModeError,
    _DEFAULT_BUSY_TIMEOUT_MS,
    _effective_sqlite_version,
    _FORCE_OPEN_ENV,
    _GUARD_ENV,
    database_file_identity,
    force_open_authorized,
    guard_enabled,
    is_wal_reset_vulnerable,
    logger,
)

# --- epoch: época de commit compartida entre procesos ----------------------
from core.sqlite.epoch import (
    _wal_content_signature,  # usado por core/memory_store.py: firma del contenido del WAL
    database_commit_epoch,
    database_commit_state,
    database_read_window,
    note_database_commit,
)

# --- pair_guard: ¿el -wal pertenece a este .db? ----------------------------
from core.sqlite.pair_guard import (
    _journal_from_header,
    _pair_can_be_opened,
    _recorded_pair_state,
    _save_conflict_forensics,
    _wal_header_salt,
    record_pair_state,
)

# --- tracking: conexión que avisa cuándo escribe ---------------------------
from core.sqlite.tracking import (
    _TrackedSQLiteConnection,
    _TrackedSQLiteCursor,
)

# --- journal: política de modo de diario y diagnóstico ---------------------
from core.sqlite.journal import (
    SQLiteWriterRuntime,
    configure_writer,
    connection_diagnostics,
)

# --- opening: las dos puertas ---------------------------------------------
from core.sqlite.opening import open_reader, open_writer


__all__ = [
    # apertura
    "open_writer",
    "open_reader",
    # interruptores
    "guard_enabled",
    "force_open_authorized",
    # identidad y diagnóstico
    "database_file_identity",
    "database_commit_state",
    "database_commit_epoch",
    "database_read_window",
    "note_database_commit",
    "connection_diagnostics",
    "is_wal_reset_vulnerable",
    "configure_writer",
    "SQLiteWriterRuntime",
    # errores
    "SQLiteLfsPointerError",
    "SQLiteSidecarConflictError",
    "SQLiteDatabaseIdentityChangedError",
    "UnsafeSQLiteJournalModeError",
]
