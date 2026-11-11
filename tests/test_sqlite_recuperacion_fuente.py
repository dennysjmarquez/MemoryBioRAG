"""Comprobaciones de evidencia para una futura recuperación de generación.

No selecciona fuentes ni publica backups de producción. Las conexiones y el
checkout proceden de la fixture temporal compartida con los ensayos WAL.
"""

import pytest

from core.sqlite import pair_guard
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


def test_alteracion_del_wal_conserva_sal_pero_invalida_la_evidencia(motor_tras_checkout_forzado):
    """Una sal igual no acredita un WAL que fue modificado tras el checkout."""
    motor, db, wal, _principal_a, contenido, _hash_b, _tmp_path = motor_tras_checkout_forzado
    registrado = pair_guard._recorded_pair_state(db)
    assert registrado is not None
    sal = pair_guard._wal_header_salt(str(wal))
    digest = pair_guard._wal_content_digest(str(wal))
    assert sal and digest
    assert registrado["wal_salt"] == sal
    assert registrado["wal_content"] == digest
    alterado = bytearray(contenido)
    alterado[-1] ^= 1
    try:
        # Solo en la fixture temporal y sin escritores concurrentes.
        wal.write_bytes(alterado)
        assert pair_guard._wal_header_salt(str(wal)) == sal
        assert pair_guard._wal_content_digest(str(wal)) != digest
    finally:
        wal.write_bytes(contenido)
