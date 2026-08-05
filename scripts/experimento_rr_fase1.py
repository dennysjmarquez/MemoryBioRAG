import sys
import os
import json
import sqlite3
import re
import unicodedata
import time
from collections import defaultdict
from multiprocessing import Process, Queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.stopwords import _STOPWORDS_QUERY
from core.memory_store import SQLiteMemoryBioRAG

def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

def tokens(text):
    t = re.sub(r'[^\w\s_-]', ' ', text.lower())
    out = []
    for w in t.split():
        wc = strip_accents(w)
        if wc not in _STOPWORDS_QUERY and len(w) >= 2:
            out.append(wc)
    return set(out)

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def load_cases():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cases = []
    with open(os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases

def worker(worker_id, chunk, src_db, out_queue):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", f"_exp_rr_{worker_id}.db")
    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    results = []
    for case in chunk:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case.get("concepto_esperado")
        deep = case.get("deep", False)
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
        profundidad = "profundo" if (deep or category == "dormido" or category == "negativo") else "activos"
        q_tok = tokens(query)
        r, _ = db.buscar_por_frase(query, profundidad=profundidad, limite=100, ignore_peso_sinaptico=True)
        pool = []
        for idx, item in enumerate(r):
            conc = item[0]
            cont = item[1] or ""
            score = item[4]
            j = jaccard(q_tok, tokens(cont[:3000]))
            pool.append({"concepto": conc, "score": score, "jaccard": j})
        results.append({
            "id": case_id,
            "categoria": category,
            "expected": expected,
            "query": query,
            "pool": pool,
        })
    db.conn.close()
    os.remove(temp_db)
    out_queue.put((worker_id, results))

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    out_path = os.path.join(base_dir, "scripts", "experimento_rr_pool.json")
    casos = load_cases()
    n_workers = 4
    chunks = [casos[i::n_workers] for i in range(n_workers)]

    print(f"Corriendo {len(casos)} casos en {n_workers} workers (limite=100, snapshot sqlite3.backup)...")
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
        print(f"  worker {wid}: {len(res)} casos")
    for p in procs:
        p.join()
    print(f"Corrida total: {time.time()-start:.1f}s")

    all_results.sort(key=lambda c: c["id"])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False)
    print(f"Guardado: {out_path}")

if __name__ == "__main__":
    main()
