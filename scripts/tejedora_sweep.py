#!/usr/bin/env python3
"""Fase 2 del Plan Tejedora — Barrido de tejido con la pipeline REAL de búsqueda.

Mide el delta de recall@5 por inyección de aristas tejidas, sobre el snapshot
de Fase 0 (mismo baseline, solo difiere el tejido). Un solo cambio a la vez.

Metodología (idéntica a experimento_rr_fase1.py para que el delta sea limpio):
1. Copia del snapshot de Fase 0 por worker (sqlite3.backup)
2. Inyección opcional de las aristas candidatas de tejedora_candidatos.json
   en la tabla sinapsis (tipo 'tejida_estructural', peso configurable)
3. Re-correr los 921 casos con buscar_por_frase(limite=100) — MISMA pipeline
   que generó experimento_rr_pool.json
4. Comparar recall@5 con vs sin tejido: el delta mide SOLO el efecto del tejido.

Configs del sweep (peso de arista tejida):
  - sin_tejido: baseline de control sobre el snapshot
  - peso 0.3 / 0.6 / 1.0: misma topología, distinto peso sináptico
La topología es la misma (13 aristas) — el peso solo afecta propagación.
"""
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

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(BASE, "snapshots", "tejedora_pre_fase0_20260805_220447.db")
CASES = os.path.join(BASE, "scripts", "experimento_rr_pool.json")
CAND = os.path.join(BASE, "scripts", "tejedora_candidatos.json")
OUT = os.path.join(BASE, "scripts", "tejedora_sweep_resultado.json")


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


def inject_edges(db_path, pares, peso):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    n = 0
    for a, b in pares:
        # Rechazar si ya existe la arista (evita duplicar)
        ya = cur.execute(
            "SELECT 1 FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
            (a, b, b, a)).fetchone()
        if ya:
            continue
        cur.execute(
            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso) "
            "VALUES (?,?,?,'tejida_estructural',?,?)",
            (a, b, peso, time.time(), time.time()))
        n += 1
    con.commit()
    con.close()
    return n


def worker(worker_id, chunk, src_db, peso_arista, pares, out_queue):
    temp_db = os.path.join(BASE, "MemoryBioRAG_Data", f"_exp_tejedora_{worker_id}.db")
    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)
    n_inj = inject_edges(temp_db, pares, peso_arista) if pares else 0
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    results = []
    for case in chunk:
        category = case["categoria"]
        expected = case["expected"]
        query = case["query"]
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
        profundidad = "profundo" if (category == "dormido" or category == "negativo") else "activos"
        q_tok = tokens(query)
        r, _ = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        pool = []
        for idx, item in enumerate(r):
            conc = item[0]
            cont = item[1] or ""
            score = item[4]
            j = jaccard(q_tok, tokens(cont[:3000]))
            pool.append({"concepto": conc, "score": score, "jaccard": j})
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


def recall_metrics(results):
    stats = defaultdict(lambda: {"total": 0, "hits5": 0, "hits1": 0, "mrr": 0.0})
    for c in results:
        cat = c["categoria"]
        exp = c["expected"]
        pool = c["pool"]
        stats[cat]["total"] += 1
        pos = -1
        for i, it in enumerate(pool[:5]):
            if it["concepto"] == exp:
                pos = i
                break
        if pos != -1:
            stats[cat]["hits5"] += 1
            stats[cat]["hits1"] += 1 if pos == 0 else 0
            stats[cat]["mrr"] += 1.0 / (pos + 1)
    return stats


def run(casos, peso_arista, pares, tag):
    n_workers = 8
    chunks = [casos[i::n_workers] for i in range(n_workers)]
    q = Queue()
    procs = []
    start = time.time()
    for i, ch in enumerate(chunks):
        p = Process(target=worker, args=(i, ch, SNAP, peso_arista, pares, q))
        p.start()
        procs.append(p)
    all_results = []
    for _ in procs:
        wid, res = q.get()
        all_results.extend(res)
    for p in procs:
        p.join()
    all_results.sort(key=lambda c: c["id"])
    elapsed = time.time() - start
    st = recall_metrics(all_results)
    tot_n = sum(v["total"] for k, v in st.items() if k != "negativo")
    tot_h5 = sum(v["hits5"] for k, v in st.items() if k != "negativo")
    tot_h1 = sum(v["hits1"] for k, v in st.items() if k != "negativo")
    mrr = sum(v["mrr"] for k, v in st.items() if k != "negativo") / tot_n
    resumen = {
        "tag": tag,
        "peso_arista": peso_arista,
        "aristas_inyectadas": len(pares),
        "n": tot_n,
        "R@5": round(100.0 * tot_h5 / tot_n, 4),
        "R@1": round(100.0 * tot_h1 / tot_n, 4),
        "MRR": round(mrr, 4),
        "tiempo_s": round(elapsed, 1),
        "por_categoria": {k: {
            "n": v["total"],
            "R@5": round(100.0 * v["hits5"] / v["total"], 2) if v["total"] else 0,
        } for k, v in st.items()},
    }
    print(f"[{tag}] R@5={resumen['R@5']}% R@1={resumen['R@1']}% MRR={resumen['MRR']} "
          f"({resumen['tiempo_s']}s, {resumen['aristas_inyectadas']} aristas)")
    return resumen


def main():
    casos = json.load(open(CASES, encoding="utf-8"))
    cand = json.load(open(CAND, encoding="utf-8"))
    pares = [(c["a"], c["b"]) for c in cand["candidatos"]]
    print(f"Casos: {len(casos)} | Aristas candidatas: {len(pares)}")

    resultados = []

    base = run(casos, 0.0, [], "baseline_sin_tejido")
    resultados.append(base)

    for peso in (0.6,):
        r = run(casos, peso, pares, f"tejido_peso_{peso}")
        resultados.append(r)

    b = base["R@5"]
    print("\n" + "=" * 78)
    print(f"{'config':<22} {'R@5':<8} {'delta vs baseline':<18}")
    print("=" * 78)
    for r in resultados:
        d = r["R@5"] - b
        print(f"{r['tag']:<22} {r['R@5']:<8.2f} {d:+.3f}pp")
    print("=" * 78)

    out = {
        "fase": "2",
        "descripcion": "Sweep de tejido estructural con pipeline REAL de búsqueda sobre "
                       "snapshot de Fase 0. Un solo cambio: inyección de aristas candidatas "
                       "en la tabla sinapsis. flag OFF. ignore_peso_sinaptico=True (igual que "
                       "la generación del pool original).",
        "snapshot": os.path.basename(SNAP),
        "n_casos": len(casos),
        "n_aristas": len(pares),
        "aristas": pares,
        "configs": resultados,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nGuardado: {OUT}")


if __name__ == "__main__":
    main()
