"""La barrera de cierre debe incluir handles DB-API y creación de conexiones."""

import sqlite3
import threading

import pytest

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
        hilo.join(5)
        assert not hilo.is_alive() and resultados == ["cerrado"]
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


def test_recursos_dbapi_no_controlados_se_rechazan(tmp_path):
    motor = SQLiteMemoryBioRAG(str(tmp_path / "recursos.db"))
    try:
        conn = motor.conn
        with pytest.raises(NotImplementedError, match="blobopen"):
            conn.blobopen("tabla", "contenido", 1)
        with pytest.raises(NotImplementedError, match="iterdump"):
            conn.iterdump()
    finally:
        motor.cerrar_sistema()


def test_callback_dbapi_no_reentra_motor_ni_cierra_desde_operacion(tmp_path):
    motor = SQLiteMemoryBioRAG(str(tmp_path / "callback.db"))
    rechazos = []

    def callback():
        for accion in (lambda: motor.consolidar_concepto("x"), motor.cerrar_sistema):
            try:
                accion()
            except RuntimeError as exc:
                rechazos.append(str(exc))
        return 1

    try:
        motor.conn.create_function("callback_seguro", 0, callback)
        with motor._operation_lease():
            assert motor.conn.execute("SELECT callback_seguro()").fetchone() == (1,)
        assert len(rechazos) == 2
        assert "DB-API activa" in rechazos[0]
        assert "operación activa" in rechazos[1]
    finally:
        motor.cerrar_sistema()


def test_setter_no_registra_handle_en_cierre(tmp_path, monkeypatch):
    motor = SQLiteMemoryBioRAG(str(tmp_path / "setter.db"))
    externo = sqlite3.connect(":memory:", check_same_thread=False)
    checkpoint_iniciado = threading.Event()
    soltar = threading.Event()
    resultados = []
    original = motor._consolidar_antes_de_cerrar

    def checkpoint(conns):
        checkpoint_iniciado.set()
        if not soltar.wait(10):
            raise TimeoutError("no se liberó el cierre")
        return original(conns)

    def asignar():
        try:
            motor.conn = externo
            resultados.append("asignado")
        except RuntimeError:
            resultados.append("cerrado")

    monkeypatch.setattr(motor, "_consolidar_antes_de_cerrar", checkpoint)
    cierre = threading.Thread(target=motor.cerrar_sistema)
    setter = threading.Thread(target=asignar)
    cierre.start()
    try:
        assert checkpoint_iniciado.wait(5)
        originales = tuple(motor._connections)
        setter.start()
        setter.join(5)
        assert not setter.is_alive() and resultados == ["cerrado"]
        assert tuple(motor._connections) == originales
        soltar.set()
        cierre.join(10)
        setter.join(10)
        assert not cierre.is_alive() and not setter.is_alive()
        assert resultados == ["cerrado"]
        assert tuple(motor._connections) == originales
    finally:
        soltar.set()
        cierre.join(10)
        if setter.ident is not None:
            setter.join(10)
        externo.close()
        if not motor._closed:
            motor.cerrar_sistema()


def test_callback_y_auxiliar_no_se_bloquean_durante_cierre(tmp_path, monkeypatch):
    """El auxiliar rechaza la llamada, así el callback termina y se drena."""
    motor = SQLiteMemoryBioRAG(str(tmp_path / "ciclo.db"))
    conn = motor.conn
    callback_iniciado = threading.Event()
    cierre_espera = threading.Event()
    auxiliar_finalizado = threading.Event()
    resultados = []
    original_wait = motor._lifecycle_condition.wait

    def wait_observado(timeout=None):
        if threading.current_thread() is cierre and motor._active_operations:
            cierre_espera.set()
        return original_wait(timeout)

    monkeypatch.setattr(motor._lifecycle_condition, "wait", wait_observado)

    def auxiliar():
        try:
            conn.execute("SELECT 1")
            resultados.append("ejecutado")
        except RuntimeError:
            resultados.append("rechazado")
        finally:
            auxiliar_finalizado.set()

    def callback():
        callback_iniciado.set()
        if not cierre_espera.wait(5):
            raise TimeoutError("el cierre no empezó a drenar")
        threading.Thread(target=auxiliar, daemon=True).start()
        if not auxiliar_finalizado.wait(5):
            raise TimeoutError("el auxiliar quedó bloqueado")
        return 1

    conn.create_function("prueba_ciclo", 0, callback)
    errores = []

    def consulta():
        try:
            conn.execute("SELECT prueba_ciclo()").fetchone()
        except (RuntimeError, sqlite3.Error) as exc:
            errores.append(exc)

    trabajador = threading.Thread(target=consulta)
    cierre = threading.Thread(target=motor.cerrar_sistema)
    trabajador.start()
    try:
        assert callback_iniciado.wait(5)
        cierre.start()
        assert auxiliar_finalizado.wait(5), "el auxiliar quedó bloqueado"
        trabajador.join(10)
        cierre.join(10)
        assert not trabajador.is_alive() and not cierre.is_alive()
        assert resultados == ["rechazado"]
        assert motor._closed
    finally:
        trabajador.join(10)
        if cierre.ident is not None:
            cierre.join(10)
        if not motor._closed:
            motor.cerrar_sistema()


