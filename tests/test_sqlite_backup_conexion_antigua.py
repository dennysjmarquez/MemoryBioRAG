"""Ensayo aislado de backup desde la conexión viva tras checkout forzado.

Solo demuestra la operación SQLite sobre la fixture; BioRAG aún no produce
un artefacto duradero ni ha implementado recuperación automática.
"""

import hashlib
import sqlite3
import time

from test_sqlite_cierre_tras_checkout import motor_tras_checkout_forzado


def test_backup_sqlite_de_conexion_antigua_tras_checkout(motor_tras_checkout_forzado, tmp_path):
    """Una conexión vieja puede generar una copia recuperable sin tocar B."""
    motor, db, wal, _principal_a, contenido, hash_b, _tmp_path = motor_tras_checkout_forzado
    assert wal.read_bytes() == contenido
    destino = tmp_path / "backup-aislado.db"
    target = sqlite3.connect(destino)
    limite = time.monotonic() + 10

    def progreso(_status, _remaining, _total):
        if time.monotonic() > limite:
            raise TimeoutError("backup de prueba excedió diez segundos")

    try:
        # La fachada guardada rechaza la generación sustituida; se ensaya la
        # conexión SQLite original aislada, sin cambiar la política de apertura.
        motor._connections[0].backup(target, pages=64, progress=progreso, sleep=0.01)
    finally:
        target.close()

    verificacion = sqlite3.connect(destino)
    try:
        assert verificacion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert verificacion.execute("SELECT texto FROM recuerdos ORDER BY texto").fetchall() == [
            ("confirmado en A",), ("rama A",)
        ]
    finally:
        verificacion.close()
    assert hashlib.sha256(db.read_bytes()).digest() == hash_b
    assert wal.read_bytes() == contenido
    motor.cerrar_sistema()
    assert hashlib.sha256(db.read_bytes()).digest() == hash_b
    verificacion = sqlite3.connect(destino)
    try:
        assert verificacion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert verificacion.execute("SELECT texto FROM recuerdos ORDER BY texto").fetchall() == [
            ("confirmado en A",), ("rama A",)
        ]
    finally:
        verificacion.close()
