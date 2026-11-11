"""Detección de sustitución de DB con conexiones abiertas, solo en fixtures temporales."""

import subprocess
import sys
import os
import shutil
from pathlib import Path
import sqlite3

import pytest

import core.sqlite_runtime as sqlite_runtime
from core.sqlite import constants as _sqlite_config
from core.sqlite import pair_guard as _sqlite_pair_guard
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
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
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
import core.sqlite.epoch as epoch_mod
conn = runtime.open_writer(sys.argv[1], consumer="crash_gap_test")
conn.execute("INSERT INTO crash_probe VALUES (9)")
epoch_mod._publish_state_locked = (
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

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
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
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
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
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
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


def test_commit_coordinado_seguido_de_raw_en_wal_no_se_acepta(tmp_path, monkeypatch):
    """Regresión de docs/auditoria_pr13_wal_9b39f4b.md (secuencia en WAL).

    En WAL el commit apenas toca el archivo principal, así que una firma que lo
    ignoraba aceptaba un commit raw posterior a uno coordinado. El contraste
    debe fallar cerrado igual que el control.
    """
    from core.sqlite_runtime import open_writer

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))

    def _explorar(con_previo_coordinado):
        db_path = tmp_path / ("wal_seq_compat.db" if con_previo_coordinado else "wal_seq_control.db")
        cerebro = SQLiteMemoryBioRAG(str(db_path))
        try:
            cerebro.cursor.execute("CREATE TABLE wal_seq_probe (value INTEGER NOT NULL)")
            cerebro.conn.commit()
            retained = cerebro.cursor
            assert retained.execute(
                "SELECT COUNT(*) FROM wal_seq_probe"
            ).fetchone()[0] == 0
            assert cerebro._journal_mode == "wal"

            if con_previo_coordinado:
                peer = open_writer(db_path, consumer="wal_seq_peer")
                try:
                    peer.execute("INSERT INTO wal_seq_probe VALUES (1)")
                    peer.commit()
                finally:
                    peer.close()

            raw = sqlite3.connect(db_path)
            try:
                raw.execute("INSERT INTO wal_seq_probe VALUES (99)")
                raw.commit()
            finally:
                raw.close()

            with pytest.raises(SQLiteDatabaseIdentityChangedError):
                retained.execute("SELECT value FROM wal_seq_probe ORDER BY value").fetchall()
        finally:
            cerebro.cerrar_sistema()

    # Control: solo el cliente raw debe alertar.
    _explorar(False)
    # Contraste: coordinado y después raw, también debe alertar.
    _explorar(True)


def test_checkpoint_cooperativo_no_es_un_cambio_no_atestiguado(tmp_path, monkeypatch):
    """Un checkpoint de un escritor compatible no debe disparar falsa alarma."""
    from core.sqlite_runtime import open_writer

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "wal_ckpt_probe.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE wal_ckpt_probe (value INTEGER)")
        cerebro.cursor.execute("INSERT INTO wal_ckpt_probe VALUES (1)")
        cerebro.conn.commit()
        assert cerebro.cursor.execute(
            "SELECT COUNT(*) FROM wal_ckpt_probe"
        ).fetchone()[0] == 1

        checkpoint = open_writer(db_path, consumer="ckpt_peer")
        try:
            assert checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
        finally:
            checkpoint.close()

        assert cerebro.cursor.execute(
            "SELECT COUNT(*) FROM wal_ckpt_probe"
        ).fetchone()[0] == 1
    finally:
        cerebro.cerrar_sistema()


