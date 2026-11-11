"""Regresión del estado de una instancia cuando falla el cierre.

Solo usa fixtures temporales. La inyección en el checkpoint ilustra el ciclo
actual; no simula una API de backup o de publicación que aún no existe.
"""

import sqlite3

import pytest

from test_sqlite_cierre_tras_checkout import motor_tras_checkout_forzado


def test_fallo_en_etapa_previa_no_debe_declarar_motor_cerrado(motor_tras_checkout_forzado, monkeypatch):
    """Una etapa fallida no debe declarar cerrado el motor con handles vivos."""
    motor, _db, _wal, _principal_a, _contenido, _hash_b, _tmp_path = motor_tras_checkout_forzado
    conexiones = tuple(motor._connections)

    def fallo(_connections):
        raise OSError("fallo inyectado antes de cerrar conexiones")

    monkeypatch.setattr(motor, "_consolidar_antes_de_cerrar", fallo)
    try:
        with pytest.raises(OSError, match="fallo inyectado"):
            motor.cerrar_sistema()
        # Verificar el handle directamente, sin consultar ni modificar el par.
        for conn in conexiones:
            assert isinstance(conn.in_transaction, bool)
        assert not motor._closed
        assert motor._close_failed
        with pytest.raises(RuntimeError, match="cierre anterior falló"):
            motor.conn.execute("SELECT 1")
    finally:
        # Limpieza exclusiva de la fixture. No modela recuperación de producción.
        for conn in conexiones:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        motor._closed = True
