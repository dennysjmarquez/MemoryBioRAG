"""
Evaluación QA Global Pura con deep=True (v1.0)
==============================================
Evalúa los 921 casos reales sobre la DB pura en reposo sin realizar
UPDATEs de estado sobre el concepto esperado.
Compara la ejecución de deep=True a nivel global contra deep=False.
"""

import sys
import os
import json
import shutil
import sqlite3
import time
from collections import defaultdict

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from core.memory_store import SQLiteMemoryBioRAG

def run_pure_deep_eval(force_deep_all=True):
    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_pure_deep_temp.db")
    cases_file = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")

    shutil.copyfile(src_db, temp_db)
    db = SQLiteMemoryBioRAG(db_path=temp_db)

    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    mode_name = "PURE deep=True (global 589 nodos)" if force_deep_all else "PURE deep=False (activos 333 nodos)"
    print(f"\n================================================================================")
    print(f"             INICIANDO EVALUACIÓN {mode_name}")
    print(f"================================================================================\n")

    stats = defaultdict(lambda: {"total": 0, "hits_at_5": 0, "hits_at_1": 0, "reciprocal_rank_sum": 0.0, "false_positives": 0})
    
    start_time = time.time()

    for case in cases:
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)

        stats[category]["total"] += 1

        # PURE EVALUATION: NO UPDATE SET estado='activo'!
        profundidad = "profundo" if force_deep_all else ("profundo" if (deep or category == "dormido" or category == "negativo") else "activos")
        
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        returned = [r[0] for r in results]
        scores = [r[4] for r in results]

        if expected is None:
            # Negativo case: score >= 0.25 is FP
            if returned and any(s >= 0.25 for s in scores):
                stats[category]["false_positives"] += 1
        else:
            if expected in returned:
                stats[category]["hits_at_5"] += 1
                rank = returned.index(expected) + 1
                if rank == 1:
                    stats[category]["hits_at_1"] += 1
                stats[category]["reciprocal_rank_sum"] += 1.0 / rank

    elapsed = time.time() - start_time

    print(f"Total time: {elapsed:.2f}s")
    print(f"{'Category':<22} | {'Total':<6} | {'Recall@5':<9} | {'Recall@1':<9} | {'MRR':<6} | {'Errors/FPs':<10}")
    print("-" * 75)

    tot_queries = 0
    tot_hits_5 = 0
    tot_hits_1 = 0
    tot_mrr = 0.0
    tot_errs = 0

    for cat in sorted(stats.keys()):
        st = stats[cat]
        cnt = st["total"]
        if cat == "negativo":
            fp = st["false_positives"]
            pct = (fp / cnt) * 100 if cnt > 0 else 0.0
            print(f"{cat:<22} | {cnt:<6} | N/A       | N/A       | N/A    | {fp} ({pct:.1f}% FP)")
        else:
            r5 = (st["hits_at_5"] / cnt) * 100 if cnt > 0 else 0.0
            r1 = (st["hits_at_1"] / cnt) * 100 if cnt > 0 else 0.0
            mrr = st["reciprocal_rank_sum"] / cnt if cnt > 0 else 0.0
            err = cnt - st["hits_at_5"]
            print(f"{cat:<22} | {cnt:<6} | {r5:>7.2f}% | {r1:>7.2f}% | {mrr:>6.3f} | {err:<10}")

            tot_queries += cnt
            tot_hits_5 += st["hits_at_5"]
            tot_hits_1 += st["hits_at_1"]
            tot_mrr += st["reciprocal_rank_sum"]
            tot_errs += err

    g_r5 = (tot_hits_5 / tot_queries) * 100 if tot_queries else 0.0
    g_r1 = (tot_hits_1 / tot_queries) * 100 if tot_queries else 0.0
    g_mrr = tot_mrr / tot_queries if tot_queries else 0.0
    neg_fp = stats["negativo"]["false_positives"]
    neg_cnt = stats["negativo"]["total"]
    neg_pct = (neg_fp / neg_cnt) * 100 if neg_cnt else 0.0

    print("-" * 75)
    print(f"{'GLOBAL SUMMARY (Retrieval)':<22} | {tot_queries:<6} | {g_r5:>7.2f}% | {g_r1:>7.2f}% | {g_mrr:>6.3f} | {tot_errs:<10}")
    print(f"{'GLOBAL SUMMARY (Noise/FP)':<22} | {neg_cnt:<6} | N/A       | N/A       | N/A    | {neg_fp} ({neg_pct:.2f}% FP)")
    print("=" * 75)

    db.close()
    if os.path.exists(temp_db):
        os.remove(temp_db)

if __name__ == "__main__":
    run_pure_deep_eval(force_deep_all=True)
