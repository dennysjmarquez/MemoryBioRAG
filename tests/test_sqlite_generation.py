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


def test_peer_open_writer_ddl_commit_advances_shared_epoch(tmp_path):
    """A commit from another supported process is explicitly attested cross-process."""
    import subprocess
    import sys

    db_path = tmp_path / "peer_ddl.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    retained = cerebro.cursor
    code = r'''
import sys
from core.sqlite_runtime import open_writer
conn = open_writer(sys.argv[1], consumer="peer_ddl_test")
conn.execute("CREATE TABLE peer_ddl_probe (value INTEGER NOT NULL)")
conn.close()
'''
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    try:
        peer = subprocess.run([sys.executable, "-c", code, str(db_path)], env=env,
                              capture_output=True, text=True)
        assert peer.returncode == 0, peer.stderr
        assert retained.execute("SELECT COUNT(*) FROM peer_ddl_probe").fetchone()[0] == 0
    finally:
        cerebro.cerrar_sistema()


def test_concurrent_supported_process_commits_remain_readable(tmp_path):
    """Concurrent current-version writers publish a shared commit epoch."""
    from concurrent.futures import ThreadPoolExecutor
    import subprocess
    import sys

    db_path = tmp_path / "peer_concurrent.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    cerebro.cursor.execute("CREATE TABLE concurrent_probe (value INTEGER NOT NULL)")
    cerebro.conn.commit()
    retained = cerebro.cursor
    code = r'''
import sys
from core.sqlite_runtime import open_writer
conn = open_writer(sys.argv[1], timeout=30, consumer="peer_concurrent_test")
conn.execute("INSERT INTO concurrent_probe VALUES (?)", (int(sys.argv[2]),))
conn.commit()
conn.close()
'''
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            runs = [pool.submit(subprocess.run,
                                [sys.executable, "-c", code, str(db_path), str(value)],
                                env=env, capture_output=True, text=True)
                    for value in (11, 22)]
            results = [future.result(timeout=60) for future in runs]
        assert all(result.returncode == 0 for result in results), [r.stderr for r in results]
        assert retained.execute(
            "SELECT value FROM concurrent_probe ORDER BY value"
        ).fetchall() == [(11,), (22,)]
    finally:
        cerebro.cerrar_sistema()


def test_legacy_raw_sqlite_commit_fails_closed_then_is_visible_after_reopen(tmp_path):
    """Unattested old consumers remain usable, but cannot bypass generation checks."""
    db_path = tmp_path / "legacy_peer.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    cerebro.cursor.execute("CREATE TABLE legacy_probe (value INTEGER NOT NULL)")
    cerebro.conn.commit()
    retained = cerebro.cursor
    legacy = sqlite3.connect(db_path)
    try:
        legacy.execute("INSERT INTO legacy_probe VALUES (5)")
        legacy.commit()
    finally:
        legacy.close()

    try:
        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute("SELECT value FROM legacy_probe").fetchall()
    finally:
        cerebro.cerrar_sistema()

    reopened = SQLiteMemoryBioRAG(str(db_path))
    try:
        assert reopened.cursor.execute(
            "SELECT value FROM legacy_probe"
        ).fetchone()[0] == 5
    finally:
        reopened.cerrar_sistema()


def test_crash_after_sqlite_commit_before_epoch_publication_fails_closed(tmp_path):
    """A commit/marker crash gap never blesses a changed DB in the old instance."""
    import subprocess
    import sys

    db_path = tmp_path / "commit_crash.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    cerebro.cursor.execute("CREATE TABLE crash_probe (value INTEGER NOT NULL)")
    cerebro.conn.commit()
    retained = cerebro.cursor
    code = r'''
import os, sys
import core.sqlite_runtime as runtime
conn = runtime.open_writer(sys.argv[1], consumer="crash_gap_test")
conn.execute("INSERT INTO crash_probe VALUES (9)")
runtime._publish_state_locked = (
    lambda _marker, _db: (_ for _ in ()).throw(OSError("simulated crash gap"))
)
try:
    conn.commit()  # SQLite commit succeeds; publishing the epoch then fails.
except OSError:
    os._exit(0)
os._exit(3)
'''
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    try:
        peer = subprocess.run([sys.executable, "-c", code, str(db_path)], env=env,
                              capture_output=True, text=True)
        assert peer.returncode == 0, peer.stderr
        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute("SELECT value FROM crash_probe").fetchall()
    finally:
        cerebro.cerrar_sistema()

    reopened = SQLiteMemoryBioRAG(str(db_path))
    try:
        assert reopened.cursor.execute(
            "SELECT value FROM crash_probe"
        ).fetchone()[0] == 9
    finally:
        reopened.cerrar_sistema()


