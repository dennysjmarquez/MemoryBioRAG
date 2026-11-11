"""Pruebas aisladas de límites del backup SQLite; no son política de producción.

Ejercitan conexiones SQLite temporales directamente. El guardián aún no
selecciona conexiones ni crea artefactos de recuperación al cerrar.
"""

import sqlite3
import subprocess
import sys

import pytest


def test_backup_desde_conexion_cerrada_no_es_fuente_valida(tmp_path):
    """Una conexión cerrada no puede producir un backup acreditable."""
    fuente = sqlite3.connect(tmp_path / "fuente.db")
    fuente.execute("CREATE TABLE recuerdos (valor TEXT)")
    fuente.commit()
    fuente.close()
    destino = sqlite3.connect(tmp_path / "destino.db")
    try:
        with pytest.raises(sqlite3.ProgrammingError):
            fuente.backup(destino)
    finally:
        destino.close()


def test_backup_con_transaccion_escritora_activa_no_termina_normalmente(tmp_path):
    """Una escritura pendiente debe descartarse como fuente; no bloquearse sin límite."""
    guion = r'''
import sqlite3, sys, time
fuente = sqlite3.connect(sys.argv[1])
fuente.execute("CREATE TABLE recuerdos (valor TEXT)")
fuente.commit()
fuente.execute("INSERT INTO recuerdos VALUES ('pendiente')")
assert fuente.in_transaction
objetivo = sqlite3.connect(sys.argv[2])
limite = time.monotonic() + 0.2

def progreso(estado, restante, total):
    if time.monotonic() >= limite:
        raise TimeoutError("backup detenido")
try:
    fuente.backup(objetivo, pages=1, progress=progreso, sleep=0.01)
except TimeoutError:
    pass
else:
    raise AssertionError("el backup terminó con transacción de escritura activa")
finally:
    objetivo.close()
    fuente.rollback()
    fuente.close()
'''
    result = subprocess.run(
        [sys.executable, "-c", guion, str(tmp_path / "fuente.db"), str(tmp_path / "destino.db")],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(tmp_path / "fuente.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM recuerdos").fetchone()[0] == 0
