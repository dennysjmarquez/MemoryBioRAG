#!/usr/bin/env python3
"""Verificación de consistencia del baseline Tejedora (respuesta al auditor).

Pregunta: ¿el baseline 94.67% (pool congelado ago-4) corresponde al sistema con
BIORAG_RERANKING_JACCARD_ENABLED en 0 o en 1?

Método: re-ejecutar los 921 casos contra el snapshot de Fase 0
(tejedora_pre_fase0_20260805_220447.db) con flag explícito OFF y ON, medir R@5/R@1
global, y comparar contra:
  - pool congelado  (ago 4): 94.67% / R@1 86.38
  - techo vivo      (ago 2): 94.78% (835/881, snapshot_prf_real.db)

Outputs:
  scripts/tejedora_verif_flag_off.json
  scripts/tejedora_verif_flag_on.json
"""
import sys
import os
import json
import sqlite3
import time
from collections import defaultdict
from multiprocessing import Process, Queue

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

SNAP = os.path.join(BASE, "snapshots", "tejedora_pre_fase0_20260805_220447.db")
POOL = os.path.join(BASE, "scripts", "experimento_rr_pool.json")


def load_cases():
    with open(os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def worker(worker_id, chunk, src_db, flag, out_queue):
    base = BASE
    tmp = os.path.join(base, "MemoryBioRAG_Data", f"_exp_verif_{flag}_{worker_id}.db")
    with sqlite3.connect(src_db) as s, sqlite3.connect(tmp) as d:
        s.backup(d)
    os.environ["BIORAG_RERANKING_JACCARD_ENABLED"] = flag
    from core.memory_store import SQLiteMemoryBioRAG
    db = SQLiteMemoryBioRAG(db_path=tmp)
    results = []
    for case in chunk:
        expected = case.get("concepto_esperado")
        deep = case.get("deep", False)
        cat = case["categoria"]
        if cat == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
        profundidad = "profundo" if (deep or cat in ("dormido", "negativo")) else "activos"
        r, _ = db.buscar_por_frase(case["query"], profundidad=profundidad, limite=100, ignore_peso_sinaptico=True)
        pool = [{"concepto": item[0], "score": item[4]} for item in r]
        results.append({"id": case["id"], "categoria": cat, "expected": expected, "pool": pool})
    db.conn.close()
    os.remove(tmp)
    out_queue.put((worker_id, results))


def metrics(cases):
    stats = defaultdict(lambda: {"total": 0, "hits5": 0, "hits1": 0})
    for c in cases:
        exp = c["expected"]
        stats[c["categoria"]]["total"] += 1
        for i, it in enumerate(c["pool"][:5]):
            if it["concepto"] == exp:
                stats[c["categoria"]]["hits5"] += 1
                stats[c["categoria"]]["hits1"] += 1 if i == 0 else 0
                break
    return stats


def run(flag):
    casos = load_cases()
    n_workers = 4
    chunks = [casos[i::n_workers] for i in range(n_workers)]
    q = Queue()
    procs = [Process(target=worker, args=(i, ch, SNAP, flag, q)) for i, ch in enumerate(chunks)]
    t0 = time.time()
    for p in procs:
        p.start()
    all_res = []
    for _ in procs:
        _, res = q.get()
        all_res.extend(res)
    for p in procs:
        p.join()
    all_res.sort(key=lambda c: c["id"])
    st = metrics(all_res)
    tot_n = tot5 = tot1 = 0
    for cat, s in st.items():
        if cat == "negativo":
            continue
        tot_n += s["total"]; tot5 += s["hits5"]; tot1 += s["hits1"]
    out = {
        "flag": flag,
        "snapshot": os.path.basename(SNAP),
        "n_casos_no_negativo": tot_n,
        "R@5_global_pct": round(100.0 * tot5 / tot_n, 2),
        "R@1_global_pct": round(100.0 * tot1 / tot_n, 2),
        "hits5": tot5, "hits1": tot1,
        "tiempo_s": round(time.time() - t0, 1),
        "por_categoria": {k: {"n": v["total"], "hits5": v["hits5"], "hits1": v["hits1"]} for k, v in st.items()},
    }
    split = json.load(open(os.path.join(BASE, "scripts", "tejedora_split_50_50.json"), encoding="utf-8"))
    mitad_a = {c["id"] for c in split["mitad_A"]}
    mitad_b = {c["id"] for c in split["mitad_B"]}
    per_half = {}
    for half_name, ids in (("A", mitad_a), ("B", mitad_b)):
        half_cases = [c for c in all_res if c["id"] in ids and c["categoria"] != "negativo"]
        st = metrics(half_cases)
        n = sum(s["total"] for s in st.values())
        h5 = sum(s["hits5"] for s in st.values())
        h1 = sum(s["hits1"] for s in st.values())
        per_half[half_name] = {
            "n": n, "hits5": h5, "hits1": h1,
            "R@5_pct": round(100.0 * h5 / n, 2) if n else None,
            "R@1_pct": round(100.0 * h1 / n, 2) if n else None,
        }
    out["por_mitad"] = per_half

    per_case = []
    for c in all_res:
        exp = c["expected"]
        hit1 = hit5 = 0
        if any(it["concepto"] == exp for it in c["pool"][:5]):
            hit5 = 1
        if c["pool"] and c["pool"][0]["concepto"] == exp:
            hit1 = 1
        per_case.append({
            "id": c["id"], "categoria": c["categoria"],
            "mitad": "A" if c["id"] in mitad_a else "B" if c["id"] in mitad_b else None,
            "hit1": hit1, "hit5": hit5,
            "expected": exp,
            "pool_top5": [{"concepto": it["concepto"], "score": it["score"]} for it in c["pool"][:5]],
        })
    out["por_caso"] = per_case

    path = os.path.join(BASE, "scripts", f"tejedora_verif_flag_{flag}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"flag={flag}: R@5={out['R@5_global_pct']}% R@1={out['R@1_global_pct']}% "
          f"({tot5}/{tot_n}) {out['tiempo_s']}s -> {os.path.relpath(path, BASE)}")
    print(f"  por mitad: {per_half}")
    return out


if __name__ == "__main__":
    flags = os.environ.get("VERIF_FLAGS", "0").split(",")
    results = {}
    for fl in flags:
        results[fl] = run(fl.strip())
    print("\n=== COMPARACIÓN ===")
    print(f"pool congelado ago-4 : R@5 94.67  R@1 86.38  (pool congelado, sin jaccard - flag no existía)")
    print(f"techo vivo ago-2     : R@5 94.78 (835/881)  (medición viva, snapshot_prf_real.db, sin jaccard)")
    for fl, res in results.items():
        print(f"snapshot Fase0 flag={fl}: R@5 {res['R@5_global_pct']} ({res['hits5']}/{res['n_casos_no_negativo']})  R@1 {res['R@1_global_pct']}")
