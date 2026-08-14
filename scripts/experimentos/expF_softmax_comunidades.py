"""
Experimento F — Softmax con Temperatura sobre Top-3 de Comunidades PPMI (2026-08-14).

Contexto: la proyección de queries cortas (1-2 palabras) es débil — el argmax duro de
coseno query->centroide acierta la comunidad del esperado solo ~42% top-1 / ~68% top-3.
Hipótesis (Claude Web, Fase B): suavizar la selección de comunidad con softmax sobre el
Top-3, y puntuar a los candidatos con P(C|q,tau)*cos(vq,vd), rescata sinónimos sin
canibalizar el ranking léxico (que NO se toca en producción — esto es un experimento).

Formulación matemática:
    v_q = vector_query(tokens(q))                     (ponderado por IDF)
    v_q_hat = v_q / |v_q|
    s_k   = v_q_hat . centroide_k                      (coseno contra todos los centroides)
    T3    = top-3 de s_k
    P(C_k | q, tau) = exp((s_k - max(s_T3))/tau) / sum_{j in T3} exp((s_j - max(s_T3))/tau)
    Score_comunidad(d) = P(C_nodo(d) | q, tau) * cos(v_q_hat, v_d_hat)   para d in union(T3) ∩ pool

Métricas:
    1. Co-comunidad top-1/top-3 (baseline 42%/68%).
    2. Rescates: fallidos sinonimo (clasificados HOY con limite=5, ignore_peso, igual que
       evaluar_qa) que caen en el top-5 del ranking suave. Meta: 2 -> >=6/13 (techo 9/13).
    3. Regresiones: correctos que se rompen. Neto sobre los 61 casos sinonimo.
    4. Referencia: re-rank léxico sobre union top-3 (expE k=3) para comparar.

Disciplina: copia aislada del snapshot a temp, solo lectura de la DB, no toca producción.

Uso:
    python3 scripts/experimentos/expF_softmax_comunidades.py
"""
import json
import os
import shutil
import sqlite3
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe_temp_f.db")
LABELS = os.path.join(BASE, "scripts", "experimentos", "expA_labels.json")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")

TOP3_TAUS = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
DIM = 100


def copiar_a_temp():
    """Copia aislada del snapshot (misma disciplina que evaluar_qa / expE)."""
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


def softmax_top3(sims_top3, tau):
    """Softmax sobre las 3 similitudes del top-3, con resta del max por estabilidad
    numérica (evita overflow de exp para tau pequenos)."""
    m = float(np.max(sims_top3))
    e = np.exp((sims_top3 - m) / tau)
    return e / e.sum()


