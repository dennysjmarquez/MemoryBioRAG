"""La barrera de cierre debe incluir handles DB-API y creación de conexiones."""

import threading

from core.memory_store import SQLiteMemoryBioRAG


def test_cierre_espera_a_lectura_dbapi_en_vuelo(tmp_path):
    motor = SQLiteMemoryBioRAG(str(tmp_path / "barrera.db"))
    conn = motor.conn
    entrado = threading.Event()
    soltar = threading.Event()
    cerrado = threading.Event()
    errores = []

    def pausa():
        entrado.set()
        if not soltar.wait(10):
            raise RuntimeError("la prueba no liberó la consulta")
        return 42

    conn.create_function("pausa_prueba", 0, pausa)

    def consultar():
        try:
            conn.execute("SELECT pausa_prueba()").fetchone()
        except Exception as exc:
            errores.append(exc)

    consulta = threading.Thread(target=consultar)
    cierre = threading.Thread(target=lambda: (motor.cerrar_sistema(), cerrado.set()))
    consulta.start()
    try:
        assert entrado.wait(5)
        cierre.start()
        # Al entrar en closing la operación DB-API debe seguir siendo activa.
        with motor._lifecycle_condition:
            assert motor._lifecycle_condition.wait_for(lambda: motor._closing, timeout=5)
            assert motor._active_operations > 0
        assert not cerrado.is_set()
        soltar.set()
        consulta.join(10)
        cierre.join(10)
        assert not consulta.is_alive() and not cierre.is_alive()
        assert cerrado.is_set()
        # fetchone puede comenzar después del cierre y fallar sin falso éxito.
        assert all(isinstance(e, RuntimeError) for e in errores)
    finally:
        soltar.set()
        consulta.join(10)
        if cierre.ident is not None:
            cierre.join(10)
        if not motor._closed:
            motor.cerrar_sistema()


def test_nuevo_handle_no_abre_conexion_durante_cierre(tmp_path, monkeypatch):
    motor = SQLiteMemoryBioRAG(str(tmp_path / "creacion.db"))
    entrado = threading.Event()
    soltar = threading.Event()
    peticion = threading.Event()
    resultados = []
    original = motor._consolidar_antes_de_cerrar

    def checkpoint(conns):
        entrado.set()
        if not soltar.wait(10):
            raise TimeoutError("la prueba no liberó el cierre")
        return original(conns)

    monkeypatch.setattr(motor, "_consolidar_antes_de_cerrar", checkpoint)
    cierre = threading.Thread(target=motor.cerrar_sistema)

    def crear():
        peticion.set()
        try:
            motor.conn.execute("SELECT 1")
            resultados.append("consulta ejecutada")
        except RuntimeError:
            resultados.append("cerrado")

    hilo = threading.Thread(target=crear)
    cierre.start()
    try:
        assert entrado.wait(5)
        iniciales = tuple(motor._connections)
        hilo.start()
        assert peticion.wait(5)
        # La barrera no debe crear ni registrar un handle durante el cierre.
        with motor._lifecycle_condition:
            assert motor._closing
            assert tuple(motor._connections) == iniciales
        soltar.set()
        cierre.join(10)
        hilo.join(10)
        assert not cierre.is_alive() and not hilo.is_alive()
        assert resultados == ["cerrado"]
        assert tuple(motor._connections) == iniciales
        for conn in iniciales:
            try:
                conn.execute("SELECT 1")
            except Exception as exc:
                assert "closed" in str(exc).lower()
            else:
                raise AssertionError("quedó una conexión viva después del cierre")
    finally:
        soltar.set()
        cierre.join(10)
        if hilo.ident is not None:
            hilo.join(10)
        if not motor._closed:
            motor.cerrar_sistema()