def test_interrupt_llega_a_sqlite_durante_drenaje(tmp_path, monkeypatch):
    motor = SQLiteMemoryBioRAG(str(tmp_path / "interrupt.db"))
    conn = motor.conn
    progreso_iniciado = threading.Event()
    soltar = threading.Event()
    drenando = threading.Event()
    original_wait = motor._lifecycle_condition.wait
    errores = []

    def progreso():
        progreso_iniciado.set()
        if not soltar.wait(10):
            raise TimeoutError("no se liberó la consulta")
        return 0

    def wait_observado(timeout=None):
        if threading.current_thread() is cierre and motor._active_operations:
            drenando.set()
        return original_wait(timeout)

    conn.set_progress_handler(progreso, 1)
    monkeypatch.setattr(motor._lifecycle_condition, "wait", wait_observado)

    def consulta():
        try:
            conn.execute("SELECT 1").fetchall()
        except (sqlite3.Error, RuntimeError) as exc:
            errores.append(exc)

    trabajador = threading.Thread(target=consulta)
    cierre = threading.Thread(target=motor.cerrar_sistema)
    trabajador.start()
    try:
        assert progreso_iniciado.wait(5)
        cierre.start()
        assert drenando.wait(5)
        conn.interrupt()
        assert not soltar.is_set(), "interrupt retornó antes de liberar la consulta"
        soltar.set()
        trabajador.join(10)
        cierre.join(10)
        assert not trabajador.is_alive() and not cierre.is_alive()
        assert len(errores) == 1
        causa = errores[0].__cause__ or errores[0]
        assert isinstance(causa, sqlite3.OperationalError) and "interrupt" in str(causa).lower()
        assert motor._closed
    finally:
        soltar.set()
        trabajador.join(10)
        if cierre.ident is not None:
            cierre.join(10)
        if not motor._closed:
            motor.cerrar_sistema()


def test_drenaje_agotado_no_cierra_y_permite_reintento(tmp_path, monkeypatch):
    import core.memory_store as memory_store

    motor = SQLiteMemoryBioRAG(str(tmp_path / "timeout.db"))
    entrado = threading.Event()
    soltar = threading.Event()
    conexiones = tuple(motor._connections)
    monkeypatch.setattr(memory_store, "_CIERRE_DRENAJE_SEGUNDOS", 0.05)

    def trabajar():
        with motor._operation_lease():
            entrado.set()
            assert soltar.wait(5)

    hilo = threading.Thread(target=trabajar)
    hilo.start()
    try:
        assert entrado.wait(5)
        with pytest.raises(TimeoutError, match="No terminó el drenaje"):
            motor.cerrar_sistema()
        assert not motor._closed and motor._close_failed and not motor._closing
        assert all(isinstance(conn.in_transaction, bool) for conn in conexiones)
        with pytest.raises(RuntimeError, match="cierre anterior falló"):
            motor.conn
        soltar.set()
        hilo.join(5)
        assert not hilo.is_alive()
        motor.cerrar_sistema()
        assert motor._closed
    finally:
        soltar.set()
        hilo.join(5)
        if not motor._closed:
            motor.cerrar_sistema()
