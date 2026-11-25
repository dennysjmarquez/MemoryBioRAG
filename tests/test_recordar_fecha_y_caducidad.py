"""recordar entrega la fecha real de cada recuerdo y marca la caducidad (stale).

Regresión: la consulta de antigüedad apuntaba a `categorias`/`nombre` (no
existen; son `categories`/`name`) y un `except: pass` la ocultaba. Resultado:
fecha_legible=None, edad_dias=0 y stale=False en TODOS los resultados, y el
principio de caducidad temporal (90 días; protegidas Principle, Profile,
Personal, Relation) nunca actuaba.
"""
import json
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).resolve().parents[1] / "snapshots" / "qa_escape_qcr_20260811.db"
DIA = 86400


def _payload(raw):
    inicio = raw.find('{"total"')
    assert inicio >= 0, raw
    return json.loads(raw[inicio:])


@pytest.fixture
def cerebro_mcp(tmp_path, monkeypatch):
    from core.memory_store import SQLiteMemoryBioRAG
    from core.mcp_server import search as mcp_search

    db_path = tmp_path / "fechas.db"
    shutil.copyfile(SNAPSHOT, db_path)
    # _recordar_impl cierra el cerebro al terminar: uno nuevo por llamada.
    monkeypatch.setattr(
        mcp_search, "_get_cerebro", lambda: SQLiteMemoryBioRAG(db_path=str(db_path))
    )
    conn = sqlite3.connect(db_path, timeout=30)
    yield conn, mcp_search
    conn.close()


def _fijar(conn, concepto, dias, categoria):
    conn.execute(
        "UPDATE largo_plazo SET creado_en = ?, "
        "categoria = (SELECT id FROM categories WHERE name = ?) WHERE concepto = ?",
        (time.time() - dias * DIA, categoria, concepto),
    )
    conn.commit()


def _buscar(mcp_search, **extra):
    return _payload(mcp_search._recordar_impl(
        query="biorag version actual ultima",
        sustantivos_clave="biorag,version",
        parafrasis="version biorag,version actual biorag,ultima version biorag",
        limite=5,
        asociados=False,
        **extra,
    ))


def test_cada_resultado_trae_fecha_y_edad_reales(cerebro_mcp):
    conn, mcp_search = cerebro_mcp
    resultados = _buscar(mcp_search)["resultados"]
    assert resultados

    creados = dict(conn.execute(
        "SELECT concepto, creado_en FROM largo_plazo WHERE concepto IN (%s)"
        % ",".join("?" * len(resultados)),
        [r["concepto"] for r in resultados],
    ).fetchall())
    for r in resultados:
        ts = creados[r["concepto"]]
        assert r["timestamp_creado"] == ts
        assert r["fecha_legible"] == datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        assert r["edad_dias"] == pytest.approx((time.time() - ts) / DIA, abs=0.2)


def test_caducidad_respeta_90_dias_y_categorias_protegidas(cerebro_mcp):
    conn, mcp_search = cerebro_mcp
    conceptos = [r["concepto"] for r in _buscar(mcp_search)["resultados"]]
    assert len(conceptos) >= 3
    viejo_lesson, viejo_principle, reciente_lesson = conceptos[:3]
    _fijar(conn, viejo_lesson, 200, "Lesson")
    _fijar(conn, viejo_principle, 200, "Principle")
    _fijar(conn, reciente_lesson, 10, "Lesson")

    raw = mcp_search._recordar_impl(
        query="biorag version actual ultima",
        sustantivos_clave="biorag,version",
        parafrasis="version biorag,version actual biorag,ultima version biorag",
        limite=5,
        asociados=False,
    )
    por_concepto = {r["concepto"]: r for r in _payload(raw)["resultados"]}

    assert por_concepto[viejo_lesson]["stale"] is True
    assert por_concepto[viejo_lesson]["edad_dias"] == pytest.approx(200, abs=0.2)
    assert por_concepto[viejo_principle]["stale"] is False  # atemporal
    assert por_concepto[reciente_lesson]["stale"] is False
    # El aviso al agente nombra al viejo y no al protegido.
    aviso = raw[: raw.find('{"total"')]
    assert "stale" in aviso and viejo_lesson in aviso
    assert viejo_principle not in aviso.split("stale")[1]


def test_vecinos_de_context_window_tambien_traen_fecha(cerebro_mcp, monkeypatch):
    from core.memory_store import SQLiteMemoryBioRAG

    conn, mcp_search = cerebro_mcp
    vecino, ts_vecino = conn.execute(
        "SELECT concepto, creado_en FROM largo_plazo "
        "WHERE estado = 'activo' AND creado_en > 0 ORDER BY id LIMIT 1"
    ).fetchone()
    fila_vecino = (vecino, "contenido", 0.5, "activo", 0.1, [])
    monkeypatch.setattr(
        SQLiteMemoryBioRAG,
        "expandir_contexto_vecinos",
        lambda self, resultados, **_kw: (resultados, [fila_vecino]),
    )
    payload = _buscar(mcp_search, context_window=1)
    ctx = {c["concepto"]: c for c in payload["contexto_expandido"]}
    assert ctx[vecino]["fecha_legible"] == datetime.fromtimestamp(ts_vecino).strftime("%Y-%m-%d %H:%M")
    assert ctx[vecino]["timestamp_creado"] == ts_vecino


def test_lectura_cubre_corto_plazo_y_no_falla_en_silencio(tmp_path, caplog):
    from core.mcp_server.search import _leer_antiguedad_y_categoria

    db_path = tmp_path / "corto.db"
    shutil.copyfile(SNAPSHOT, db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ahora = time.time()
    cur.execute(
        "INSERT INTO corto_plazo (concepto, contenido, timestamp, categoria) VALUES (?, ?, ?, "
        "(SELECT id FROM categories WHERE name = 'Lesson'))",
        ("nodo_en_corto_plazo_prueba", "x", ahora),
    )
    edad, cat = _leer_antiguedad_y_categoria(cur, ["nodo_en_corto_plazo_prueba", "no_existe"])
    assert edad == {"nodo_en_corto_plazo_prueba": ahora}
    assert cat == {"nodo_en_corto_plazo_prueba": "Lesson"}

    # Si el esquema no cuadra, queda registrado (antes: except: pass mudo).
    roto = sqlite3.connect(":memory:").cursor()
    with caplog.at_level("WARNING", logger="mcp_server"):
        assert _leer_antiguedad_y_categoria(roto, ["x"]) == ({}, {})
    assert "antigüedad" in caplog.text
