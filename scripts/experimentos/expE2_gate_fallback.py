"""
Experimento E2 — Gate del fallback condicional: ¿puede aislar los 13 sin tocar los 48?
(2026-08-13)

Diseño propuesto por Claude Web tras la refutación de expE: la expansión de query NO
debe alimentar el pool ni el ranking global. Debe usarse SOLO como fallback condicional:

  1. Correr el ranking léxico global actual (intacto). Si el esperado ya está en top-5,
     no tocar nada.
  2. Solo si el léxico global falló: expandir la query, proyectar a la isla, y aplicar
     el ranking intra-isla (oráculo 11/13) como red de seguridad.

Esto hace imposible romper los 48 correctos (nunca se tocan). El punto crítico que falta
medir ANTES de invertir en la expansión (lo caro) es: ¿existe un gate PREDICTIVO
(sin ground truth) que aísle los 13 fallidos con un superset pequeño y que no capture
muchos correctos? Si no existe, el diseño no tiene punto de activación viable.

Señales de gate evaluadas (ya medidas como discriminantes en el experimento RRF):
  - GAP: score top-1 léxico - score top-2 léxico (fallidos tenían 0.000-0.144)
  - RANGO_COS: rango del top-1 léxico en el ranking coseno PPMI global (fallidos
    mediana 13 vs correctos 1, con solapamiento)
  - GAP_AND_RANGO: combinación AND de ambas (activa solo si ambas señales son débiles)

Métricas por umbral: TPR (fallidos capturados/13), FPR (correctos capturados/48),
techo del fallback oráculo sobre el superset activado.

Disciplina: copia temp, buscar_por_frase limite=200, ignore_peso_sinaptico — igual que
evaluar_qa.py. Solo lectura de la fuente.

Uso:
    python3 scripts/experimentos/expE2_gate_fallback.py
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
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe2_temp.db")
LABELS = os.path.join(BASE, "scripts", "experimentos", "expA_labels.json")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")
FALLIDOS = os.path.join(BASE, "scripts", "casos_fallidos.jsonl")

GAPS = [0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30]
RANGOS = [2, 3, 5, 8, 12, 20, 40, 80]


def copiar_a_temp():
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

    fallidos_ids = set()
    if os.path.exists(FALLIDOS):
        for l in open(FALLIDOS):
            if l.strip():
                try:
                    fc = json.loads(l)
                except json.JSONDecodeError:
                    continue
                if fc.get("categoria") == "sinonimo":
                    fallidos_ids.add(fc.get("id"))

    copiar_a_temp()

    con = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    rows = con.execute("SELECT concepto, vector FROM nodos").fetchall()
    con.close()
    vmap = {r[0]: np.frombuffer(r[1], dtype=np.float32).astype("float64") for r in rows}
    vn = {c: v / np.linalg.norm(v) for c, v in vmap.items()}
    mat = np.array([vn[c] for c in vn])
    node_list = list(vn)

    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)
    idx = IndicesBioRAG(TEMP_DB)

    casos = [json.loads(l) for l in open(CASES) if l.strip()]
    sin = [c for c in casos if c.get("categoria") == "sinonimo"]

    # Por cada caso: top-200 léxico, gap, rango_cos del top-1 léxico, y veredicto global
    rows_caso = []
    for caso in sin:
        q = caso["query"]
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                     ignore_peso_sinaptico=True)
        pool = [r[0] for r in res]
        scores = {r[0]: r[4] for r in res}
        toks = _tokenizar(q)
        gap = None
        rango_cos = None
        if len(pool) >= 2:
            gap = scores[pool[0]] - scores[pool[1]]
        if toks and pool:
            vq = idx.vector_query(toks)
            vq = vq / np.linalg.norm(vq)
            cos_all = mat @ vq
            order = np.argsort(-cos_all)
            rank_por_nodo = {node_list[i]: int(rp) for rp, i in enumerate(order)}
            rango_cos = rank_por_nodo.get(pool[0])  # rango coseno del top-1 léxico
        esp = caso["concepto_esperado"]
        global_top5_ok = esp in pool[:5]
        rows_caso.append({
            "id": caso["id"], "q": q, "esp": esp, "gap": gap, "rango_cos": rango_cos,
            "global_ok": global_top5_ok, "fallido": caso["id"] in fallidos_ids,
            "com_esp": com_por_concepto.get(esp),
        })

    n_fallidos = sum(1 for r in rows_caso if r["fallido"])
    n_correctos = sum(1 for r in rows_caso if not r["fallido"])
    print(f"casos sinonimo: {len(sin)} | fallidos: {n_fallidos} | correctos: {n_correctos}")
    print(f"global_top5_ok: {sum(1 for r in rows_caso if r['global_ok'])}/61")

    # Distribución de gap/rango en fallidos vs correctos (resumen)
    gaps_f = [r["gap"] for r in rows_caso if r["fallido"] and r["gap"] is not None]
    gaps_c = [r["gap"] for r in rows_caso if not r["fallido"] and r["gap"] is not None]
    rc_f = [r["rango_cos"] for r in rows_caso if r["fallido"] and r["rango_cos"] is not None]
    rc_c = [r["rango_cos"] for r in rows_caso if not r["fallido"] and r["rango_cos"] is not None]
    print(f"\nGAP fallidos: min={min(gaps_f):.3f} mediana={np.median(gaps_f):.3f} max={max(gaps_f):.3f}")
    print(f"GAP correctos: min={min(gaps_c):.3f} mediana={np.median(gaps_c):.3f} max={max(gaps_c):.3f}")
    print(f"RANGO_COS fallidos: mediana={np.median(rc_f):.1f} p90={np.percentile(rc_f, 90):.1f}")
    print(f"RANGO_COS correctos: mediana={np.median(rc_c):.1f} p90={np.percentile(rc_c, 90):.1f}")

    # --- Barrido de gates ---
    def evaluar_gate(filtro, nombre):
        activados = [r for r in rows_caso if filtro(r)]
        tpr = sum(1 for r in activados if r["fallido"]) / n_fallidos
        fpr = sum(1 for r in activados if not r["fallido"]) / n_correctos
        # techo del fallback oráculo sobre los activados: esperado en top-5 de su isla
        rescate_oraculo = 0
        for r in activados:
            if not r["fallido"]:
                continue
            if r["esp"] not in idx_por_concepto or r["com_esp"] is None:
                continue
            miem = [c for c in miembros_por_com[r["com_esp"]] if c in idx_por_concepto]
            if not miem:
                continue
            vq = idx.vector_query(_tokenizar(r["q"]))
            vq = vq / np.linalg.norm(vq)
            sims = {m: float(np.dot(vq, vn[m])) for m in miem}
            top5 = sorted(sims, key=sims.get, reverse=True)[:5]
            if r["esp"] in top5:
                rescate_oraculo += 1
        return tpr, fpr, rescate_oraculo

    print("\n" + "=" * 78)
    print("[A] GATE POR GAP top1-top2 (activa si gap < umbral)")
    print(f"{'umbral':<8}{'TPR(13)':<10}{'FPR(48)':<10}{'superset':<10}{'fallidos_en':<13}{'correctos_en':<13}{'techo_orac':<11}")
    for u in GAPS:
        tpr, fpr, resc = evaluar_gate(lambda r, u=u: r["gap"] is not None and r["gap"] < u, f"gap<{u}")
        act = [r for r in rows_caso if r["gap"] is not None and r["gap"] < u]
        n_act = len(act)
        n_f = sum(1 for r in act if r["fallido"])
        n_c = n_act - n_f
        print(f"{u:<8.2f}{tpr:<10.3f}{fpr:<10.3f}{n_act:<10}{n_f:<13}{n_c:<13}{resc:<11}")

    print("\n" + "=" * 78)
    print("[B] GATE POR RANGO_COS top-1 léxico (activa si rango > umbral)")
    print(f"{'umbral':<8}{'TPR(13)':<10}{'FPR(48)':<10}{'superset':<10}{'fallidos_en':<13}{'correctos_en':<13}{'techo_orac':<11}")
    for u in RANGOS:
        tpr, fpr, resc = evaluar_gate(lambda r, u=u: r["rango_cos"] is not None and r["rango_cos"] > u, f"rango>{u}")
        act = [r for r in rows_caso if r["rango_cos"] is not None and r["rango_cos"] > u]
        n_act = len(act)
        n_f = sum(1 for r in act if r["fallido"])
        n_c = n_act - n_f
        print(f"{u:<8}{tpr:<10.3f}{fpr:<10.3f}{n_act:<10}{n_f:<13}{n_c:<13}{resc:<11}")

    print("\n" + "=" * 78)
    print("[C] GATE COMBINADO AND (gap < g AND rango_cos > r) — barrido fino")
    print(f"{'gap':<6}{'rango':<7}{'TPR(13)':<10}{'FPR(48)':<10}{'superset':<10}{'fallidos_en':<13}{'correctos_en':<13}{'techo_orac':<11}")
    best = (0, None, None)
    for g in [0.05, 0.08, 0.10, 0.12, 0.15]:
        for r in [3, 5, 8, 12, 20]:
            tpr, fpr, resc = evaluar_gate(
                lambda x, g=g, r=r: (x["gap"] is not None and x["gap"] < g
                                      and x["rango_cos"] is not None and x["rango_cos"] > r),
                f"gap<{g}&rango>{r}")
            act = [x for x in rows_caso
                   if x["gap"] is not None and x["gap"] < g
                   and x["rango_cos"] is not None and x["rango_cos"] > r]
            n_act = len(act)
            n_f = sum(1 for x in act if x["fallido"])
            n_c = n_act - n_f
            marca = ""
            if resc > best[0]:
                best = (resc, g, r)
                marca = "  <== best"
            if n_act > 0:
                print(f"{g:<6.2f}{r:<7}{tpr:<10.3f}{fpr:<10.3f}{n_act:<10}{n_f:<13}{n_c:<13}{resc:<11}{marca}")

    print(f"\nBEST techo oráculo: {best[0]} rescatados con gap<{best[1]} & rango_cos>{best[2]}")
    print(f"(techo máximo del diseño: 11 — oráculo sobre los 13)")

    # techo oráculo global (sin gate): todos los fallidos con isla oráculo
    tpr, fpr, resc = evaluar_gate(lambda r: r["fallido"] or True, "global")
    print(f"\nTecho oráculo GLOBAL (sin gate, todos los 13): {resc}/13")

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
