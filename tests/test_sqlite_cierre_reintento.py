"""Estado de cierre y reintento del motor ante fallos controlados."""

import threading

import pytest

from core.memory_store import SQLiteMemoryBioRAG


def test_reintento_tras_cierre_parcial_no_reutiliza_conexiones_cerradas(tmp_path, monkeypatch):
    """Un fallo parcial bloquea operaciones y reintenta solo handles pendientes."""
    motor = SQLiteMemoryBioRAG(str(tmp_path / "memoria.db"))
    reales = tuple(motor._connections)
    llamadas_checkpoint = []

    class ConexionControlada:
        def __init__(self, falla=False):
            self.falla = falla
            self.llamadas = 0

        def close(self):
            self.llamadas += 1
            if self.falla:
                self.falla = False
                raise OSError("fallo de cierre inyectado")

    primera, segunda = ConexionControlada(), ConexionControlada(falla=True)
    motor._connections[:] = [primera, segunda]
    monkeypatch.setattr(motor, "_consolidar_antes_de_cerrar", lambda conns: llamadas_checkpoint.append(conns))
    try:
        with pytest.raises(OSError, match="fallo de cierre"):
            motor.cerrar_sistema()
        assert not motor._closed and motor._close_failed
        assert motor._close_pending == [segunda]
        assert primera.llamadas == segunda.llamadas == 1
        with pytest.raises(RuntimeError, match="cierre anterior falló"):
            motor._begin_operation()
        motor.cerrar_sistema()
        assert motor._closed and not motor._close_failed
        assert primera.llamadas == 1 and segunda.llamadas == 2
        assert len(llamadas_checkpoint) == 1
    finally:
        for conn in reales:
            conn.close()


def test_cierre_concurrente_reintenta_si_primer_cierre_falla(tmp_path, monkeypatch):
    """Quien espera otro cierre no debe declarar éxito tras su fallo."""
    motor = SQLiteMemoryBioRAG(str(tmp_path / "memoria.db"))
    iniciado = threading.Event()
    soltar = threading.Event()
    resultados = []
    contador = []
    original = motor._consolidar_antes_de_cerrar

    def checkpoint(conns):
        contador.append(1)
        if len(contador) == 1:
            iniciado.set()
            if not soltar.wait(5):
                raise TimeoutError("la prueba no liberó el primer cierre")
            raise OSError("fallo inicial")
        return original(conns)

    monkeypatch.setattr(motor, "_consolidar_antes_de_cerrar", checkpoint)

    def cerrar():
        try:
            motor.cerrar_sistema()
            resultados.append("cerrado")
        except OSError:
            resultados.append("falló")

    primero = threading.Thread(target=cerrar)
    segundo = threading.Thread(target=cerrar)
    primero.start()
    try:
        assert iniciado.wait(5)
        segundo.start()
        soltar.set()
        primero.join(10)
        segundo.join(10)
        assert not primero.is_alive() and not segundo.is_alive()
        assert sorted(resultados) == ["cerrado", "falló"]
        assert len(contador) == 2 and motor._closed
    finally:
        soltar.set()
        primero.join(10)
        if segundo.ident is not None:
            segundo.join(10)
        if not motor._closed:
            motor.cerrar_sistema()
