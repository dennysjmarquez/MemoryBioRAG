"""QA por el CAMINO REAL del agente: la herramienta MCP `recordar`, no `buscar_por_frase`.

POR QUÉ: `scripts/evaluar_qa.py` llama al motor directo (sin peso sináptico, sin
sustantivos_clave, sin auto-paráfrasis PMI, sin auto-dimensiones, sin el pool 3x
del MCP). Eso es el motor sin el agente. Un agente real pasa por `recordar`, que
EXIGE sustantivos_clave y agrega todo lo anterior. Este script mide ese camino.

Mismo arnés que la QA oficial (para que la comparación sea justa):
  - etiquetas oro obsoletas resueltas con la MISMA lógica (`_resolver_etiqueta`);
  - consultas con oro contradictorio (`ambiguo`) y `negativo` fuera del recall;
  - antes de cada caso: el nodo esperado `activo` (o `dormido` en esa categoría);
    después: se restaura `estado` y `peso_sinaptico` de todo el corpus, así cada
    caso arranca del mismo estado (independiente del orden).
Por caso:
  - sustantivos_clave = lo que extraería un agente mínimo (las 3 primeras palabras
    con significado de la consulta, sin mirar la respuesta). Es una extracción
    tosca A PROPÓSITO (distinta de la que usa la neurona al practicar): mide si
    generaliza a otro "agente";
  - `dormido` se busca con deep=True (como lo pide el protocolo);
  - se mide el puesto del recuerdo esperado en la respuesta (top-10 del MCP).

ABLACIONES (--quitar a,b,...): atribuyen la diferencia con la QA a cada pieza del
camino MCP, interceptando la llamada al motor que hace `recordar`:
  peso        -> ignore_peso_sinaptico=True
  sustantivos -> sin sustantivos_clave_boost
  parafrasis  -> sin auto-paráfrasis PMI
  dims        -> sin auto-dimensiones
  pool        -> limite=5 y convergencia sobre 5 (como la QA)

Uso (sobre una COPIA, nunca la DB viva ni el snapshot):
  BIORAG_PATH=/copia.db BIORAG_NEURONA=0|1 python evaluar_camino_mcp.py --salida res.json [--quitar peso]
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
os.environ["BIORAG_NO_LOG"] = "1"

QUITABLES = ("peso", "sustantivos", "parafrasis", "dims", "pool")


def sustantivos(q):
    from core.stopwords import STOPWORDS
    ws = [w for w in re.findall(r"[a-z0-9_ñ]+", q.lower()) if 2 <= len(w) <= 15]
    ws = [w for w in dict.fromkeys(ws) if w not in STOPWORDS]
    return ",".join(ws[:3])


def _clave(texto):
    t = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def resolutor(cur):
    """La misma resolución de etiquetas obsoletas que scripts/evaluar_qa.py (umbral .94, margen .02)."""
    por_clave = defaultdict(list)
    for (c,) in cur.execute("SELECT concepto FROM largo_plazo").fetchall():
        if c:
            por_clave[_clave(c)].append(c)
    claves = list(por_clave)

    def resolver(esperado):
        if not esperado or cur.execute("SELECT 1 FROM largo_plazo WHERE concepto = ?", (esperado,)).fetchone():
            return esperado
        k = _clave(esperado)
        if len(por_clave.get(k, [])) == 1:
            return por_clave[k][0]
        if por_clave.get(k):
            return esperado
        cerca = difflib.get_close_matches(k, claves, n=3, cutoff=0.80)
        if not cerca:
            return esperado
        r1 = difflib.SequenceMatcher(None, k, cerca[0]).ratio()
        r2 = difflib.SequenceMatcher(None, k, cerca[1]).ratio() if len(cerca) > 1 else 0.0
        if r1 < .94 or r1 - r2 < .02 or len(por_clave[cerca[0]]) > 1:
            return esperado
        return por_clave[cerca[0]][0]
    return resolver


def interceptar(cerebro, quitar):
    """Envuelve buscar_por_frase del cerebro del MCP para quitar piezas del camino."""
    if not quitar:
        return
    real = cerebro.buscar_por_frase

    def envuelto(frase, *args, **kw):
        if "peso" in quitar:
            kw["ignore_peso_sinaptico"] = True
        if "sustantivos" in quitar:
            kw["sustantivos_clave_boost"] = None
        if "parafrasis" in quitar:
            kw["parafrasis_list"] = None
        if "dims" in quitar:
            kw["dimensiones_ids"] = None
            kw["dimensiones_dict"] = None
        if "pool" in quitar:
            kw["limite"] = 5
            kw["convergencia_limite"] = 5
        return real(frase, *args, **kw)
    cerebro.buscar_por_frase = envuelto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True)
    ap.add_argument("--n", type=int, default=0, help="0 = todos")
    ap.add_argument("--casos", default=os.path.join(REPO, "scripts", "casos_qa_baseline_v1.jsonl"),
                    help="JSONL con query + concepto_esperado|esperado (+ categoria|seccion)")
    ap.add_argument("--sin", default="", help="categorías a excluir, separadas por coma (ej. literal)")
    ap.add_argument("--quitar", default="", help="ablaciones separadas por coma: " + ",".join(QUITABLES))
    a = ap.parse_args()
    quitar = {x.strip() for x in a.quitar.split(",") if x.strip()}
    assert quitar <= set(QUITABLES), f"ablación desconocida: {quitar - set(QUITABLES)}"

    casos = [json.loads(l) for l in open(a.casos, encoding="utf-8") if l.strip()]
    for c in casos:   # el examen humano de pydocs usa esperado/seccion
        c.setdefault("concepto_esperado", c.get("esperado"))
        c.setdefault("categoria", "humana_" + str(c.get("seccion", "")))
    golds = defaultdict(set)
    for c in casos:
        if c.get("concepto_esperado"):
            golds[c["query"].strip().lower()].add(c["concepto_esperado"])
    ambiguas = {q for q, g in golds.items() if len(g) > 1}
    casos = [c for c in casos if c.get("concepto_esperado") and c.get("categoria") != "negativo"
             and c["query"].strip().lower() not in ambiguas]
    sin = {x.strip() for x in a.sin.split(",") if x.strip()}
    casos = [c for c in casos if c["categoria"] not in sin]
    if a.n:
        casos = casos[:a.n]

    import mcp_server as m
    tools = {t.name: t.fn for t in m._build_server()._tool_manager.list_tools()}
    from core.memory import neurona
    from core.memory_service import get_cerebro
    cerebro = get_cerebro()
    info = neurona.resumen(cerebro)
    interceptar(cerebro, quitar)
    cur = cerebro.cursor
    resolver = resolutor(cur)
    inicial = {r[0]: (r[1], r[2]) for r in cur.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo")}

    def restaurar():
        cambios = []
        for c, e, p in cur.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall():
            o = inicial.get(c)
            if o and (o[0] != e or o[1] != p):
                cambios.append((o[0], o[1], c))
        if cambios:
            cur.executemany("UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?", cambios)
            cerebro.conn.commit()

    por_cat, filas, t0 = {}, [], time.time()
    for c in casos:
        q, cat = c["query"], c["categoria"]
        esperado = resolver(c["concepto_esperado"])
        cur.execute("UPDATE largo_plazo SET estado = ? WHERE concepto = ?",
                    ("dormido" if cat == "dormido" else "activo", esperado))
        cerebro.conn.commit()
        sk = sustantivos(q) or "consulta"
        raw = tools["recordar"](query=q, sustantivos_clave=sk, deep=(cat == "dormido"))
        try:
            d = json.loads(raw[raw.find("{"):])
            nombres = [r["concepto"] for r in d.get("resultados", []) or []]
        except Exception:
            nombres = []
        puesto = nombres.index(esperado) + 1 if esperado in nombres else 0
        if cat == "dormido" and puesto:   # como la QA: además tiene que haberlo despertado
            fila = cur.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (esperado,)).fetchone()
            puesto = puesto if fila and fila[0] == "activo" else 0
        restaurar()
        filas.append(dict(id=c.get("id"), cat=cat, q=q, sk=sk, esperado=esperado, puesto=puesto, top5=nombres[:5]))
        s = por_cat.setdefault(cat, [0, 0, 0, 0.0])
        s[0] += 1
        s[1] += puesto == 1
        s[2] += 1 <= puesto <= 5
        s[3] += 1.0 / puesto if 1 <= puesto <= 5 else 0.0   # MRR@5, como la QA
    tot = [sum(v[i] for v in por_cat.values()) for i in range(4)]
    tabla = {k: dict(n=v[0], r1=round(100 * v[1] / v[0], 2), r5=round(100 * v[2] / v[0], 2),
                     mrr=round(v[3] / v[0], 4)) for k, v in sorted(por_cat.items())}
    tabla["GLOBAL"] = dict(n=tot[0], r1=round(100 * tot[1] / tot[0], 2), r5=round(100 * tot[2] / tot[0], 2),
                           mrr=round(tot[3] / tot[0], 4))
    out = dict(neurona_env=os.environ.get("BIORAG_NEURONA", "1"), quitar=sorted(quitar), neurona=info,
               segundos=round(time.time() - t0), tabla=tabla, casos=filas)
    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"quitar={sorted(quitar)}  neurona={out['neurona_env']}")
    print(f"{'categoría':22s} {'n':>4s} {'R@1':>7s} {'R@5':>7s} {'MRR':>7s}")
    for k, v in tabla.items():
        print(f"{k:22s} {v['n']:4d} {v['r1']:7.2f} {v['r5']:7.2f} {v['mrr']:7.4f}")


if __name__ == "__main__":
    main()
