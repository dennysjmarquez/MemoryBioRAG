"""Sonda de backup con conexiones reales del motor en varios hilos.

Es una prueba exploratoria: un backup que pasa estos controles no acredita por
sí mismo la generación ante reemplazos in-place, sidecars modificados o procesos
externos. BioRAG todavía no selecciona ni publica backups de recuperación.
"""

import hashlib
import sqlite3
import time

import pytest

from test_sqlite_cierre_tras_checkout import motor_tras_checkout_forzado


@pytest.mark.parametrize("motor_tras_checkout_forzado", [True], indirect=True)
def test_backup_desde_dos_conexiones_despues_de_checkout(motor_tras_checkout_forzado, tmp_path):
    """Ambas conexiones deben ver el último commit en este escenario aislado."""
    motor, db, wal, _principal_a, contenido, hash_b, _tmp_path = motor_tras_checkout_forzado
    assert wal.read_bytes() == contenido
    assert len(motor._connections) == 2
    for indice, fuente in enumerate(motor._connections):
        assert not fuente.in_transaction
        destino = sqlite3.connect(tmp_path / f"backup-{indice}.db")
        limite = time.monotonic() + 10

        def progreso(_status, _remaining, _total):
            if time.monotonic() > limite:
                raise TimeoutError("backup de prueba excedió diez segundos")

        try:
            fuente.backup(destino, pages=64, progress=progreso, sleep=0.01)
            assert destino.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert destino.execute("SELECT texto FROM recuerdos ORDER BY texto").fetchall() == [
                ("commit de otro hilo",), ("confirmado en A",), ("rama A",)
            ]
        finally:
            destino.close()
        assert hashlib.sha256(db.read_bytes()).digest() == hash_b
        assert wal.read_bytes() == contenido
