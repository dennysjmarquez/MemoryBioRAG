#!/usr/bin/env python3
"""Fase A: re-evaluar los 921 casos contra un snapshot con Signal #12 restaurada.
Uso: BIORAG_PATH=<snapshot> python3 scripts/experimento_faseA_eval.py [out.json]"""
import os
import sys
import re
import json
import time
import sqlite3
import unicodedata
from multiprocessing import Process, Queue

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
from core.memory_store import SQLiteMemoryBioRAG

_STOP = {
    'de', 'la', 'el', 'que', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por',
    'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero',
    'sus', 'le', 'ya', 'o', 'este', 'si', 'porque', 'esta', 'entre', 'cuando',
    'muy', 'sin', 'sobre', 'tambien', 'me', 'hasta', 'hay', 'donde', 'quien',
    'es', 'son', 'fue', 'era', 'ser', 'est', 'mi', 'tu', 'te', 'les', 'nos',
    'he', 'ha', 'han', 'hemos', 'tener', 'tiene', 'hacer', 'se', '_'
}


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def tokens(t):
    out = []
    for w in t.split():
        wc = strip_accents(w)
        if wc not in _STOP and len(w) >= 2:
            out.append(wc)
    return set(out)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_cases():
    cases = []
    with open(os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def worker(worker_id, chunk, src_db, out_queue):
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", f"_faseA_w{worker_id}.db")
    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    results = []
    for case in chunk:
        category = case["categoria"]
        query = case["query"]
        expected = case.get("concepto_esperado")
        deep = case.get("deep", False)
        if expected:
            estado = "dormido" if (category == "dormido" or deep) else "activo"
            db.cursor.execute("UPDATE largo_plazo SET estado = ? WHERE concepto = ?", (estado, expected))
            db.conn.commit()
        profundidad = "profundo" if (deep or category in ("dormido", "negativo")) else "activos"
        q_tok = tokens(query)
        r, _ = db.buscar_por_frase(query, profundidad=profundidad, limite=100, ignore_peso_sinaptico=True)
        pool = []
        for item in r:
            conc = item[0]
            cont = item[1] or ""
            score = item[4]
            pool.append({"concepto": conc, "score": score, "jaccard": jaccard(q_tok, tokens(cont[:3000]))})
        results.append({
            "id": case["id"],
            "categoria": category,
            "expected": expected,
            "query": query,
            "pool": pool,
        })
    db.conn.close()
    os.remove(temp_db)
    out_queue.put((worker_id, results))


def main():
    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base_dir, "scripts", "experimento_faseA_pool.json")
    casos = load_cases()
    n_workers = 4
    chunks = [casos[i::n_workers] for i in range(n_workers)]

    print(f"Corriendo {len(casos)} casos contra {src_db}...")
    q = Queue()
    procs = []
    start = time.time()
    for i, ch in enumerate(chunks):
        p = Process(target=worker, args=(i, ch, src_db, q))
        p.start()
        procs.append(p)
    all_results = []
    for _ in procs:
        wid, res = q.get()
        all_results.extend(res)
    for p in procs:
        p.join()
    print(f"Corrida total: {time.time()-start:.1f}s")

    all_results.sort(key=lambda c: c["id"])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False)
    print(f"Guardado: {out_path}")


if __name__ == "__main__":
    main()
