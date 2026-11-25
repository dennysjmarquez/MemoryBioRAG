"""Experimento 16 — construye un mundo sintético con el MOTOR REAL sin modificarlo (PROTOCOLO.md §2).

Replica el camino de `aprender` (core/mcp_server/write.py L295–322): _resolver_dimensiones →
percibir_corto_plazo → auto_vincular → vincular_por_sinonimos; sueño cada 50 recuerdos y al final.
Solo escribe en la ruta indicada (que debe estar en /tmp). Uso como módulo: construir(mundo, ruta).
"""
import contextlib
import io
import json
import os
import sys
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)


def catalogo_real():
    """Nombres del catálogo de dimensiones de una base nueva (esquema del motor)."""
    import sqlite3
    import tempfile
    from core.memory_store import SQLiteMemoryBioRAG
    d = tempfile.mkdtemp(prefix="exp16_cat_", dir="/tmp")
    ruta = os.path.join(d, "c.db")
    with contextlib.redirect_stdout(io.StringIO()):
        SQLiteMemoryBioRAG(db_path=ruta)
    con = sqlite3.connect(ruta)
    cat = {}
    for eje, nombre in con.execute(
            "SELECT t.nombre, d.name FROM dimensiones_semanticas d JOIN tipos_dimension t ON t.id=d.tipo_id "
            "ORDER BY t.id, d.id"):
        cat.setdefault(eje, []).append(nombre)
    con.close()
    return cat


def abrir(ruta):
    from core.memory_store import SQLiteMemoryBioRAG
    with contextlib.redirect_stdout(io.StringIO()):
        return SQLiteMemoryBioRAG(db_path=ruta)


def guardar(cerebro, ev):
    """Un `aprender` sin bridges ni vincular_con (manual: decisión 3)."""
    from core.mcp_server._shared import _resolver_dimensiones
    from core.memory_store import normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    from core.sinapsis import auto_vincular, vincular_por_sinonimos
    clave = ev["concepto"].lower().replace(" ", "_")
    sk_ex = normalizar_sustantivos_clave_exacto(ev["sk"])
    sk_norm = normalizar_sustantivos_clave(sk_ex)
    dims, _, err, _ = _resolver_dimensiones(cerebro, json.dumps(ev["dims"]))
    if err:
        raise RuntimeError(err)
    cerebro.percibir_corto_plazo(clave, ev["contenido"], ev["syn"], ev["cat"], dims, predicados=None,
                                 valencia_somatica=0.0, sustantivos_clave=sk_norm,
                                 sustantivos_clave_exactos=sk_ex)
    auto_vincular(cerebro, clave, ev["contenido"])
    if ev["syn"]:
        vincular_por_sinonimos(cerebro, clave, ev["syn"])


def dormir(cerebro):
    with contextlib.redirect_stdout(io.StringIO()):
        cerebro.ciclo_sueno_consolidacion()


def construir(mundo, ruta, cada=50):
    assert os.path.abspath(ruta).startswith("/tmp/"), "solo bases temporales en /tmp"
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    t0 = time.time()
    cerebro = abrir(ruta)
    for k, ev in enumerate(mundo["eventos"], 1):
        with contextlib.redirect_stdout(io.StringIO()):
            guardar(cerebro, ev)
        if k % cada == 0:
            dormir(cerebro)
    dormir(cerebro)
    cerebro.conn.commit() if hasattr(cerebro, "conn") else cerebro.cursor.connection.commit()
    return cerebro, time.time() - t0
