"""
Experimento G3 — Impacto de la variante refinada sobre las 921 casos completas.

Contexto: expG2 midió la variante refinada (proteger baseline si >=3/5 del top-5
tienen el token de la query en su concepto; re-rankear por idf_sin si no; guard
obligatorio: query no tokenizable => proteger) SOLO sobre las 61 casos sinonimo:
6 rescates, 0 rotos, neto +6.

Antes de tocar producción hay que saber si ese gate rompe algo en las OTRAS
categorías (literal, typo, variante_gramatical, por_tema, pregunta_natural,
cruce_idioma, dormido, negativo). Un re-ranking idf_sin que salva sinonimo podría
desplazar matchs directos si la query no matchea con el concepto esperado.

Este script replica fielmente el scoring del pipeline real (buscar_por_frase con
los mismos parámetros de evaluar_qa.py) y compara, caso a caso, si el esperado
está en el top-5 del baseline vs top-5 de la variante refinada. Reporta por
categoría y global.

Disciplina: copia aislada del snapshot a temp, solo lectura, NO toca producción.
Uso:
    python3 scripts/experimentos/expG3_refinado_921_casos.py
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe_temp_g3.db")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")


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


def tokens(s):
    return set(_tokenizar(s))


def baseline(db, q):
    res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5,
                                 ignore_peso_sinaptico=True)
    return [r[0] for r in res]


def pool_real(db, q):
    todos = getattr(db, "last_todos", []) or []
    if todos and isinstance(todos[0], tuple) and len(todos[0]) > 1:
        return {r[1] for r in todos}
    res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                 ignore_peso_sinaptico=True)
    return {r[0] for r in res}


def rerank_idf(idx, qt, pool_set, topn=5):
    ranked = sorted(((idx.idf_sin(qt, cn, pool_set), cn) for cn in pool_set),
                    key=lambda x: x[0], reverse=True)
    return [cn for _, cn in ranked[:topn]]


def gate_refinado(top5, qt):
    """Variante refinada + guard. True => proteger baseline (no re-rankear)."""
    if not qt:
        return True  # query no tokenizable: sin señal de idf_sin, proteger
    n = sum(1 for cn in top5 if qt & tokens(cn))
    return n >= 3


def main():
    copiar_a_temp()
    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)
    idx = IndicesBioRAG(TEMP_DB)

    casos = [json.loads(l) for l in open(CASES) if l.strip()]
    print(f"casos totales: {len(casos)}")

    stats = defaultdict(lambda: {"total": 0, "ok_base": 0, "ok_ref": 0,
                                 "rescatados": [], "rotos": []})
    detalle = []
    for caso in casos:
        q = caso["query"]
        esp = caso["concepto_esperado"]
        cat = caso.get("categoria", "?")
        top5 = baseline(db, q)
        ok_base = esp in top5
        pool = pool_real(db, q)
        qt = tokens(q)
        if gate_refinado(top5, qt):
            top5_ref = top5
        else:
            top5_ref = rerank_idf(idx, qt, pool)
        ok_ref = esp in top5_ref

        s = stats[cat]
        s["total"] += 1
        if ok_base:
            s["ok_base"] += 1
        if ok_ref:
            s["ok_ref"] += 1
        if not ok_base and ok_ref:
            s["rescatados"].append(caso["id"])
        if ok_base and not ok_ref:
            s["rotos"].append(caso["id"])
        detalle.append({"id": caso["id"], "cat": cat, "ok_base": ok_base,
                        "ok_ref": ok_ref, "gate_abierto": not gate_refinado(top5, qt)})

    print("\n=== POR CATEGORIA ===")
    print(f"{'categoria':<20} {'total':>5} {'base R@5':>9} {'ref R@5':>9} "
          f"{'delta':>5}  rescatados/rotos")
    tot_base = tot_ref = 0
    for cat in sorted(stats):
        s = stats[cat]
        tot_base += s["ok_base"]
        tot_ref += s["ok_ref"]
        pct_b = s["ok_base"] / s["total"] * 100
        pct_r = s["ok_ref"] / s["total"] * 100
        print(f"{cat:<20} {s['total']:>5} {pct_b:>7.1f}% {pct_r:>7.1f}% "
              f"{pct_r-pct_b:>+5.1f}  {len(s['rescatados'])}/{len(s['rotos'])}")
        if s["rescatados"]:
            print(f"    rescatados: {s['rescatados']}")
        if s["rotos"]:
            print(f"    ROTOS: {s['rotos']}")

    n = len(casos)
    print(f"\n=== GLOBAL ===")
    print(f"R@5 baseline: {tot_base/n*100:.2f}%  |  R@5 refinada: {tot_ref/n*100:.2f}%")
    print(f"delta: {tot_ref-tot_base:+d} casos sobre {n}")

    print("\n=== CASOS DONDE EL GATE SE ABRIO (re-rankearon) ===")
    abiertos = [d for d in detalle if not d["gate_abierto"]]
    for d in abiertos:
        print(f"  {d['id']} [{d['cat']}] {'RESCATADO' if (not d['ok_base'] and d['ok_ref']) else ('ROTO' if (d['ok_base'] and not d['ok_ref']) else 'sin cambio')}")

    # limpieza
    for f in [TEMP_DB, TEMP_DB + "-wal", TEMP_DB + "-shm"]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    main()