def test_reuso_de_wal_tras_checkpoint_no_oculta_commit_raw(tmp_path, monkeypatch):
    # Política cerrada: tras un checkpoint externo el principal cambia y el
    # motor pide confirmación explícita antes de reabrir.
    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "1")
    """Regresión de docs/auditoria_pr13_reuso_wal_68e4151.md.

    Tras un checkpoint PASSIVE el WAL conserva su tamaño y los commits reutilizan
    frames dentro del área ya válida. Muestrear cabecera y cola no alcanza: solo
    el digest completo distingue el commit raw posterior a uno coordinado.
    """
    from core.sqlite_runtime import open_writer

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))

    def _preparar(nombre):
        db_path = tmp_path / f"{nombre}.db"
        cerebro = SQLiteMemoryBioRAG(str(db_path))
        cerebro.cursor.execute("CREATE TABLE reuso_probe (value INTEGER, relleno TEXT)")
        cerebro.conn.commit()
        cerebro.cursor.execute("BEGIN")
        cerebro.cursor.executemany(
            "INSERT INTO reuso_probe VALUES (?, ?)",
            [(i, "x" * 200) for i in range(4000)],
        )
        cerebro.conn.commit()
        assert cerebro._journal_mode == "wal"
        peer = open_writer(db_path, consumer="reuso_checkpoint")
        try:
            assert peer.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()[0] == 0
        finally:
            peer.close()
        return cerebro, db_path

    def _explorar(nombre, con_previo_coordinado):
        cerebro, db_path = _preparar(nombre)
        try:
            retained = cerebro.cursor
            assert retained.execute("SELECT COUNT(*) FROM reuso_probe").fetchone()[0] > 0

            if con_previo_coordinado:
                peer = open_writer(db_path, consumer="reuso_peer")
                try:
                    peer.execute("INSERT INTO reuso_probe VALUES (1, 'coord')")
                    peer.commit()
                finally:
                    peer.close()

            raw = sqlite3.connect(db_path)
            try:
                raw.execute("INSERT INTO reuso_probe VALUES (99, 'raw')")
                raw.commit()
            finally:
                raw.close()

            with pytest.raises(SQLiteDatabaseIdentityChangedError):
                retained.execute("SELECT COUNT(*) FROM reuso_probe").fetchall()
        finally:
            cerebro.cerrar_sistema()

    _explorar("reuso_control", False)
    _explorar("reuso_contraste", True)


def test_checkpoint_de_cliente_sin_protocolo_falla_cerrado(tmp_path, monkeypatch):
    """Límite operativo documentado, no un bug (auditoría 68e4151).

    Un checkpoint ejecutado por una conexión que no acata el protocolo reescribe
    el archivo principal (páginas del WAL pasan al .db). Es el mismo tipo de
    cambio que una sustitución in-place, así que la política es fallar cerrado:
    los checkpoints de mantenimiento deben hacerse con `open_writer`.
    """
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "raw_checkpoint.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE raw_ckpt_probe (value INTEGER)")
        cerebro.cursor.execute("INSERT INTO raw_ckpt_probe VALUES (1)")
        cerebro.conn.commit()
        retained = cerebro.cursor
        assert retained.execute("SELECT COUNT(*) FROM raw_ckpt_probe").fetchone()[0] == 1

        # Cliente sin protocolo: no escribe datos, solo ejecuta mantenimiento.
        raw = sqlite3.connect(db_path)
        try:
            raw.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        finally:
            raw.close()

        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute("SELECT COUNT(*) FROM raw_ckpt_probe").fetchone()
    finally:
        cerebro.cerrar_sistema()

    # La base sigue íntegra y accesible tras reabrir: no se perdió nada.
    reopened = SQLiteMemoryBioRAG(str(db_path))
    try:
        assert reopened.cursor.execute(
            "SELECT COUNT(*) FROM raw_ckpt_probe"
        ).fetchone()[0] == 1
    finally:
        reopened.cerrar_sistema()


