"""Verificación reproducible del mapa de nacimiento de sinapsis (2026-11-25).

Qué hace y POR QUÉ:
  El mapa que circuló entre agentes traía cifras sin comprobar. Este script mide
  sobre el snapshot público (solo lectura) y hace dos repros sobre una COPIA en
  un directorio temporal. Nunca escribe en el snapshot ni en la DB viva.

Uso:
  python3 verificar.py snapshots/qa_escape_qcr_20260811.db

Solo usa la biblioteca estándar (sqlite3) y core.sinapsis / core.memory.synapses.
"""
import collections
import hashlib
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import types

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)

AUTO = "tipo NOT IN ('manual','manual_v7')"


def sha12(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def medir_solo_lectura(ruta):
    c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    q = lambda s, *a: c.execute(s, a).fetchall()
    r = {}
    r["tipos(tipo,n,peso_medio,min,max,ultimo_uso_NULL)"] = q(
        "SELECT tipo,COUNT(*),ROUND(AVG(peso),3),ROUND(MIN(peso),2),ROUND(MAX(peso),2),"
        "SUM(ultimo_uso IS NULL) FROM sinapsis GROUP BY tipo ORDER BY 2 DESC")
    r["manuales_con_peso_distinto_de_0.5"] = q(
        "SELECT COUNT(*) FROM sinapsis WHERE tipo IN ('manual','manual_v7') AND ABS(peso-0.5)>1e-9")[0][0]
    r["pares_mixtos(manual en un sentido, automatico en el otro)"] = q(
        "SELECT b.tipo,COUNT(*) FROM sinapsis a JOIN sinapsis b ON a.origen=b.destino AND a.destino=b.origen "
        "WHERE a.tipo IN ('manual','manual_v7') AND b.tipo NOT IN ('manual','manual_v7') "
        "GROUP BY 1 ORDER BY 2 DESC")
    r["max_salida_auto"] = q(f"SELECT origen,COUNT(*) n FROM sinapsis WHERE {AUTO} GROUP BY origen ORDER BY n DESC LIMIT 1")
    r["max_entrada_auto"] = q(f"SELECT destino,COUNT(*) n FROM sinapsis WHERE {AUTO} GROUP BY destino ORDER BY n DESC LIMIT 1")
    tablas = {t for (t,) in q("SELECT name FROM sqlite_master WHERE type='table'")}
    if "sinapsis_cuarentena" in tablas:
        r["cuarentena_no_restaurada"] = q(
            "SELECT COUNT(*) FROM sinapsis_cuarentena WHERE restaurado=0 AND tabla_origen='sinapsis'")[0][0]
        r["renacidas(tipo,n,dias_medios_hasta_renacer)"] = q(
            "SELECT s.tipo,COUNT(*),ROUND(AVG((s.creado_en-k.eliminado_en)/86400.0),1) "
            "FROM sinapsis_cuarentena k JOIN sinapsis s ON s.origen=k.origen AND s.destino=k.destino "
            "WHERE k.restaurado=0 AND k.tabla_origen='sinapsis' AND s.creado_en>k.eliminado_en "
            "GROUP BY 1 ORDER BY 2 DESC")
    # Cierre triádico: ¿cuántos pares AL AZAR ya comparten un vecino?
    vec = collections.defaultdict(set)
    for o, d in q("SELECT origen,destino FROM sinapsis"):
        vec[o].add(d)
        vec[d].add(o)
    activos = [x for (x,) in q("SELECT concepto FROM largo_plazo WHERE estado='activo' ORDER BY concepto")]
    rnd = random.Random(1)
    com = sum(bool(vec[a] & vec[b]) for a, b in (rnd.sample(activos, 2) for _ in range(20000)))
    r["pares_al_azar_con_vecino_comun"] = round(com / 20000, 3)
    r["activos_con_mas_de_5_sinapsis"] = round(sum(len(vec[a]) > 5 for a in activos) / len(activos), 3)
    c.close()
    return r


def repros_sobre_copia(ruta):
    import core.sinapsis as S
    from core.memory import synapses as SY

    tmp = tempfile.mkdtemp(prefix="mapa_sinapsis_")
    copia = os.path.join(tmp, "copia.db")
    shutil.copy(ruta, copia)
    con = sqlite3.connect(copia)
    con.create_function(
        "PALABRA_COMPLETA", 2,
        lambda w, t: 1 if re.search(r"\b" + re.escape(w) + r"\b", (t or "").replace("_", " ")) else 0)
    cer = types.SimpleNamespace(conn=con, cursor=con.cursor())
    q = lambda s, *a: con.execute(s, a).fetchall()
    r = {}

    # Repro 1: el agente borra un enlace automático (desvincular) y el recuerdo se vuelve a guardar.
    pares = q("SELECT s.origen,s.destino,s.tipo,l.contenido FROM sinapsis s JOIN largo_plazo l ON l.concepto=s.origen "
              "WHERE s.tipo IN ('co_ocurrencia','co_nombre','co_semantica') AND l.estado='activo' "
              "ORDER BY s.origen,s.destino")
    muestra = random.Random(7).sample(pares, 40)
    renacen = 0
    for o, d, _t, cont in muestra:
        S.desvincular(cer, o, d)
        S.auto_vincular(cer, o, cont)
        renacen += bool(q("SELECT 1 FROM sinapsis WHERE origen=? AND destino=?", o, d))
    r["desvincular_y_volver_a_guardar: renacen de 40"] = renacen

    # Repro 2: el agente vincula un par que ya tenía enlace automático.
    o, d = q("SELECT origen,destino FROM sinapsis WHERE tipo='co_ocurrencia' AND NOT EXISTS("
             "SELECT 1 FROM sinapsis b WHERE b.origen=sinapsis.destino AND b.destino=sinapsis.origen) "
             "ORDER BY origen,destino LIMIT 1")[0]
    SY.establecer_asociacion(cer, o, d)
    r["vincular_sobre_par_automatico(sentido_original?,tipo,peso)"] = q(
        "SELECT origen=?,tipo,peso FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?) "
        "ORDER BY 1 DESC", o, o, d, d, o)
    con.close()
    shutil.rmtree(tmp)
    return r


if __name__ == "__main__":
    ruta = sys.argv[1]
    antes = sha12(ruta)
    for k, v in medir_solo_lectura(ruta).items():
        print(f"{k}: {v}")
    for k, v in repros_sobre_copia(ruta).items():
        print(f"{k}: {v}")
    despues = sha12(ruta)
    print(f"sha256 del origen antes/después: {antes} / {despues}")
    assert antes == despues, "¡el origen cambió!"
