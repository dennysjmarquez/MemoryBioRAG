"""Regresión pendiente: pérdida de WAL tras un commit y caída del escritor.

Solo usa una base temporal. El xfail estricto documenta el bloqueante hasta
que el guardián pueda distinguir una desaparición de un checkpoint verificado.
No constituye una prueba de recuperación ni autoriza borrar un WAL real.
"""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from core.sqlite import constants
from core.sqlite_runtime import SQLiteSidecarConflictError, open_reader


@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="Pendiente: detectar WAL registrado que desapareció sin checkpoint verificado",
)
def test_no_abrir_silenciosamente_si_desaparece_wal_con_commit(tmp_path, monkeypatch):
    """Un principal estructuralmente válido no prueba que conserve los commits."""
    monkeypatch.setattr(constants, "_effective_sqlite_version", lambda: (3, 51, 3))
    db = tmp_path / "memoria.db"
    inicial = sqlite3.connect(db)
    try:
        inicial.execute("PRAGMA journal_mode=WAL")
        inicial.execute("CREATE TABLE recuerdos (texto TEXT NOT NULL)")
        inicial.commit()
    finally:
        inicial.close()

    # El proceso cae sin cerrar la conexión después de confirmar su escritura.
    script = """
import os, sys
from core.sqlite import constants
from core.sqlite_runtime import open_writer
constants._effective_sqlite_version = lambda: (3, 51, 3)
conn = open_writer(sys.argv[1])
conn.execute("INSERT INTO recuerdos VALUES ('recuerdo confirmado')")
conn.commit()
os._exit(0)
"""
    result = subprocess.run([sys.executable, "-c", script, str(db)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    wal = Path(str(db) + "-wal")
    assert wal.exists() and wal.stat().st_size > 0
    estado = json.loads(Path(str(db) + ".biorag-pair-state").read_text())
    assert estado["wal_salt"] and estado["wal_content"]

    # Simula exclusivamente en el directorio temporal la eliminación accidental.
    os.unlink(wal)
    with pytest.raises(SQLiteSidecarConflictError):
        conexion = open_reader(db)
        conexion.close()
