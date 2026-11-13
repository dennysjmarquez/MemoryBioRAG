"""Regresión del guardián ante pérdida de WAL, solo con bases temporales.

El xfail estricto documenta un bloqueante; no constituye una reparación ni
una prueba de apagón del sistema, y no autoriza tocar un WAL real.
"""

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from core.sqlite import constants, pair_guard
from core.sqlite_runtime import SQLiteSidecarConflictError, open_reader, open_writer


@pytest.fixture
def base_con_commit_en_wal(tmp_path, monkeypatch):
    """Prepara esquema consolidado y un commit en WAL de un proceso caído."""
    # Solo simula la política de versión; no verifica el runtime corregido.
    monkeypatch.setattr(constants, "_effective_sqlite_version", lambda: (3, 51, 3))
    monkeypatch.setenv("BIORAG_SQLITE_GUARD", "1")
    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "0")
    db = tmp_path / "memoria.db"
    inicial = sqlite3.connect(db)
    try:
        assert inicial.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        inicial.execute("CREATE TABLE recuerdos (texto TEXT NOT NULL)")
        inicial.commit()
        assert inicial.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone() == (0, 0, 0)
    finally:
        inicial.close()

    # os._exit reproduce caída de proceso, no apagón ni fallo de filesystem.
    script = """
import os, sys
from core.sqlite import constants
from core.sqlite_runtime import open_writer
constants._effective_sqlite_version = lambda: (3, 51, 3)
conn = open_writer(sys.argv[1])
assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
conn.execute("PRAGMA wal_autocheckpoint=0")
assert conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0] == 0
conn.execute("PRAGMA synchronous=FULL")
assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
conn.execute("INSERT INTO recuerdos VALUES ('recuerdo confirmado')")
conn.commit()
os._exit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(db)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    wal = Path(str(db) + "-wal")
    assert wal.exists() and wal.stat().st_size > 0
    estado = json.loads(Path(str(db) + ".biorag-pair-state").read_text())
    assert estado["wal_salt"] == pair_guard._wal_header_salt(str(wal))
    assert estado["wal_content"] == pair_guard._wal_content_digest(str(wal))
    assert estado["wal_salt"] and estado["wal_content"]
    return db


def test_recuerdo_existe_en_copia_del_par_pero_no_del_principal(base_con_commit_en_wal, tmp_path):
    """El WAL contiene el recuerdo; el principal aislado pasa integridad sin él."""
    db = base_con_commit_en_wal
    con_wal = tmp_path / "con-wal.db"
    sin_wal = tmp_path / "sin-wal.db"
    # El proceso ya terminó: se copian archivos de la fixture, no una base activa.
    shutil.copyfile(db, con_wal)
    shutil.copyfile(str(db) + "-wal", str(con_wal) + "-wal")
    shutil.copyfile(db, sin_wal)
    for copia, esperado in ((con_wal, [("recuerdo confirmado",)]), (sin_wal, [])):
        conn = sqlite3.connect(copia)
        try:
            assert conn.execute("SELECT texto FROM recuerdos").fetchall() == esperado
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()


@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="Pendiente: detectar WAL registrado que desapareció sin checkpoint verificado",
)
def test_no_abrir_silenciosamente_si_desaparece_wal_con_commit(base_con_commit_en_wal):
    """La ausencia inesperada no debe hacerse pasar por una apertura segura."""
    db = base_con_commit_en_wal
    os.unlink(str(db) + "-wal")  # Solo en la fixture temporal.
    with pytest.raises(SQLiteSidecarConflictError):
        conexion = open_reader(db)
        conexion.close()


def test_checkpoint_normal_conserva_recuerdo_al_reabrir(tmp_path, monkeypatch):
    """Control: no se debe rechazar automáticamente todo WAL desaparecido."""
    monkeypatch.setattr(constants, "_effective_sqlite_version", lambda: (3, 51, 3))
    monkeypatch.setenv("BIORAG_SQLITE_GUARD", "1")
    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "0")
    db = tmp_path / "checkpoint.db"
    conn = open_writer(db)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        conn.execute("PRAGMA wal_autocheckpoint=0")
        assert conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0] == 0
        conn.execute("CREATE TABLE recuerdos (texto TEXT NOT NULL)")
        conn.execute("INSERT INTO recuerdos VALUES ('conservado')")
        conn.commit()
        wal = Path(str(db) + "-wal")
        assert wal.stat().st_size > 0
        estado = json.loads(Path(str(db) + ".biorag-pair-state").read_text())
        assert estado["wal_salt"] and estado["wal_salt"] == pair_guard._wal_header_salt(str(wal))
        assert estado["wal_content"] and estado["wal_content"] == pair_guard._wal_content_digest(str(wal))
        assert estado["main"]["sha256"] == pair_guard._file_forensics(str(db))["sha256"]
        assert conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone() == (0, 0, 0)
    finally:
        conn.close()
    wal = Path(str(db) + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    lector = open_reader(db)
    try:
        assert lector.execute("SELECT texto FROM recuerdos").fetchall() == [("conservado",)]
    finally:
        lector.close()
