"""Comprobaciones de evidencia para una futura recuperación de generación.

No selecciona fuentes ni publica backups de producción. Las conexiones y el
checkout proceden de la fixture temporal compartida con los ensayos WAL.
"""

import pytest

from test_sqlite_cierre_tras_checkout import motor_tras_checkout_forzado


@pytest.mark.parametrize("motor_tras_checkout_forzado", [True], indirect=True)
def test_instantaneas_por_conexion_no_son_un_registro_global(motor_tras_checkout_forzado):
    """Dos handles del mismo motor pueden tener épocas registradas diferentes."""
    motor, _db, _wal, _principal_a, _contenido, _hash_b, _tmp_path = motor_tras_checkout_forzado
    conexiones = tuple(motor._connections)
    assert len(conexiones) == 2
    snapshots = [motor._connection_snapshots.get(id(conn)) for conn in conexiones]
    assert all(snapshot is not None and snapshot[0] is conn for snapshot, conn in zip(snapshots, conexiones))
    epocas = [snapshot[3] for snapshot in snapshots]
    assert epocas[1] > epocas[0], f"se esperaba snapshot anterior en el primer handle: {epocas}"
