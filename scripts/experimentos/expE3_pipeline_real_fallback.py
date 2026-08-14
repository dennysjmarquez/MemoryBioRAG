"""
Experimento E3 — Pipeline real completo del fallback condicional (2026-08-13).

Decisión: ¿vale la pena invertir en la expansión de query (cara) sabiendo que el gate
la limita? E2 mostró que el techo realista del diseño es +3 a +5 con proyección ORÁCULO.
Pero en producción no hay oráculo: la proyección real query->isla es coseno (3/13 solo).
Falta medir el NETO REAL del pipeline completo simulado tal como correría en producción:

  1. Ranking léxico global (intacto, limite=200).
  2. Gate de activación predictivo (gap y/o rango_cos) — decide si el caso "parece"
     resuelto mal. NO usa ground truth.
  3. Solo si el gate activa: proyección REAL por coseno query->centroide (top-1 isla),
     y re-ranking léxico intra-isla como resultado final.
  4. Neto = fallidos rescatados - correctos rotos, sobre los 61.

Este experimento separa el techo (E2, oráculo) del neto real (E3, producción). Si el
neto real es positivo en algún punto del barrido de gates, la expansión de query tiene
sentido (mejorar la proyección levanta más el neto). Si es <=0 en todos los gates, la
expansión NO puede desplegarse sola: el gate es el cuello y atacarlo es primero.

Disciplina: copia temp, mismo pool/score que evaluar_qa.py. Solo lectura de la fuente.

Uso:
    python3 scripts/experimentos/expE3_pipeline_real_fallback.py
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
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe3_temp.db")
LABELS = os.path.join(BASE, "scripts", "experimentos", "expA_labels.json")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")
FALLIDOS = os.path.join(BASE, "scripts", "casos_fallidos.jsonl")

GATES = {
    "sin_gate (baseline global)": lambda r: True,
    "gap<0.03": lambda r: r["gap"] is not None and r["gap"] < 0.03,
    "gap<0.05": lambda r: r["gap"] is not None and r["gap"] < 0.05,
    "gap<0.15": lambda r: r["gap"] is not None and r["gap"] < 0.15,
    "rango_cos>8": lambda r: r["rango_cos"] is not None and r["rango_cos"] > 8,
    "rango_cos>12": lambda r: r["rango_cos"] is not None and r["rango_cos"] > 12,
    "rango_cos>20": lambda r: r["rango_cos"] is not None and r["rango_cos"] > 20,
    "gap<0.05 & rango>8": lambda r: (r["gap"] is not None and r["gap"] < 0.05
                                     and r["rango_cos"] is not None and r["rango_cos"] > 8),
    "gap<0.15 & rango>8": lambda r: (r["gap"] is not None and r["gap"] < 0.15
                                     and r["rango_cos"] is not None and r["rango_cos"] > 8),
}


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

    rows_caso = []
    for caso in sin:
        q = caso["query"]
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                     ignore_peso_sinaptico=True)
        pool = {r[0]: r[4] for r in res}
        pool_order = [r[0] for r in res]
        toks = _tokenizar(q)
        vq = None
        if toks:
            vq = idx.vector_query(toks)
            if np.linalg.norm(vq) > 1e-10:
                vq = vq / np.linalg.norm(vq)
        gap = None
        if len(pool_order) >= 2:
            gap = pool[pool_order[0]] - pool[pool_order[1]]
        rango_cos = None
        if vq is not None and pool_order:
            cos_all = centro_mat @ vq  # coseno query->islas
            order = np.argsort(-cos_all)
            rank_por_isla = {comun_ordenadas[i]: int(rp) for rp, i in enumerate(order)}
            # rango de la isla del top-1 léxico dentro del ranking de islas
            com_top1 = com_por_concepto.get(pool_order[0])
            rango_cos = rank_por_isla.get(com_top1) if com_top1 is not None else None
        esp = caso["concepto_esperado"]
        rows_caso.append({
            "id": caso["id"], "q": q, "esp": esp, "pool": pool,
            "pool_order": pool_order, "vq": vq, "gap": gap, "rango_cos": rango_cos,
            "fallido": caso["id"] in fallidos_ids,
            "com_esp": com_por_concepto.get(esp),
        })

    n_fallidos = sum(1 for r in rows_caso if r["fallido"])
    n_correctos = sum(1 for r in rows_caso if not r["fallido"])
    print(f"casos sinonimo: {len(sin)} | fallidos: {n_fallidos} | correctos: {n_correctos}")

    print(f"\n{'gate':<26}{'activa':<8}{'resc_fall':<11}{'rotos_corr':<12}"
          f"{'neto':<7}{'tpr':<7}{'fpr':<7}{'techo_orac_act':<15}")
    print("-" * 90)

    for nombre, filtro in GATES.items():
        activados = [r for r in rows_caso if filtro(r)]
        rescatados = 0
        rotos = 0
        detalle = []
        techo_orac = 0
        for r in activados:
            # Fallback: proyección REAL top-1 isla por coseno query->centroide
            vq = r["vq"]
            esp = r["esp"]
            if vq is not None and esp in idx_por_concepto:
                sims = centro_mat @ vq
                isla_top1 = comun_ordenadas[int(np.argmax(sims))]
                miem = [c for c in miembros_por_com.get(isla_top1, []) if c in idx_por_concepto]
                intra = {n: s for n, s in r["pool"].items() if n in miem}
                ranked = sorted(intra.items(), key=lambda x: x[1], reverse=True)
                top5 = [n for n, _ in ranked[:5]]
                ok = esp in top5
                # techo oráculo: misma señal pero con la isla CORRECTA
                miem_orac = [c for c in miembros_por_com.get(r["com_esp"], []) if c in idx_por_concepto]
                intra_orac = {n: s for n, s in r["pool"].items() if n in miem_orac}
                ranked_orac = sorted(intra_orac.items(), key=lambda x: x[1], reverse=True)
                ok_orac = esp in [n for n, _ in ranked_orac[:5]]
            else:
                ok = esp in r["pool_order"][:5]
                ok_orac = ok
            if r["fallido"]:
                if ok:
                    rescatados += 1
                if ok_orac:
                    techo_orac += 1
            else:
                if not ok:
                    rotos += 1
            detalle.append((r["id"], esp, ok, ok_orac, r["fallido"]))
        neto = rescatados - rotos
        n_act = len(activados)
        n_f_act = sum(1 for r in activados if r["fallido"])
        tpr = rescatados / n_fallidos if n_fallidos else 0
        fpr = rotos / n_correctos if n_correctos else 0
        print(f"{nombre:<26}{n_act:<8}{rescatados:<11}{rotos:<12}{neto:<7}"
              f"{tpr:<7.3f}{fpr:<7.3f}{techo_orac:<15}")

        if nombre == "rango_cos>20" or nombre == "gap<0.05 & rango>8":
            print("    detalle (id, esperado, rescatado, techo_orac, es_fallido):")
            for d in detalle:
                print(f"      {d[0]} | {d[1]} | real={d[2]} | orac={d[3]} | fallido={d[4]}")

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
