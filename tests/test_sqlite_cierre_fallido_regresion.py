"""Regresión del estado de una instancia cuando falla el cierre.

Solo usa fixtures temporales. La inyección en el checkpoint ilustra el ciclo
actual; no simula una API de backup o de publicación que aún no existe.
"""

import sqlite3

import pytest

from test_sqlite_cierre_tras_checkout import motor_tras_checkout_forzado


class CierreDeclaradoAntesDeTerminar(AssertionError):
    """El motor se marcó cerrado aunque falló una etapa previa al cierre."""


@pytest.mark.xfail(
    strict=True,
    raises=CierreDeclaradoAntesDeTerminar,
    reason="El cierre actual marca la instancia cerrada antes de completar sus etapas",
)
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
        if motor._closed:
            raise CierreDeclaradoAntesDeTerminar("_closed=True con conexiones aún abiertas")
    finally:
        # Limpieza exclusiva de la fixture. No modela recuperación de producción.
        for conn in conexiones:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        motor._closed = True
