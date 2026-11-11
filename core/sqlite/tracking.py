"""Conexión y cursor instrumentados.

Qué problema resuelve: hay que saber cuándo una sentencia escribe, para
publicar la época de commit y reanotar el estado del par en el momento justo,
sin obligar a cada consumidor a acordarse de hacerlo.

Por qué está aquí y no en otro sitio: es una subclase de `sqlite3.Connection`
que no sabe nada de la política de apertura; solo avisa. Se puede quitar sin
que el resto deje de funcionar.

Quién lo usa: `journal.configure_writer` lo instala como `factory` de la
conexión.

Medida con la que se aprobó: `tests/test_sqlite_runtime.py`, incluida la
prueba de que un commit de otro proceso se ve y uno propio no se pierde.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from core.sqlite import config as _cfg
from core.sqlite import pair_guard as _pair_guard
from core.sqlite.epoch import _exclusive_commit_window


def guard_enabled() -> bool:
    """Reenvío: el interruptor se lee donde se define."""
    return _cfg.guard_enabled()


def record_pair_state(database) -> None:
    """Reenvío: la anotación del par se hace donde se define."""
    return _pair_guard.record_pair_state(database)

def _statement_may_write(sql: Any) -> bool:
    """Conservative first-keyword classifier for SQLite write statements."""
    if not isinstance(sql, (str, bytes)):
        return False
    if isinstance(sql, bytes):
        sql = sql.decode("utf-8", errors="ignore")
    statement = re.sub(r"(?m)^\s*(?:--[^\n]*(?:\n|$)|/\*.*?\*/\s*)+", "", sql).lstrip()
    match = re.match(r"([A-Za-z]+)", statement)
    if not match:
        return False
    keyword = match.group(1).upper()
    if keyword in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "REINDEX", "VACUUM", "ATTACH", "DETACH"}:
        return True
    if keyword == "WITH":
        return bool(re.search(r"\b(INSERT|UPDATE|DELETE|REPLACE)\b", statement, re.I))
    if keyword == "PRAGMA":
        pragma = statement.partition(" ")[2].strip()
        match = re.match(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)", pragma)
        if not match:
            return False
        pragma_name = match.group(1).lower()
        if pragma_name == "wal_checkpoint":
            return True
        if "=" not in pragma:
            return False
        # Only database-persistent header/schema pragmas can attest a file
        # transition. Connection-local settings such as busy_timeout must not
        # advance the epoch.
        return pragma_name in {
            "application_id", "auto_vacuum", "encoding", "journal_mode",
            "page_size", "schema_version", "secure_delete", "user_version",
        }
    return False

class _TrackedSQLiteCursor(sqlite3.Cursor):
    """Cursor that publishes DML, auto-committed DDL and scripts safely."""

    def execute(self, sql, parameters=()):
        keyword = _statement_keyword(sql)
        if keyword in {"COMMIT", "END"}:
            self.connection.commit()
            return self
        if keyword == "ROLLBACK":
            self.connection.rollback()
            return self
        may_write = _statement_may_write(sql)
        data_version = self.connection._data_version() if may_write else None
        result = super().execute(sql, parameters)
        if may_write:
            self.connection._biorag_pending_write = True
            if not self.connection.in_transaction:
                self.connection._biorag_pending_write = False
                self.connection._publish_autocommit(data_version)
        return result

    def executemany(self, sql, seq_of_parameters):
        may_write = _statement_may_write(sql)
        data_version = self.connection._data_version() if may_write else None
        result = super().executemany(sql, seq_of_parameters)
        if may_write:
            self.connection._biorag_pending_write = True
            if not self.connection.in_transaction:
                self.connection._biorag_pending_write = False
                self.connection._publish_autocommit(data_version)
        return result

    def executescript(self, sql_script):
        connection = self.connection
        if connection.in_transaction:
            connection.commit()
        may_write = _statement_may_write(sql_script)
        data_version = connection._data_version() if may_write else None
        result = super().executescript(sql_script)
        if may_write:
            connection._biorag_pending_write = True
            if not connection.in_transaction:
                connection._biorag_pending_write = False
                connection._publish_autocommit(data_version)
        return result

def _statement_keyword(sql: Any) -> str:
    """Primera palabra de la sentencia SQL, sin comentarios. Se usa para saber si escribe."""
    if isinstance(sql, bytes):
        sql = sql.decode("utf-8", errors="ignore")
    if not isinstance(sql, str):
        return ""
    statement = re.sub(r"(?m)^\s*(?:--[^\n]*(?:\n|$)|/\*.*?\*/\s*)+", "", sql).lstrip()
    match = re.match(r"([A-Za-z]+)", statement)
    return match.group(1).upper() if match else ""

class _TrackedSQLiteConnection(sqlite3.Connection):
    """Attests current-process commits under SQLite's writer lock."""

    def __init__(self, database, *args, **kwargs):
        super().__init__(database, *args, **kwargs)
        self._biorag_database = database
        self._biorag_pending_write = False

    def _data_version(self) -> int:
        row = sqlite3.Connection.execute(self, "PRAGMA data_version").fetchone()
        return int(row[0]) if row else -1

    def _assert_no_foreign_commit(self, data_version_before) -> None:
        """Fail closed when another connection committed during our write.

        ``PRAGMA data_version`` is *not* advanced by the connection's own
        commits; it only moves when a different connection changes the file. So
        a non-zero delta right after our commit means a foreign commit was
        interleaved. Version 4 of the protocol never attests such a state: the
        file may already mix a coordinated commit with a legacy one.
        """
        if data_version_before is None:
            raise sqlite3.OperationalError("Falta la sonda previa del commit SQLite.")
        after = self._data_version()
        delta = (after - int(data_version_before)) & 0xFFFFFFFF
        if delta != 0:
            raise sqlite3.OperationalError(
                "Se detectó un commit externo no coordinado durante la operación; "
                "el commit quedó aplicado, pero no se publicó como generación segura."
            )

    def _publish_autocommit(self, data_version_before) -> None:
        """Attest an autocommitted statement (DDL, PRAGMA or script) atomically.

        The statement is already committed here, so the exclusive window only
        spans the publication: a concurrent reader sees either the previous
        epoch with the previous file, or the new epoch with the new file.
        """
        with _exclusive_commit_window(self._biorag_database) as publish:
            self._assert_no_foreign_commit(data_version_before)
            publish()

    def cursor(self, factory=None):
        if factory not in (None, _TrackedSQLiteCursor):
            raise TypeError("open_writer requiere cursores con seguimiento de commits")
        cursor = sqlite3.Connection.cursor(self, _TrackedSQLiteCursor)
        # Se recuerda el cursor para poder liberarlo al cerrar. `execute()`
        # crea uno por sentencia y no lo cierra: ese cursor mantiene viva la
        # conexión hasta que pasa el recolector, y mientras esté viva la base
        # sigue bloqueada (el `-wal` no se consolida y una apertura posterior
        # falla con "database is locked"). Cerrarlos al cerrar la conexión
        # hace que el bloqueo se suelte en el acto.
        pendientes = self.__dict__.setdefault("_biorag_cursors", [])
        pendientes.append(cursor)
        return cursor

    def close(self):
        """Cierra la conexión y los cursores que creó, en ese orden.

        Motivo: `execute()` deja un cursor abierto por sentencia. Si no se
        cierran, la conexión no se libera hasta el recolector de basura y el
        archivo queda bloqueado mientras tanto (ver `cursor`).
        """
        pendientes = self.__dict__.pop("_biorag_cursors", [])
        for cursor in pendientes:
            try:
                cursor.close()
            except sqlite3.Error:
                pass  # un cursor ya cerrado no debe impedir cerrar la conexión
        return super().close()

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, seq_of_parameters):
        return self.cursor().executemany(sql, seq_of_parameters)

    def executescript(self, sql_script):
        return self.cursor().executescript(sql_script)

    def commit(self):
        if not self.in_transaction or not self._biorag_pending_write:
            return sqlite3.Connection.commit(self)
        data_version = self._data_version()
        with _exclusive_commit_window(self._biorag_database) as publish:
            result = sqlite3.Connection.commit(self)
            self._biorag_pending_write = False
            self._assert_no_foreign_commit(data_version)
            publish()
            # Anotar el par tras cada commit propio: si el proceso se cae
            # después, la próxima apertura puede distinguir un diario nuevo
            # legítimo de uno heredado comparando el principal.
            if guard_enabled():
                record_pair_state(self._biorag_database)
        return result

    def rollback(self):
        result = sqlite3.Connection.rollback(self)
        self._biorag_pending_write = False
        return result

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
