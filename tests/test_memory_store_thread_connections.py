"""Regresión de concurrencia y lifecycle sobre instancias temporales del motor."""

import sqlite3
import threading
import time

from core.memory_store import SQLiteMemoryBioRAG


def test_hilos_no_comparten_cursor_ni_resultados(tmp_path):
    cerebro = SQLiteMemoryBioRAG(str(tmp_path / "cursores.db"))
    first_ready = threading.Event()
    second_ready = threading.Event()
    first_fetched = threading.Event()
    refs = {}
    rows = {}

    def first_worker():
        conn = cerebro.conn
        cursor = cerebro.cursor
        refs["first"] = (conn, cursor)
        cursor.execute("SELECT 101")
        first_ready.set()
        assert second_ready.wait(5)
        rows["first"] = cursor.fetchone()[0]
        first_fetched.set()

    def second_worker():
        assert first_ready.wait(5)
        conn = cerebro.conn
        cursor = cerebro.cursor
        refs["second"] = (conn, cursor)
        cursor.execute("SELECT 202")
        second_ready.set()
        assert first_fetched.wait(5)
        rows["second"] = cursor.fetchone()[0]

    threads = [threading.Thread(target=first_worker), threading.Thread(target=second_worker)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

        assert all(not thread.is_alive() for thread in threads)
        assert refs["first"][0] is not refs["second"][0]
        assert refs["first"][1] is not refs["second"][1]
        assert rows == {"first": 101, "second": 202}
    finally:
        cerebro.cerrar_sistema()


def test_memory_database_conserva_conexion_compartida_entre_hilos():
    cerebro = SQLiteMemoryBioRAG(":memory:")
    main_connection = cerebro.conn
    worker_connections = []

    def worker():
        worker_connections.append(cerebro.conn)
        cerebro.cursor.execute("CREATE TABLE memory_thread_fixture (value INTEGER)")
        cerebro.cursor.execute("INSERT INTO memory_thread_fixture VALUES (7)")
        cerebro.conn.commit()

    thread = threading.Thread(target=worker)
    try:
        thread.start()
        thread.join(5)
        assert not thread.is_alive()
        assert worker_connections == [main_connection]
        assert cerebro.cursor.execute(
            "SELECT value FROM memory_thread_fixture"
        ).fetchone()[0] == 7
    finally:
        cerebro.cerrar_sistema()


def test_estado_last_es_aislado_por_hilo(tmp_path):
    cerebro = SQLiteMemoryBioRAG(str(tmp_path / "estado-hilo.db"))
    cerebro.last_todos = [("main",)]
    worker_values = []

    def worker():
        cerebro.last_todos = [("worker",)]
        worker_values.append(cerebro.last_todos)

    thread = threading.Thread(target=worker)
    try:
        thread.start()
        thread.join(5)
        assert not thread.is_alive()
        assert worker_values == [[("worker",)]]
        assert cerebro.last_todos == [("main",)]
    finally:
        cerebro.cerrar_sistema()


def test_escrituras_concurrentes_en_una_instancia_no_pierden_filas(tmp_path):
    db_path = tmp_path / "writes.db"
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    cerebro.cursor.execute(
        "CREATE TABLE concurrent_fixture (worker INTEGER, seq INTEGER, PRIMARY KEY(worker, seq))"
    )
    cerebro.conn.commit()

    workers = 6
    rows_per_worker = 60
    barrier = threading.Barrier(workers)
    failures = []

    def write_batch(worker_id):
        try:
            cursor = cerebro.cursor
            conn = cerebro.conn
            barrier.wait(timeout=5)
            cursor.executemany(
                "INSERT INTO concurrent_fixture(worker, seq) VALUES (?, ?)",
                [(worker_id, seq) for seq in range(rows_per_worker)],
            )
            conn.commit()
        except Exception as exc:  # el test registra errores de cualquier hilo
            failures.append(exc)

    threads = [threading.Thread(target=write_batch, args=(worker,)) for worker in range(workers)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)

        assert all(not thread.is_alive() for thread in threads)
        assert failures == []
        verify = sqlite3.connect(db_path)
        try:
            assert verify.execute("SELECT COUNT(*) FROM concurrent_fixture").fetchone()[0] == (
                workers * rows_per_worker
            )
            assert verify.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            verify.close()
    finally:
        cerebro.cerrar_sistema()


def test_cerrar_espera_a_que_termine_una_operacion_en_vuelo(tmp_path):
    cerebro = SQLiteMemoryBioRAG(str(tmp_path / "lifecycle.db"))
    entered = threading.Event()
    release = threading.Event()
    close_done = threading.Event()

    def hold_operation():
        with cerebro._operation_lease():
            entered.set()
            assert release.wait(5)

    worker = threading.Thread(target=hold_operation)
    closer = threading.Thread(target=lambda: (cerebro.cerrar_sistema(), close_done.set()))

    worker.start()
    try:
        assert entered.wait(5)
        closer.start()
        time.sleep(0.05)
        assert not close_done.is_set(), "el cierre adelantó a una operación activa"
        release.set()
        worker.join(5)
        closer.join(5)
        assert not worker.is_alive()
        assert not closer.is_alive()
        assert close_done.is_set()
    finally:
        release.set()
        if worker.is_alive():
            worker.join(5)
        if closer.ident is not None and closer.is_alive():
            closer.join(5)
