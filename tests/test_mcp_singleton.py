"""Instancia persistente MCP: no reconstruir la corteza por tool."""
import threading
import time

from core.memory_service import get_cerebro, reset_cerebro


def test_get_cerebro_misma_instancia(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_PATH", str(tmp_path / "s.db"))
    reset_cerebro()
    a = get_cerebro()
    b = get_cerebro()
    assert a is b
    a.percibir_corto_plazo("nodo_s", "contenido persistente bio rag")
    a.consolidar_concepto("nodo_s")
    t0 = time.perf_counter()
    c = get_cerebro()
    dt_ms = (time.perf_counter() - t0) * 1000
    assert c is a
    assert dt_ms < 50
    reset_cerebro()


def test_cerrar_no_mata_singleton(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_PATH", str(tmp_path / "s2.db"))
    reset_cerebro()
    c = get_cerebro()
    c.cerrar_sistema()
    c.cursor.execute("SELECT 1")
    assert c.cursor.fetchone()[0] == 1
    reset_cerebro()


def test_hilos_comparten_instancia(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_PATH", str(tmp_path / "s3.db"))
    reset_cerebro()
    ids = []

    def f():
        ids.append(id(get_cerebro()))

    ts = [threading.Thread(target=f) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(set(ids)) == 1
    reset_cerebro()
