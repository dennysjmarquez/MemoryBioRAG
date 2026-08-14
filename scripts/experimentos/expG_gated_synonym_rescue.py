"""
Experimento G — Gated Fallback Condicional por Score Top-1 (2026-08-14).

Propuesta del auditor (Claude Web, vía Dennys) tras refutar la Fase B (softmax global):
el rescate de sinonimia NUNCA debe alterar el ranking cuando el pipeline primario ya
gana. Solo se abre una puerta (gate) cuando el top-1 está "a oscuras" (score bajo o
sin match FTS5), y dentro de esa puerta se re-rankea por la señal de sinonimo IDF
(es la Opcion A del auditor; usa core/ppmi_hybrid_search.py:idf_sin).

Preguntas empiricas que este script contesta (no asumidas):
  Q1. Distribucion real de score top-1 (pipeline estandar, limite=5, ignore_peso):
      los 49 correctos realmente viven arriba de 0.60? los 12 fallidos abajo?
      Si los rangos se solapan, "0 regresiones garantizadas" NO es cierto — se mide.
  Q2. Con gate score_top1 < umbral, cuantos correctos entran (riesgo de romper) y
      cuantos fallidos se activan (oportunidad de rescate) para cada umbral.
  Q3. Re-ranking intra-pool por idf_sin: cuantos fallidos rescatados vs correctos rotos
      dentro del gate, para umbrales [0.50, 0.55, 0.60, 0.65, 0.70].

Disciplina: copia aislada del snapshot a temp, solo lectura, NO toca produccion.

Uso:
    python3 scripts/experimentos/expG_gated_synonym_rescue.py
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
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe_temp_g.db")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")

UMBRALES = [0.50, 0.55, 0.60, 0.65, 0.70]


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
    copiar_a_temp()
    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)
    idx = IndicesBioRAG(TEMP_DB)

    casos = [json.loads(l) for l in open(CASES) if l.strip()]
    sin = [c for c in casos if c.get("categoria") == "sinonimo"]

    # ---- Q1/Q2: score top-1 real por caso (pipeline estandar) ----
    info = []
    for caso in sin:
        q = caso["query"]
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5,
                                     ignore_peso_sinaptico=True)
        top5 = [r[0] for r in res]
        score_top1 = res[0][4] if res else 0.0
        ok = caso["concepto_esperado"] in top5
        info.append({
            "caso": caso, "top5": top5, "score_top1": score_top1, "ok": ok,
        })

    correctos = [i for i in info if i["ok"]]
    fallidos = [i for i in info if not i["ok"]]
    print(f"casos sinonimo: {len(sin)} | correctos: {len(correctos)} | fallidos: {len(fallidos)}")

    print("\n[1] DISTRIBUCION score_top1 (pipeline estandar limite=5)")
    for label, grp in [("correctos", correctos), ("fallidos", fallidos)]:
        scores = sorted(i["score_top1"] for i in grp)
        med = scores[len(scores) // 2]
        mn, mx = scores[0], scores[-1]
        print(f"  {label:<9} n={len(grp):<3} min={mn:.3f} mediana={med:.3f} max={mx:.3f}")
        print(f"             scores: {', '.join(f'{s:.2f}' for s in scores)}")

    # Cuantos correctos/fallidos quedan bajo cada umbral (solapamiento = riesgo)
    print("\n[2] GATE score_top1 < umbral (cuantos casos entrarian al fallback)")
    print(f"  {'umbral':<8}{'correctos_en_gate':<19}{'fallidos_en_gate':<17}")
    for u in UMBRALES:
        c = sum(1 for i in correctos if i["score_top1"] < u)
        f = sum(1 for i in fallidos if i["score_top1"] < u)
        print(f"  {u:<8.2f}{c:<19}{f:<17}")

    # ---- Q3: pool + re-ranking idf_sin dentro del gate ----
    print("\n[3] RE-RANKING idf_sin dentro del gate (pool limite=200)")
    print("     rescates: fallidos que vuelven al top5 | rotos: correctos que se caen del top5")
    print(f"  {'umbral':<8}{'rescates':<10}{'rotos':<8}{'neto':<6}")
    print("-" * 40)
    detalle_mejor = None
    mejor = (0.0, -1, -1, None)  # (umbral, rescates, rotos, detalle)
    for u in UMBRALES:
        rescates = 0
        rotos = 0
        detalle = {}
        for i in info:
            q = i["caso"]["query"]
            esp = i["caso"]["concepto_esperado"]
            if i["score_top1"] >= u:
                continue  # gate cerrado: pipeline intacto
            # gate abierto: recuperar pool amplio y re-rankear por idf_sin
            res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                         ignore_peso_sinaptico=True)
            pool_set = {r[0] for r in res}
            q_toks_unique = set(_tokenizar(q))
            ranked = []
            for conc, _sc in res:
                s_idf = idx.idf_sin(q_toks_unique, conc, pool_set)
                ranked.append((s_idf, conc))
            ranked.sort(key=lambda x: x[0], reverse=True)
            top5_gate = {c for _, c in ranked[:5]}
            # solo cuentan nodos del pool real (evitar nodos fantasma)
            top5_gate &= pool_set
            if len(top5_gate) < 5:
                top5_gate = {c for _, c in ranked[:5]}
            ok_gate = esp in top5_gate
            if i["ok"]:
                if not ok_gate:
                    rotos += 1
                    detalle[i["caso"]["id"]] = "ROTO"
            else:
                if ok_gate:
                    rescates += 1
                    detalle[i["caso"]["id"]] = "RESCATADO"
        neto = rescates - rotos
        print(f"  {u:<8.2f}{rescates:<10}{rotos:<8}{neto:<6}")
        if (rescates, -rotos) > (mejor[1], -mejor[2]):
            mejor = (u, rescates, rotos, detalle)

    print("\n[4] DETALLE para el mejor umbral "
          f"(umbral={mejor[0]:.2f}, rescates={mejor[1]}, rotos={mejor[2]}):")
    for i in info:
        q = i["caso"]["query"]
        esp = i["caso"]["concepto_esperado"]
        estado = mejor[3].get(i["caso"]["id"], "-")
        cls = "fallido" if not i["ok"] else "correcto"
        print(f"  {estado:<10} [{cls:<8}] score_top1={i['score_top1']:.3f} "
              f"| '{q}' -> {esp}")

    # limpieza
    for f in [TEMP_DB, TEMP_DB + "-wal", TEMP_DB + "-shm"]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    main()
