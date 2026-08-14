"""
Experimento E — top-k islas candidatas + ranking léxico sobre la UNIÓN (2026-08-13).

Contexto: el ranking léxico restringido a la isla CORRECTA (oráculo) rescata 11/13 de
los fallos sinonimo (techo supera el coseno intra-isla de 9/13). Pero elegir UNA isla
desde una query corta es frágil (campeón léxico 1/13, coseno PPMI 3/13, boost 1-3/13).

Hipótesis (Claude Web, 2026-08-13): no forzar una sola isla. Usar el top-k de islas
candidatas por coseno query->centroide, y aplicar la señal ganadora (ranking léxico
intra-isla, 11/13) sobre la UNIÓN de esos nodos, no sobre una isla elegida a la fuerza.

Objetivos medidos sobre los 61 casos sinonimo del benchmark:
  1. Cobertura: ¿la isla del esperado está en el top-k de islas de la query? (verificar
     el "68% a top-5" que cita Claude Web — NO lo asumo, lo mido).
  2. Rescate: ¿cuántos de los 13 fallidos se rescatan re-rankeando por score léxico la
     unión top-k islas ∩ pool?
  3. Regresión: ¿cuántos de los 48 correctos se rompen? Neto sobre los 61.
  4. Comparación con techo: 11/13 (isla oráculo) y baseline 48/61.

Disciplina: copia aislada a temp (no mutar la fuente), solo lectura de la DB, misma
lógica de pool/score que evaluar_qa.py (buscar_por_frase limite=200, ignore_peso).

Uso:
    python3 scripts/experimentos/expE_topk_islas_union.py
"""
import json
import os
import sqlite3
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe_temp.db")
LABELS = os.path.join(BASE, "scripts", "experimentos", "expA_labels.json")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")

TOP_K = [1, 2, 3, 5, 8, 10]


def copiar_a_temp():
    """Copia aislada del snapshot (misma disciplina que evaluar_qa.py / rrf)."""
    for ext in ["", "-wal", "-shm"]:
        f = TEMP_DB + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    conn_src = sqlite3.connect(DB_SRC)
    conn_src.execute("PRAGMA wal_checkpoint(FULL);")
    conn_dst = sqlite3.connect(TEMP_DB)
    conn_src.backup(conn_dst)
    conn_dst.close()
    conn_src.close()