def main():
    labels = json.load(open(LABELS))
    conceptos = labels["conceptos"]
    comunidades = labels["knn_lpa"]
    com_por_concepto = dict(zip(conceptos, comunidades))
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
    vn = {c: v / (np.linalg.norm(v) + 1e-10) for c, v in vmap.items()}
    acum = {}
    for c, com in com_por_concepto.items():
        if c not in vn:
            continue
        if com not in acum:
            acum[com] = np.zeros(DIM)
        acum[com] += vn[c]
    centroides = {}
    for com, v in acum.items():
        n = np.linalg.norm(v)
        centroides[com] = v / n if n > 1e-10 else v
    comun_ordenadas = sorted(centroides)
    centro_mat = np.array([centroides[c] for c in comun_ordenadas])

    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)
    idx = IndicesBioRAG(TEMP_DB)

    casos = [json.loads(l) for l in open(CASES) if l.strip()]
    sin = [c for c in casos if c.get("categoria") == "sinonimo"]

    # ---- clasificar fallidos HOY (igual que evaluar_qa: limite=5, ignore_peso) ----
    fallidos = set()
    for caso in sin:
        res, _ = db.buscar_por_frase(
            caso["query"], profundidad="activos", limite=5, ignore_peso_sinaptico=True
        )
        top5 = {r[0] for r in res}
        if caso["concepto_esperado"] not in top5:
            fallidos.add(caso["id"])
    n_fallidos = len(fallidos)
    n_correctos = len(sin) - n_fallidos
    print(f"casos sinonimo: {len(sin)}  |  fallidos HOY: {n_fallidos}  |  correctos: {n_correctos}")
    print("(baseline run_b documentaba 13/48 — hoy el entorno da distinta cifra; se clasifica actual)")

    # ---- pre-computar pool lexico + vector de query por caso ----
    pool_cache = {}
    vq_cache = {}
    for caso in sin:
        q = caso["query"]
        res, _ = db.buscar_por_frase(
            q, profundidad="activos", limite=200, ignore_peso_sinaptico=True
        )
        pool_cache[q] = {r[0]: r[4] for r in res}
        toks = _tokenizar(q)
        if toks:
            vq = idx.vector_query(toks)
            if np.linalg.norm(vq) > 1e-10:
                vq_cache[q] = vq / np.linalg.norm(vq)

    print("\n[1] CO-COMUNIDAD del esperado (coseno query->centroide, sin softmax)")
    top1 = top3 = 0
    for caso in sin:
        q, esp = caso["query"], caso["concepto_esperado"]
        if esp not in com_por_concepto or q not in vq_cache:
            continue
        sims = centro_mat @ vq_cache[q]
        order = np.argsort(-sims)
        if comun_ordenadas[order[0]] == com_por_concepto[esp]:
            top1 += 1
        if com_por_concepto[esp] in set(comun_ordenadas[i] for i in order[:3]):
            top3 += 1
    print(f"  top-1: {top1}/{len(sin)} ({top1/len(sin):.1%})   "
          f"top-3: {top3}/{len(sin)} ({top3/len(sin):.1%})")

    # ---- barrido de temperatura ----
    print("\n[2] BARRIDO tau (ranking suave softmax top-3, top-5 result)")
    header = (f"{'tau':<6}{'rescates':<10}{'rotos':<8}{'neto':<6}"
              f"{'fallidos_en_T3':<15}{'co-comunidad_T3':<16}")
    print(header)
    print("-" * 78)
    for tau in TOP3_TAUS:
        rescatados = 0
        rotos = 0
        fallidos_en_T3 = 0
        com_acierta = 0
        for caso in sin:
            q, esp = caso["query"], caso["concepto_esperado"]
            pool = pool_cache.get(q, {})
            if not pool or q not in vq_cache or esp not in com_por_concepto:
                continue
            vq = vq_cache[q]
            sims = centro_mat @ vq
            order = np.argsort(-sims)[:3]
            top3_com = [comun_ordenadas[i] for i in order]
            probs = softmax_top3(sims[order], tau)
            prob_por_com = dict(zip(top3_com, probs))
            com_esp = com_por_concepto[esp]
            if caso["id"] in fallidos and com_esp in set(top3_com):
                fallidos_en_T3 += 1

            union = set()
            for com in top3_com:
                union.update(miembros_por_com.get(com, []))
            intra = union & set(pool.keys())

            ranked = []
            for nodo in intra:
                com_n = com_por_concepto.get(nodo)
                if com_n not in prob_por_com:
                    continue
                if nodo not in vn:
                    continue
                p = prob_por_com[com_n]
                cos = float(vn[nodo] @ vq)
                ranked.append((p * cos, nodo))
            ranked.sort(key=lambda x: x[0], reverse=True)
            top5 = {n for _, n in ranked[:5]}
            ok = esp in top5
            if caso["id"] in fallidos:
                if ok:
                    rescatados += 1
                    if com_esp in set(top3_com):
                        com_acierta += 1
            else:
                if not ok:
                    rotos += 1
        neto = rescatados - rotos
        pct_com = com_acierta / rescatados if rescatados else 0.0
        print(f"{tau:<6.2f}{rescatados:<10}{rotos:<8}{neto:<6}"
              f"{fallidos_en_T3:<15}{pct_com:<16.1%}")

    # ---- detalle para el mejor tau (mas rescates, desempate por menos rotos) ----
    print("\n[3] DETALLE por caso fallido (para el mejor tau del barrido):")
    mejores = []
    for tau in TOP3_TAUS:
        rescatados = 0
        rotos = 0
        detalle = {}
        for caso in sin:
            q, esp = caso["query"], caso["concepto_esperado"]
            pool = pool_cache.get(q, {})
            if not pool or q not in vq_cache or esp not in com_por_concepto:
                continue
            vq = vq_cache[q]
            sims = centro_mat @ vq
            order = np.argsort(-sims)[:3]
            top3_com = [comun_ordenadas[i] for i in order]
            probs = softmax_top3(sims[order], tau)
            prob_por_com = dict(zip(top3_com, probs))
            union = set()
            for com in top3_com:
                union.update(miembros_por_com.get(com, []))
            intra = union & set(pool.keys())
            ranked = []
            for nodo in intra:
                com_n = com_por_concepto.get(nodo)
                if com_n not in prob_por_com or nodo not in vn:
                    continue
                ranked.append((prob_por_com[com_n] * float(vn[nodo] @ vq), nodo))
            ranked.sort(key=lambda x: x[0], reverse=True)
            top5 = {n for _, n in ranked[:5]}
            ok = esp in top5
            if caso["id"] in fallidos:
                detalle[caso["id"]] = ok
                if ok:
                    rescatados += 1
            elif not ok:
                rotos += 1
        mejores.append((tau, rescatados, rotos, detalle))
    mejor = max(mejores, key=lambda x: (x[1], -x[2]))
    for caso in sin:
        if caso["id"] in fallidos:
            marca = "RESCATADO" if mejor[3].get(caso["id"]) else "  fallido  "
            print(f"  [{marca}] {caso['id']} | '{caso['query']}' -> {caso['concepto_esperado']}"
                  f"  (tau={mejor[0]:.2f})")

    # limpieza
    for f in [TEMP_DB, TEMP_DB + "-wal", TEMP_DB + "-shm"]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    main()