def test_lectura_sin_cambios_no_rehashea_el_wal(tmp_path, monkeypatch):
    """El coste de la firma no debe crecer con el WAL en cada lectura.

    Auditoría 2818e72: hashear el WAL completo en cada comprobación hacía que 30
    lecturas sobre un WAL grande pasaran de 0,010 s a 1,428 s. Las sondas baratas
    (data_version y época) evitan el hash cuando nada cambió.
    """
    import time

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "perf_wal.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE perf_probe (value INTEGER, relleno TEXT)")
        cerebro.conn.commit()
        cerebro.cursor.execute("BEGIN")
        cerebro.cursor.executemany(
            "INSERT INTO perf_probe VALUES (?, ?)",
            [(i, "x" * 200) for i in range(20000)],
        )
        cerebro.conn.commit()
        wal = tmp_path / "perf_wal.db-wal"
        assert wal.exists() and wal.stat().st_size > 5_000_000

        retained = cerebro.cursor
        retained.execute("SELECT COUNT(*) FROM perf_probe").fetchone()

        start = time.perf_counter()
        for _ in range(30):
            retained.execute("SELECT COUNT(*) FROM perf_probe").fetchone()
        elapsed = time.perf_counter() - start

        # Margen amplio: el valor correcto está en milisegundos; el defecto
        # tardaba ~1,4 s para este tamaño de WAL.
        assert elapsed < 0.5, f"lecturas sin cambio demasiado costosas: {elapsed:.3f}s"
    finally:
        cerebro.cerrar_sistema()


def test_alteracion_in_place_de_tamano_constante_se_detecta(tmp_path, monkeypatch):
    """Regresión de docs/auditoria_pr13_d5c3834.md, caso 1.

    Un fast path basado en data_version, época y tamaño del archivo principal
    dejaba pasar una reescritura externa con el mismo tamaño e inodo: solo
    cambian mtime/ctime y el contenido. La firma completa debe detectarlo.
    """
    import os

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 45, 1))
    db_path = tmp_path / "in_place_same_size.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE tamano_probe (value TEXT)")
        cerebro.cursor.execute("INSERT INTO tamano_probe VALUES ('AAAA')")
        cerebro.conn.commit()
        retained = cerebro.cursor
        assert retained.execute("SELECT value FROM tamano_probe").fetchone() == ("AAAA",)

        data = db_path.read_bytes()
        offset = data.find(b"AAAA")
        assert offset >= 0
        st = os.stat(db_path)
        with open(db_path, "r+b") as handle:
            handle.write(data[:offset] + b"BBBB" + data[offset + 4:])
        os.utime(db_path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        assert os.stat(db_path).st_size == st.st_size
        assert os.stat(db_path).st_ino == st.st_ino

        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute("SELECT value FROM tamano_probe").fetchone()
    finally:
        cerebro.cerrar_sistema()


def test_checkpoint_raw_sin_cambio_de_tamano_se_detecta(tmp_path, monkeypatch):
    """Regresión de docs/auditoria_pr13_d5c3834.md, caso 2.

    Un checkpoint PASSIVE ejecutado por un cliente sin protocolo puede mover
    páginas del WAL al archivo principal sin cambiar su tamaño ni data_version.
    Debe seguir fallando cerrado.

    Lleva FORCE_OPEN porque esta prueba mide el rechazo por firma, y la capa
    nueva rechaza antes de llegar a esa comprobación: tras un checkpoint externo
    el principal cambió y el par no se puede verificar. Es el coste declarado de
    fallar cerrado, no un atajo de la prueba.
    """
    import os

    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "1")

    from core.sqlite_runtime import open_writer

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "raw_ckpt_same_size.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE ckpt_size_probe (value INTEGER, relleno TEXT)")
        cerebro.cursor.execute("INSERT INTO ckpt_size_probe VALUES (1, 'a')")
        cerebro.conn.commit()

        peer = open_writer(db_path, consumer="ckpt_size_setup")
        try:
            peer.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        finally:
            peer.close()

        peer = open_writer(db_path, consumer="ckpt_size_update")
        try:
            peer.execute("UPDATE ckpt_size_probe SET relleno='b' WHERE value=1")
            peer.commit()
        finally:
            peer.close()

        retained = cerebro.cursor
        retained.execute("SELECT COUNT(*) FROM ckpt_size_probe").fetchone()
        size_before = os.stat(db_path).st_size

        raw = sqlite3.connect(db_path)
        try:
            raw.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        finally:
            raw.close()
        assert os.stat(db_path).st_size == size_before

        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute("SELECT COUNT(*) FROM ckpt_size_probe").fetchone()
    finally:
        cerebro.cerrar_sistema()