def main():
    labels = json.load(open(LABELS))
    conceptos = labels["conceptos"]
    comunidades = labels["knn_lpa"]
    com_por_concepto = dict(zip(conceptos, comunidades))
    idx_por_concepto = {c: i for i, c in enumerate(conceptos)}
    miembros_por_com = {}
    for c, com in zip(conceptos, comunidades):
        miembros_por_com.setdefault(com, []).append(c)
    n_com = len(miembros_por_com)
    print(f"nodos: {len(conceptos)}  islas: {n_com}")

    copiar_a_temp()

    # Vectores PPMI + centroides por isla (normalizados)
    con = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    rows = con.execute("SELECT concepto, vector FROM nodos").fetchall()
    con.close()
    vmap = {r[0]: np.frombuffer(r[1], dtype=np.float32).astype("float64") for r in rows}
    vn = {c: v / np.linalg.norm(v) for c, v in vmap.items()}
    centroides = {}
    acum = {}
    for c, com in com_por_concepto.items():
        if c not in vn:
            continue
        if com not in acum:
            acum[com] = np.zeros(100)
        acum[com] += vn[c]
    for com, v in acum.items():
        n = np.linalg.norm(v)
        centroides[com] = v / n if n > 1e-10 else v
    comun_ordenadas = sorted(centroides)
    centro_mat = np.array([centroides[c] for c in comun_ordenadas])

    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)
    idx = IndicesBioRAG(TEMP_DB)

    casos = [json.loads(l) for l in open(CASES) if l.strip()]
    sin = [c for c in casos if c.get("categoria") == "sinonimo"]

    # Pre-computar pool léxico + score por caso (una sola vez; ~1.3s/query con limite 200)
    pool_cache = {}
    vq_cache = {}
    for caso in sin:
        q = caso["query"]
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                     ignore_peso_sinaptico=True)
        pool_cache[q] = {r[0]: r[4] for r in res}
        toks = _tokenizar(q)
        if toks:
            vq = idx.vector_query(toks)
            if np.linalg.norm(vq) > 1e-10:
                vq = vq / np.linalg.norm(vq)
                vq_cache[q] = vq

    print(f"\ncasos sinonimo: {len(sin)}")
    print("=" * 90)

    # ---- 1) cobertura: isla del esperado en top-k de la query ----
    print("\n[1] COBERTURA — isla del esperado dentro del top-k de islas de la query")
    for k in TOP_K:
        cubre = 0
        for caso in sin:
            q, esp = caso["query"], caso["concepto_esperado"]
            if esp not in com_por_concepto or q not in vq_cache:
                continue
            com_esp = com_por_concepto[esp]
            sims = centro_mat @ vq_cache[q]
            top_k_com = set([comun_ordenadas[i] for i in np.argsort(-sims)[:k]])
            if com_esp in top_k_com:
                cubre += 1
        print(f"  top-{k:<2}: {cubre}/{len(sin)} ({cubre / len(sin):.1%})")

    # ---- 2-4) ranking léxico restringido a la unión top-k islas ∩ pool ----
    print("\n[2] RESCATE — ranking léxico sobre unión top-k islas ∩ pool (top-5 result)")
    # etiquetas de contexto: 13 fallidos conocidos (de casos_fallidos.jsonl)
    header = (f"{'k':<4}{'union_total':<12}{'fallidos_rescatados':<20}"
              f"{'correctos_rotos':<16}{'neto_61':<8}{'en_union_13':<12}")
    print(header)
    print("-" * 90)

    fallidos_ids = set()
    casos_fallidos = os.path.join(BASE, "scripts", "casos_fallidos.jsonl")
    if os.path.exists(casos_fallidos):
        for l in open(casos_fallidos):
            if l.strip():
                try:
                    fc = json.loads(l)
                except json.JSONDecodeError:
                    continue
                if fc.get("categoria") == "sinonimo":
                    fallidos_ids.add(fc.get("id"))

    resultados_detalle = {}
    for k in TOP_K:
        rescatados = 0
        rotos = 0
        en_union_13 = 0
        union_prom = 0.0
        detalle = []
        for caso in sin:
            q, esp = caso["query"], caso["concepto_esperado"]
            pool = pool_cache.get(q, {})
            if not pool or q not in vq_cache:
                continue
            com_esp = com_por_concepto.get(esp)
            sims = centro_mat @ vq_cache[q]
            top_k_com = set([comun_ordenadas[i] for i in np.argsort(-sims)[:k]])
            union = set()
            for com in top_k_com:
                union.update(miembros_por_com.get(com, []))
            # restringir a nodos que YA están en el pool léxico (misma base que el techo)
            intra = {n: s for n, s in pool.items() if n in union}
            union_prom += len(intra)
            ranked = sorted(intra.items(), key=lambda x: x[1], reverse=True)
            top5 = [n for n, _ in ranked[:5]]
            ok = esp in top5
            es_fallido = caso["id"] in fallidos_ids
            if es_fallido:
                if ok:
                    rescatados += 1
                if com_esp in top_k_com:
                    en_union_13 += 1
            else:
                if not ok:
                    rotos += 1
            detalle.append((caso["id"], q, esp, ok, es_fallido, len(intra)))
        resultados_detalle[k] = detalle
        union_prom /= len(sin)
        neto = rescatados - rotos
        print(f"{k:<4}{union_prom:<12.1f}{rescatados:<20}/{rescatados:<18}"
              f"{rotos:<16}{neto:<8}{en_union_13:<12}")
        print(f"      fallidos rescatados: {rescatados}/13  |  correctos rotos: {rotos}/48")

    # ---- detalle por caso para el mejor k ----
    print("\n[3] DETALLE por caso fallido (mejor k visible arriba; detalle top-5):")
    mejor = None
    mejor_neto = -10**9
    for k in TOP_K:
        det = resultados_detalle[k]
        resc = sum(1 for c in det if c[3] and c[4])
        rot = sum(1 for c in det if not c[3] and not c[4])
        net = resc - rot
        if net > mejor_neto:
            mejor_neto = net
            mejor = k
    detalle = resultados_detalle[mejor]
    for c in detalle:
        if c[4]:  # solo fallidos
            print(f"  {c[0]} | '{c[1]}' -> {c[2]}: rescatado={c[3]} (union={c[5]} nodos)")

    # limpieza
    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