def test_wal_checkpoint_without_commit_is_accepted(tmp_path, monkeypatch):
    """A real checkpoint is not confused with an external logical transaction."""
    from core.sqlite_runtime import open_writer

    monkeypatch.setattr(sqlite_runtime, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "wal_checkpoint.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    pinned_reader = None
    try:
        assert cerebro.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        cerebro.cursor.execute("CREATE TABLE wal_checkpoint_probe (value INTEGER)")
        cerebro.cursor.execute("INSERT INTO wal_checkpoint_probe VALUES (1)")
        cerebro.conn.commit()
        pinned_reader = sqlite3.connect(db_path)
        pinned_reader.execute("BEGIN")
        pinned_reader.execute("SELECT * FROM wal_checkpoint_probe").fetchall()
        peer = open_writer(db_path, consumer="wal_checkpoint_peer")
        try:
            peer.execute("INSERT INTO wal_checkpoint_probe VALUES (2)")
            peer.commit()
        finally:
            peer.close()
        assert cerebro.cursor.execute(
            "SELECT COUNT(*) FROM wal_checkpoint_probe"
        ).fetchone()[0] == 2
        pinned_reader.close()
        pinned_reader = None
        checkpoint = open_writer(db_path, consumer="wal_checkpoint_test")
        try:
            result = checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            assert result is not None and result[0] == 0
        finally:
            checkpoint.close()
        assert cerebro.cursor.execute(
            "SELECT COUNT(*) FROM wal_checkpoint_probe"
        ).fetchone()[0] == 2
    finally:
        if pinned_reader is not None:
            pinned_reader.close()
        cerebro.cerrar_sistema()


def test_legacy_commit_after_cooperative_commit_does_not_borrow_epoch(tmp_path):
    """Un commit antiguo intercalado no puede ampararse en la época compatible."""
    from core.sqlite_runtime import open_writer

    db_path = tmp_path / "interleaved_legacy.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    cerebro.cursor.execute("CREATE TABLE interleaved_probe (value INTEGER NOT NULL)")
    cerebro.conn.commit()
    retained = cerebro.cursor

    peer = open_writer(db_path, consumer="interleaved_compat_peer")
    try:
        peer.execute("INSERT INTO interleaved_probe VALUES (1)")
        peer.commit()
    finally:
        peer.close()

    # Un consumidor antiguo confirma su propio cambio antes de la lectura; la
    # época avanzada no atestigua el estado final del archivo.
    legacy = sqlite3.connect(db_path)
    try:
        legacy.execute("INSERT INTO interleaved_probe VALUES (2)")
        legacy.commit()
    finally:
        legacy.close()

    try:
        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute(
                "SELECT value FROM interleaved_probe ORDER BY value"
            ).fetchall()
    finally:
        cerebro.cerrar_sistema()

    # La base sigue íntegra y accesible tras reabrir.
    reopened = SQLiteMemoryBioRAG(str(db_path))
    try:
        assert reopened.cursor.execute(
            "SELECT value FROM interleaved_probe ORDER BY value"
        ).fetchall() == [(1,), (2,)]
    finally:
        reopened.cerrar_sistema()


def test_atestacion_no_degrada_wal_y_conserva_sidecars(tmp_path, monkeypatch):
    """La publicación de commits no debe cambiar el journal ni perder sidecars."""
    monkeypatch.setattr(sqlite_runtime, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "wal_attest.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        assert cerebro.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        cerebro.cursor.execute("CREATE TABLE wal_attest_probe (value INTEGER)")
        cerebro.conn.commit()
        cerebro.cursor.execute("INSERT INTO wal_attest_probe VALUES (1)")
        cerebro.conn.commit()
        assert cerebro.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert (tmp_path / "wal_attest.db-wal").exists()
        assert cerebro.cursor.execute(
            "SELECT COUNT(*) FROM wal_attest_probe"
        ).fetchone()[0] == 1
    finally:
        cerebro.cerrar_sistema()


def test_commit_sin_cambios_no_pierde_economia_ni_bloquea(tmp_path, monkeypatch):
    """Un commit vacío debe respetar el contrato DB-API sin publicar generación."""
    monkeypatch.setattr(sqlite_runtime, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "empty_commit.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE empty_commit_probe (value INTEGER)")
        cerebro.conn.commit()
        cerebro.cursor.execute("BEGIN")
        cerebro.cursor.execute("SELECT COUNT(*) FROM empty_commit_probe").fetchone()
        cerebro.conn.commit()
        assert cerebro.cursor.execute(
            "SELECT COUNT(*) FROM empty_commit_probe"
        ).fetchone()[0] == 0
    finally:
        cerebro.cerrar_sistema()