def test_alteracion_directa_del_wal_se_detecta(tmp_path, monkeypatch):
    """Regresión de docs/auditoria_pr13_4747ca8.md.

    Una alteración directa de un byte del WAL no toca el archivo principal ni
    data_version. Una sonda barata limitada al archivo principal la dejaba pasar;
    la sonda debe cubrir también el WAL.
    """
    import os

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "wal_byte.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE wal_byte_probe (value INTEGER, relleno TEXT)")
        cerebro.cursor.execute("INSERT INTO wal_byte_probe VALUES (1, 'a')")
        cerebro.conn.commit()
        retained = cerebro.cursor
        assert retained.execute("SELECT COUNT(*) FROM wal_byte_probe").fetchone()[0] == 1

        wal_path = tmp_path / "wal_byte.db-wal"
        wal_stat = os.stat(wal_path)
        main_stat = os.stat(db_path)
        digest_before = sqlite_runtime._wal_content_signature(str(db_path))

        with open(wal_path, "r+b") as handle:
            handle.seek(-20, os.SEEK_END)
            byte = handle.read(1)
            handle.seek(-20, os.SEEK_END)
            handle.write(bytes([byte[0] ^ 0xFF]))

        # El WAL cambia de contenido sin cambiar de tamaño ni de inodo, y el
        # archivo principal queda intacto.
        assert sqlite_runtime._wal_content_signature(str(db_path)) != digest_before
        assert os.stat(wal_path).st_size == wal_stat.st_size
        assert os.stat(wal_path).st_ino == wal_stat.st_ino
        assert (
            os.stat(db_path).st_size,
            os.stat(db_path).st_mtime_ns,
            os.stat(db_path).st_ctime_ns,
        ) == (main_stat.st_size, main_stat.st_mtime_ns, main_stat.st_ctime_ns)

        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            retained.execute("SELECT COUNT(*) FROM wal_byte_probe").fetchone()
    finally:
        cerebro.cerrar_sistema()


