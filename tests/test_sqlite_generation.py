"""Detección de sustitución de DB con conexiones abiertas, solo en fixtures temporales."""

import os
import shutil
import sqlite3

import pytest

import core.sqlite_runtime as sqlite_runtime
from core.memory_store import SQLiteMemoryBioRAG
from core.sqlite_runtime import SQLiteDatabaseIdentityChangedError


def test_motor_antiguo_rechaza_escritura_tras_reemplazo_de_db(tmp_path):
    db_path = tmp_path / "memoria.db"
    old_path = tmp_path / "memoria-original.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute(
            "CREATE TABLE generation_probe (value TEXT NOT NULL)"
        )
        cerebro.cursor.execute("INSERT INTO generation_probe VALUES ('old-generation')")
        cerebro.conn.commit()

        try:
            os.replace(db_path, old_path)
        except PermissionError as exc:
            if os.name == "nt":
                pytest.skip(f"Windows impidió reemplazar el archivo abierto: {exc}")
            raise

        replacement = sqlite3.connect(db_path)
        try:
            replacement.execute(
                "CREATE TABLE generation_probe (value TEXT NOT NULL)"
            )
            replacement.execute(
                "INSERT INTO generation_probe VALUES ('new-generation')"
            )
            replacement.commit()
        finally:
            replacement.close()

        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            cerebro.percibir_corto_plazo("stale_probe", "no debe escribirse")

        for path, expected in ((old_path, "old-generation"), (db_path, "new-generation")):
            check = sqlite3.connect(path)
            try:
                assert check.execute(
                    "SELECT value FROM generation_probe"
                ).fetchone()[0] == expected
            finally:
                check.close()
    finally:
        cerebro.cerrar_sistema()


def test_motor_rechaza_cambio_in_place_y_dbapi_handles_retenidos(tmp_path):
    db_path = tmp_path / "in_place.db"
    replacement_path = tmp_path / "replacement.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute(
            "CREATE TABLE generation_probe (value TEXT NOT NULL)"
        )
        cerebro.cursor.execute(
            "INSERT INTO generation_probe VALUES ('old-generation')"
        )
        cerebro.conn.commit()

        retained_cursor = cerebro.cursor
        retained_connection = cerebro.conn
        assert retained_cursor.execute(
            "SELECT value FROM generation_probe"
        ).fetchone()[0] == "old-generation"

        replacement = sqlite3.connect(replacement_path)
        try:
            replacement.execute(
                "CREATE TABLE generation_probe (value TEXT NOT NULL)"
            )
            replacement.execute(
                "INSERT INTO generation_probe VALUES ('new-generation')"
            )
            replacement.commit()
        finally:
            replacement.close()

        inode_before = os.stat(db_path).st_ino
        try:
            shutil.copyfile(replacement_path, db_path)
        except PermissionError as exc:
            if os.name == "nt":
                pytest.skip(f"Windows impidió sobrescribir el archivo abierto: {exc}")
            raise
        assert os.stat(db_path).st_ino == inode_before
        replacement_bytes = db_path.read_bytes()

        for handle in (retained_cursor, retained_connection):
            try:
                rows = handle.execute("SELECT value FROM generation_probe").fetchone()
            except sqlite3.Error:
                # SQLite puede fallar de forma nativa al cambiar un archivo abierto;
                # también es un cierre seguro si no devuelve la generación anterior.
                continue
            assert rows != ("old-generation",)
        assert db_path.read_bytes() == replacement_bytes

        # Windows may deny an independent SQLite open while the original handle
        # is still alive; verify the replacement only after orderly closure.
        cerebro.cerrar_sistema()
        cerebro = None
        check = sqlite3.connect(db_path)
        try:
            assert check.execute(
                "SELECT value FROM generation_probe"
            ).fetchone()[0] == "new-generation"
        finally:
            check.close()
    finally:
        if cerebro is not None:
            cerebro.cerrar_sistema()


def test_cursor_retenido_no_devuelve_filas_stale_tras_copia_mismo_esquema(tmp_path):
    db_path = tmp_path / "same_schema.db"
    replacement_path = tmp_path / "same_schema_replacement.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute(
            "CREATE TABLE stable_schema_probe (value TEXT NOT NULL)"
        )
        cerebro.cursor.execute(
            "INSERT INTO stable_schema_probe VALUES ('old-generation')"
        )
        cerebro.conn.commit()
        retained_cursor = cerebro.cursor
        retained_connection = cerebro.conn

        replacement = sqlite3.connect(replacement_path)
        try:
            retained_connection.backup(replacement)
            replacement.execute(
                "UPDATE stable_schema_probe SET value='new-generation'"
            )
            replacement.commit()
        finally:
            replacement.close()

        inode_before = os.stat(db_path).st_ino
        try:
            shutil.copyfile(replacement_path, db_path)
        except PermissionError as exc:
            if os.name == "nt":
                pytest.skip(f"Windows impidió sobrescribir el archivo abierto: {exc}")
            raise
        assert os.stat(db_path).st_ino == inode_before

        try:
            result = retained_cursor.execute(
                "SELECT value FROM stable_schema_probe"
            ).fetchone()[0]
        except sqlite3.Error:
            result = None  # fail closed es válido; devolver datos de la generación vieja no.
        assert result != "old-generation"
        if result is not None:
            assert result == "new-generation"
    finally:
        cerebro.cerrar_sistema()


@pytest.mark.parametrize("suffix", ("-wal", "-shm"))
def test_motor_rechaza_reemplazo_del_sidecar_sin_modificarlo(tmp_path, monkeypatch, suffix):
    # El sandbox incluye SQLite 3.40; simular solo el clasificador de versión
    # fija permite ejercitar WAL sobre un archivo descartable.
    monkeypatch.setattr(sqlite_runtime, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "wal.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    sidecar_path = tmp_path / f"wal.db{suffix}"
    moved_sidecar = tmp_path / f"wal-original.db{suffix}"
    try:
        assert cerebro.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        cerebro.cursor.execute("CREATE TABLE wal_probe (value INTEGER)")
        cerebro.conn.commit()
        assert sidecar_path.exists()
        assert cerebro._sidecar_identities.get(suffix) is not None

        try:
            os.replace(sidecar_path, moved_sidecar)
        except PermissionError as exc:
            if os.name == "nt":
                pytest.skip(f"Windows bloqueó el reemplazo del sidecar abierto: {exc}")
            raise
        sidecar_path.write_bytes(b"external replacement fixture")

        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            cerebro.cursor.execute("SELECT 1")
        assert sidecar_path.read_bytes() == b"external replacement fixture"
        assert moved_sidecar.exists()
    finally:
        cerebro.cerrar_sistema()
