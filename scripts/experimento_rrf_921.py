"""
Experimento RRF (Reciprocal Rank Fusion) sobre los 921 casos del baseline.

Objetivo: medir si fusionar el ranking léxico de producción (buscar_por_frase)
con el ranking por coseno PPMI global rescata fallos sinonimo SIN dañar las
demás categorías (literal, por_tema, variante, typo, pregunta_natural, negativo).

Réplica EXACTA de la lógica de evaluar_qa.py (setup de estados, profundidad,
threshold FP 0.25) + inyección de RRF post-pool.

Uso:
  BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/experimento_rrf_921.py [k]

Comparar contra scripts/run_b_umbral_060.txt (baseline: R@5 96.03%, R@1 88.76%,
MRR 0.916, FP 25%).
"""
import os
import sys
import json
import sqlite3
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from core.memory_store import SQLiteMemoryBioRAG
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar


def load_labels():
    """Carga islas KNN-LPA si existen (expA_labels.json); si no, {} para no crashear."""
    labels_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "experimentos", "expA_labels.json"
    )
    if os.path.exists(labels_path):
        labels = json.load(open(labels_path))
        return dict(zip(labels["conceptos"], labels["knn_lpa"]))
    return {}


def run(k=60, umbral_gap=None, intra_pool=True):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env_local = os.path.join(base_dir, ".env.local")
    if os.path.exists(env_local):
        with open(env_local, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

    src_db = os.environ.get("BIORAG_PATH") or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    cases_file = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")

    # Copia aislada a temp (misma disciplina que evaluar_qa.py: no mutar la fuente)
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_rrf_temp.db")
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    conn_src = sqlite3.connect(src_db)
    conn_src.execute("PRAGMA wal_checkpoint(FULL);")
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_dst.close()
    conn_src.close()

    # --- Vectores PPMI globales (una vez, desde temp) ---
    conn_src = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
    vrows = conn_src.execute("SELECT concepto, vector FROM nodos").fetchall()
    conn_src.close()
    vmap = {r[0]: np.frombuffer(r[1], dtype=np.float32).astype("float64") for r in vrows}
    vn = {c: v / np.linalg.norm(v) for c, v in vmap.items()}
    mat = np.array([vn[c] for c in vn])
    node_list = list(vn)

    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    db = SQLiteMemoryBioRAG(db_path=temp_db)
    idx = IndicesBioRAG(temp_db)

    stats = defaultdict(lambda: {"total": 0, "hits_at_5": 0, "hits_at_1": 0, "reciprocal_rank_sum": 0, "false_positives": 0})
    failures_by_category = defaultdict(list)
    start = time.time()

    for case in cases:
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)
        stats[category]["total"] += 1

        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()

        profundidad = "profundo" if (deep or category == "dormido" or category == "negativo") else "activos"
        res, _ = db.buscar_por_frase(query, profundidad=profundidad, limite=200, ignore_peso_sinaptico=True)
        pool = list(dict.fromkeys([r[0] for r in res]))
        # Score híbrido REAL por nodo (para que el threshold FP 0.25 sea comparable al evaluador)
        pool_score = {r[0]: r[4] for r in res}

        # Gate de confianza: si el pool ya está decidido (gap top1-top2 grande), no tocar.
        # Evita que RRF rompa queries que la capa léxica ya resuelve bien (p.ej. literal).
        aplicar_rrf = True
        if umbral_gap is not None and len(pool) >= 2:
            gap = res[0][4] - res[1][4]
            aplicar_rrf = gap < umbral_gap
        elif umbral_gap is not None:
            aplicar_rrf = False  # pool trivial de 1 solo candidato: no hay nada que fusionar

        if not aplicar_rrf:
            results = [(r[0], r[4]) for r in res[:5]]
            total = len(results)
        else:
            # --- RRF intra-pool: fusiona rango léxico + coseno PPMI SOLO entre los
            # candidatos que la búsqueda léxica ya trajo (no mete nodos externos). ---
            toks = _tokenizar(query)
            scored = {}
            for i, node in enumerate(pool):
                scored[node] = scored.get(node, 0.0) + 1.0 / (k + i + 1)
            if toks:
                vq = idx.vector_query(toks)
                vq = vq / np.linalg.norm(vq)
                if intra_pool:
                    # Coseno PPMI restringido a los miembros del pool (índice local)
                    local = np.array([vn[c] for c in pool])
                    cos_local = local @ vq
                    order = np.argsort(-cos_local)
                    for rank_pos in order:
                        node = pool[rank_pos]
                        scored[node] = scored.get(node, 0.0) + 1.0 / (k + rank_pos + 1)
                else:
                    # Coseno PPMI GLOBAL (todos los nodos) — es la señal que rescató 4/13
                    cos_all = mat @ vq
                    order = np.argsort(-cos_all)
                    for rank_pos in range(len(order)):
                        node = node_list[order[rank_pos]]
                        scored[node] = scored.get(node, 0.0) + 1.0 / (k + rank_pos + 1)

            ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
            # Conserva el score híbrido real del nodo para la evaluación de FP
            results = [(node, pool_score.get(node, 0.0)) for node, _ in ranked[:5]]
            total = len(ranked)

        returned = [r[0] for r in results]
        scores = [r[1] for r in results]

        if expected is None:
            fps = [r for r in results if r[1] >= 0.25]
            if len(fps) > 0:
                stats[category]["false_positives"] += 1
                failures_by_category[category].append({
                    "id": case["id"], "query": query, "expected": None,
                    "returned": returned[:3], "scores": scores[:3],
                    "error": f"False positive returned with score {scores[0]}"
                })
        else:
            found_at = -1
            for idx_pos, concept in enumerate(returned):
                if concept == expected:
                    found_at = idx_pos + 1
                    break
            if found_at != -1:
                stats[category]["hits_at_5"] += 1
                stats[category]["reciprocal_rank_sum"] += 1.0 / found_at
                if found_at == 1:
                    stats[category]["hits_at_1"] += 1
                if category == "dormido":
                    db.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (expected,))
                    row = db.cursor.fetchone()
                    if not row or row[0] != "activo":
                        failures_by_category[category].append({
                            "id": case["id"], "query": query, "expected": expected,
                            "returned": returned[:3], "scores": scores[:3],
                            "error": f"Node found but remained dormant (state is {row[0] if row else 'None'})"
                        })
                        stats[category]["hits_at_5"] -= 1
                        if found_at == 1:
                            stats[category]["hits_at_1"] -= 1
                        stats[category]["reciprocal_rank_sum"] -= 1.0 / found_at
            else:
                failures_by_category[category].append({
                    "id": case["id"], "query": query, "expected": expected,
                    "returned": returned[:3], "scores": scores[:3],
                    "error": "Expected concept not found in top 5 results"
                })

    elapsed = time.time() - start
    db.conn.close()

    # Limpieza del temp DB (misma disciplina que evaluar_qa.py)
    if os.path.exists(temp_db):
        os.remove(temp_db)

    print("\n" + "=" * 80)
    print("      BIORAG QA EVALUATION REPORT — RRF (intra-pool, gate por gap)")
    print(f"      k = {k}   |   umbral_gap = {umbral_gap}   |   tiempo: {elapsed:.1f}s")
    print("=" * 80)
    print(f"{'Category':<22} | {'Total':<6} | {'Recall@5':<9} | {'Recall@1':<9} | {'MRR':<8} | {'Errors/FPs':<10}")
    print("-" * 80)

    total_queries = 0
    total_hits_at_5 = 0
    total_hits_at_1 = 0
    total_mrr_sum = 0
    total_negatives = 0
    total_false_positives = 0

    for cat in sorted(stats.keys()):
        stat = stats[cat]
        cnt = stat["total"]
        if cat == "negativo":
            total_negatives += cnt
            total_false_positives += stat["false_positives"]
            fp_rate = (stat["false_positives"] / cnt) * 100 if cnt > 0 else 0
            print(f"{cat:<22} | {cnt:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {stat['false_positives']:<10} ({fp_rate:.1f}% FP)")
        else:
            total_queries += cnt
            total_hits_at_5 += stat["hits_at_5"]
            total_hits_at_1 += stat["hits_at_1"]
            total_mrr_sum += stat["reciprocal_rank_sum"]
            recall_5 = (stat["hits_at_5"] / cnt) * 100 if cnt > 0 else 0
            recall_1 = (stat["hits_at_1"] / cnt) * 100 if cnt > 0 else 0
            mrr = stat["reciprocal_rank_sum"] / cnt if cnt > 0 else 0
            num_failures = cnt - stat["hits_at_5"] if cat != "dormido" else len(failures_by_category[cat])
            print(f"{cat:<22} | {cnt:<6} | {recall_5:>7.2f}% | {recall_1:>7.2f}% | {mrr:>6.3f} | {num_failures:<10}")

    print("-" * 80)
    global_recall_5 = (total_hits_at_5 / total_queries) * 100 if total_queries > 0 else 0
    global_recall_1 = (total_hits_at_1 / total_queries) * 100 if total_queries > 0 else 0
    global_mrr = total_mrr_sum / total_queries if total_queries > 0 else 0
    global_fp_rate = (total_false_positives / total_negatives) * 100 if total_negatives > 0 else 0
    print(f"{'GLOBAL SUMMARY (Retrieval)':<22} | {total_queries:<6} | {global_recall_5:>7.2f}% | {global_recall_1:>7.2f}% | {global_mrr:>6.3f} | {total_queries - total_hits_at_5:<10}")
    print(f"{'GLOBAL SUMMARY (Noise/FP)':<22} | {total_negatives:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {total_false_positives:<10} ({global_fp_rate:.2f}% FP)")
    print("=" * 80)


if __name__ == "__main__":
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    umbral_gap = float(sys.argv[2]) if len(sys.argv) > 2 else None
    intra_pool = sys.argv[3] != "global" if len(sys.argv) > 3 else True
    run(k=k, umbral_gap=umbral_gap, intra_pool=intra_pool)