def test_cambio_durante_la_instantanea_no_se_bendice(tmp_path, monkeypatch):
    """Regresión de docs/auditoria_pr13_41a98a3.md.

    Un cambio directo del WAL intercalado entre el cálculo de la firma y el
    registro del stat dejaba guardada una firma previa junto a un stat posterior,
    de modo que la lectura siguiente coincidía y no alertaba. La instantánea
    debe rechazarse cuando lo observado no coincide con lo atestiguado.
    """
    import os

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "snapshot_race.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    original = SQLiteMemoryBioRAG._file_change_signature
    state = {"armed": False, "fired": False}

    def hooked(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if state["armed"] and not state["fired"]:
            state["fired"] = True
            wal = tmp_path / "snapshot_race.db-wal"
            with open(wal, "r+b") as handle:
                handle.seek(-20, os.SEEK_END)
                byte = handle.read(1)
                handle.seek(-20, os.SEEK_END)
                handle.write(bytes([byte[0] ^ 0xFF]))
        return result

    try:
        cerebro.cursor.execute("CREATE TABLE snapshot_probe (value INTEGER, relleno TEXT)")
        cerebro.cursor.execute("INSERT INTO snapshot_probe VALUES (1, 'a')")
        cerebro.conn.commit()
        retained = cerebro.cursor
        retained.execute("SELECT COUNT(*) FROM snapshot_probe").fetchone()

        monkeypatch.setattr(SQLiteMemoryBioRAG, "_file_change_signature", hooked)
        cerebro.cursor.execute("INSERT INTO snapshot_probe VALUES (2, 'b')")
        state["armed"] = True
        with pytest.raises(SQLiteDatabaseIdentityChangedError):
            cerebro.conn.commit()
        assert state["fired"], "el hook no llegó a intercalarse"
    finally:
        monkeypatch.setattr(SQLiteMemoryBioRAG, "_file_change_signature", original)
        cerebro.cerrar_sistema()


def _preparar_dos_generaciones(tmp_path, nombre="rama"):
    """Base con dos versiones distintas, como dos ramas de git que la versionan."""
    db_path = tmp_path / f"{nombre}.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE memoria (id INTEGER PRIMARY KEY, texto TEXT)")
        conn.executemany(
            "INSERT INTO memoria (texto) VALUES (?)",
            [(f"A{i}" * 40,) for i in range(50)],
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    shutil.copyfile(db_path, tmp_path / f"{nombre}-version-B.db")

    conn = sqlite3.connect(tmp_path / f"{nombre}-version-B.db")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE otra_cosa (x)")
        conn.executemany(
            "INSERT INTO otra_cosa (x) VALUES (?)", [(f"B{i}" * 30,) for i in range(80)]
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    return db_path, tmp_path / f"{nombre}-version-B.db"


def test_al_cerrar_no_queda_un_wal_con_datos(tmp_path, monkeypatch):
    """Causa raíz: el motor consolida el diario al cerrarse.

    El problema original nacía de que el motor podía terminar con un `-wal` con
    datos. Ese archivo, al copiarse o versionarse aparte del `.db`, podía
    acabar junto a otra versión del principal y aplicarse sobre ella. Si al
    cerrar el diario queda vacío, ese estado no llega a existir.
    """
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "consolidado.db"

    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE t (v TEXT)")
        cerebro.cursor.executemany(
            "INSERT INTO t VALUES (?)", [(f"dato{i}" * 50,) for i in range(100)]
        )
        cerebro.conn.commit()
        wal = Path(str(db_path) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0, "antes de cerrar hay WAL"
    finally:
        cerebro.cerrar_sistema()

    wal = Path(str(db_path) + "-wal")
    assert (not wal.exists()) or wal.stat().st_size == 0, (
        "tras cerrar el diario debe quedar vacío: así no puede sobrevivir "
        "emparejado con otra versión del archivo principal"
    )

    comprobacion = sqlite3.connect(db_path)
    try:
        assert comprobacion.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 100
        assert comprobacion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        comprobacion.close()


def test_el_principal_cambia_tanto_en_mantenimiento_legitimo_como_en_sustitucion(
    tmp_path, monkeypatch
):
    """Documenta por qué no hay detección automática de WAL ajeno.

    Decidir "el principal cambió -> rechazar" bloquearía el mantenimiento
    normal de SQLite: comprobado en las auditorías, un checkpoint legítimo y
    una sustitución dejan el disco en estados del mismo tipo (principal
    modificado, diario con su sal). Ninguna comprobación los separa sin
    rechazar también la operación legítima.

    Por eso la protección elegida es eliminar el estado que lo permite
    (`test_al_cerrar_no_queda_un_wal_con_datos`), no adivinar pertenencia.
    """
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "cambia_siempre.db"

    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES (1, 'a')")
        cerebro.conn.commit()
    finally:
        cerebro.cerrar_sistema()

    antes = db_path.stat().st_size

    # Mantenimiento perfectamente legítimo: una escritura externa y su commit.
    escritor = sqlite3.connect(db_path)
    try:
        escritor.execute("PRAGMA journal_mode=WAL")
        # Una escritura externa legítima que además hace crecer el archivo.
        escritor.executemany(
            "INSERT INTO t (v) VALUES (?)", [("relleno" * 100,) for _ in range(200)]
        )
        escritor.commit()
        escritor.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
    finally:
        escritor.close()

    assert db_path.stat().st_size != antes, (
        "una operación legítima también cambia el tamaño del principal, así que "
        "ese cambio no distingue una sustitución de un mantenimiento normal"
    )


def test_caida_con_wal_vivo_recupera_los_datos(tmp_path, monkeypatch):
    """Escenario 1 de la auditora: caída del proceso.

    Tras una caída el `-wal` es de ESTA base: contiene commits propios que aún
    no se consolidaron. La capa no debe impedir que SQLite los aplique, porque
    impedirlo sería perder esos datos. Se mata un proceso real (no se cierran
    conexiones a mano) para que la prueba sea una caída de verdad.
    """
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "caida.db"
    repo = Path(__file__).resolve().parent.parent

    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES (1, 'antes')")
        cerebro.conn.commit()
    finally:
        cerebro.cerrar_sistema()

    guion = f"""
import sys, time
sys.path.insert(0, {str(repo)!r})
import core.sqlite_runtime as rt
from core.sqlite import constants as _cfg
_cfg._effective_sqlite_version = lambda: (3, 51, 3)  # entorno de pruebas
from core.memory_store import SQLiteMemoryBioRAG
c = SQLiteMemoryBioRAG({str(db_path)!r})
c.cursor.execute("INSERT INTO t VALUES (2, 'sin_consolidar')")
c.conn.commit()
print("LISTO", flush=True)
time.sleep(60)
"""
    proceso = subprocess.Popen(
        [sys.executable, "-c", guion],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        salida = proceso.stdout.readline().strip()
        if salida != "LISTO":
            raise AssertionError("hijo falló: " + proceso.stderr.read()[:3000])
        assert Path(str(db_path) + "-wal").stat().st_size > 0
    finally:
        proceso.kill()  # caída abrupta: sin consolidar, sin cerrar
        proceso.wait(timeout=30)

    assert Path(str(db_path) + "-wal").stat().st_size > 0, (
        "la caída debe dejar un WAL con datos pendientes"
    )

    reabierto = SQLiteMemoryBioRAG(str(db_path))
    try:
        assert reabierto.conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2, (
            "los datos del proceso caído deben recuperarse"
        )
        assert reabierto.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reabierto.cerrar_sistema()


def test_wal_ajeno_tras_cambio_de_rama_no_se_aplica(tmp_path, monkeypatch):
    """Escenario 2: el agente seguía abierto al cambiar de rama.

    Es el caso que originó todo esto. El `-wal` de la rama anterior no
    pertenece al principal actual: la capa lo detecta sin abrir el par y
    rechaza, conservando los archivos intactos.
    """
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    principal = tmp_path / "principal.db"

    cerebro = SQLiteMemoryBioRAG(str(principal))
    try:
        cerebro.cursor.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES (1, 'branch_B')")
        cerebro.conn.commit()
    finally:
        cerebro.cerrar_sistema()

    otra = tmp_path / "otra.db"
    shutil.copyfile(principal, otra)
    conn = sqlite3.connect(otra)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("UPDATE t SET v='branch_A' WHERE id=1")
        conn.commit()
        wal_bytes = Path(str(otra) + "-wal").read_bytes()
        shm_bytes = Path(str(otra) + "-shm").read_bytes()
    finally:
        conn.close()

    for suffix in ("-wal", "-shm"):
        leftover = Path(str(principal) + suffix)
        if leftover.exists():
            leftover.unlink()
    (tmp_path / "principal.db-wal").write_bytes(wal_bytes)
    (tmp_path / "principal.db-shm").write_bytes(shm_bytes)

    db_antes = principal.read_bytes()
    with pytest.raises(sqlite_runtime.SQLiteSidecarConflictError):
        SQLiteMemoryBioRAG(str(principal))

    assert principal.read_bytes() == db_antes, "el principal no debe cambiar"
    assert (tmp_path / "principal.db-wal").exists(), "el -wal no debe moverse"
    assert list(tmp_path.glob("*.conflicto.json")), "debe quedar constancia"


def test_consolidacion_imposible_no_rompe_el_cierre(tmp_path, monkeypatch):
    """Escenario 3: no se puede completar la consolidación al cerrar."""
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "solo_lectura.db"

    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE t (v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES ('dato')")
        cerebro.conn.commit()
    finally:
        os.chmod(db_path, 0o444)
        try:
            cerebro.cerrar_sistema()  # no debe lanzar
        finally:
            os.chmod(db_path, 0o644)

    comprobacion = sqlite3.connect(db_path)
    try:
        assert comprobacion.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        comprobacion.close()


def test_la_capa_se_puede_desactivar(tmp_path, monkeypatch):
    """Arquitectura: la protección es sustituible y se apaga sin tocar código."""
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "apagada.db"

    cerebro = SQLiteMemoryBioRAG(str(db_path))
    try:
        cerebro.cursor.execute("CREATE TABLE t (v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES ('dato')")
        cerebro.conn.commit()
    finally:
        cerebro.cerrar_sistema()

    monkeypatch.setenv("BIORAG_SQLITE_GUARD", "0")
    assert sqlite_runtime.guard_enabled() is False

    # Con la capa apagada no se consulta el estado del par: abre directo.
    conn = sqlite_runtime.open_writer(db_path, consumer="sin_capa")
    try:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        conn.close()

    monkeypatch.setenv("BIORAG_SQLITE_GUARD", "1")
    assert sqlite_runtime.guard_enabled() is True


def test_force_open_es_la_via_de_escape_autorizada(tmp_path, monkeypatch):
    """La recuperación no es automática: requiere autorización explícita."""
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    principal = tmp_path / "forzada.db"

    cerebro = SQLiteMemoryBioRAG(str(principal))
    try:
        cerebro.cursor.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES (1, 'original')")
        cerebro.conn.commit()
    finally:
        cerebro.cerrar_sistema()

    otra = tmp_path / "o.db"
    shutil.copyfile(principal, otra)
    conn = sqlite3.connect(otra)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("UPDATE t SET v='ajeno' WHERE id=1")
        conn.commit()
        wal_bytes = Path(str(otra) + "-wal").read_bytes()
    finally:
        conn.close()
    (tmp_path / "forzada.db-wal").write_bytes(wal_bytes)

    with pytest.raises(sqlite_runtime.SQLiteSidecarConflictError):
        sqlite_runtime.open_writer(principal)

    # Autorización explícita del operador: abre y deja constancia.
    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "1")
    conn = sqlite_runtime.open_writer(principal, consumer="forzada")
    try:
        conn.execute("SELECT COUNT(*) FROM t").fetchone()
    finally:
        conn.close()
    assert list(tmp_path.glob("*.conflicto.json"))


def test_la_proteccion_viene_activada_por_defecto(monkeypatch):
    """Requisito explicito: sin configurar nada, la capa esta encendida.

    Si alguien cambia el default a apagado, esto falla. No se prueba solo
    `guard_enabled()`: se prueba que la comprobacion del par realmente corre.
    """
    monkeypatch.delenv("BIORAG_SQLITE_GUARD", raising=False)
    monkeypatch.delenv("BIORAG_SQLITE_FORCE_OPEN", raising=False)

    assert sqlite_runtime.guard_enabled() is True
    assert sqlite_runtime.force_open_authorized() is False

    llamadas = []
    original = sqlite_runtime._pair_can_be_opened

    def espia(database):
        llamadas.append(str(database))
        return original(database)

    monkeypatch.setattr(_sqlite_pair_guard, "_pair_can_be_opened", espia)
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "defecto.db")
        cerebro = SQLiteMemoryBioRAG(db_path)
        try:
            cerebro.cursor.execute("CREATE TABLE t (v TEXT)")
            cerebro.conn.commit()
        finally:
            cerebro.cerrar_sistema()

        assert os.path.exists(db_path), "la base debe existir para reabrirla"

        # Segunda apertura: la base ya existe, asi que la comprobacion del par
        # tiene que ejecutarse sin que nadie configure nada.
        cerebro = SQLiteMemoryBioRAG(db_path)
        try:
            cerebro.cursor.execute("SELECT COUNT(*) FROM t").fetchone()
        finally:
            cerebro.cerrar_sistema()

    assert llamadas, "con el default, la comprobacion del par debe ejecutarse"


def test_wal_ajeno_con_principal_intacto_se_rechaza(tmp_path, monkeypatch):
    """Regresión de la revisión independiente sobre `88ef43f`, hallazgo 1.

    El caso 3 de `_pair_can_be_opened` aceptaba solo con que el sha256 del
    principal coincidiera con el anotado. Eso descarta la sustitución del
    archivo principal, pero NO que el `-wal` sea de otra base: tras una caída
    el principal queda intacto y el registro sigue valiendo, así que un diario
    ajeno puesto en ese hueco se aplicaba en silencio.

    La sal de la cabecera identifica al diario y ya estaba anotada; ahora
    participa en la decisión.
    """
    import subprocess
    import sys

    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    db_path = tmp_path / "principal_intacto.db"
    repo = Path(__file__).resolve().parent.parent

    # Proceso real que hace commit y se queda abierto: el principal queda
    # registrado y sin cambios, que es el estado del fallo.
    guion = f"""
import sys, time
sys.path.insert(0, {str(repo)!r})
from core.sqlite import constants as _cfg
_cfg._effective_sqlite_version = lambda: (3, 51, 3)
from core.memory_store import SQLiteMemoryBioRAG
c = SQLiteMemoryBioRAG({str(db_path)!r})
c.cursor.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
c.cursor.execute("INSERT INTO t VALUES (1, 'original')")
c.conn.commit()
print("LISTO", flush=True)
time.sleep(60)
"""
    proceso = subprocess.Popen(
        [sys.executable, "-c", guion],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        salida = proceso.stdout.readline().strip()
        if salida != "LISTO":
            raise AssertionError("hijo falló: " + proceso.stderr.read()[:3000])
    finally:
        proceso.kill()  # caída: el principal queda como estaba, el registro vale
        proceso.wait(timeout=30)

    principal_antes = db_path.read_bytes()

    # Un `-wal` de OTRA base, colocado junto a este principal intacto.
    otra = tmp_path / "otra_base.db"
    conn = sqlite3.connect(otra)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("UPDATE t SET v='INYECTADO' WHERE id=1")
        conn.commit()
        wal_bytes = Path(str(otra) + "-wal").read_bytes()
    finally:
        conn.close()
    for suffix in ("-wal", "-shm"):
        leftover = Path(str(db_path) + suffix)
        if leftover.exists():
            leftover.unlink()
    Path(str(db_path) + "-wal").write_bytes(wal_bytes)

    with pytest.raises(sqlite_runtime.SQLiteSidecarConflictError):
        SQLiteMemoryBioRAG(str(db_path))

    assert db_path.read_bytes() == principal_antes, "el principal no debe cambiar"
    assert Path(str(db_path) + "-wal").exists(), "el -wal no debe moverse"


def test_open_reader_rechaza_el_mismo_par_que_open_writer(tmp_path, monkeypatch):
    """Regresión de la revisión independiente sobre `88ef43f`, hallazgo 2.

    `open_reader` abría el par sin comprobar pertenencia, así que aceptaba lo
    que `open_writer` rechazaba y las lecturas veían datos de otra versión.
    Las dos puertas deben aplicar la misma política.
    """
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: (3, 51, 3))
    principal = tmp_path / "dos_puertas.db"

    cerebro = SQLiteMemoryBioRAG(str(principal))
    try:
        cerebro.cursor.execute("CREATE TABLE t (v TEXT)")
        cerebro.cursor.execute("INSERT INTO t VALUES ('base')")
        cerebro.conn.commit()
    finally:
        cerebro.cerrar_sistema()

    otra = tmp_path / "ajena.db"
    shutil.copyfile(principal, otra)
    conn = sqlite3.connect(otra)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("UPDATE t SET v='AJENO'")
        conn.commit()
        wal_bytes = Path(str(otra) + "-wal").read_bytes()
    finally:
        conn.close()
    for suffix in ("-wal", "-shm"):
        leftover = Path(str(principal) + suffix)
        if leftover.exists():
            leftover.unlink()
    Path(str(principal) + "-wal").write_bytes(wal_bytes)

    with pytest.raises(sqlite_runtime.SQLiteSidecarConflictError):
        sqlite_runtime.open_writer(principal)
    with pytest.raises(sqlite_runtime.SQLiteSidecarConflictError):
        sqlite_runtime.open_reader(principal)

    # La vía de escape autorizada también aplica a la lectura.
    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "1")
    conn = sqlite_runtime.open_reader(principal, consumer="lectura_forzada")
    try:
        conn.execute("SELECT COUNT(*) FROM t").fetchone()
    finally:
        conn.close()
