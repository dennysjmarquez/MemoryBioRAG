"""
Diagnóstico Empírico de por_tema: deep=False vs deep=True
=========================================================
Evalúa los 65 casos de la categoría por_tema en dos modos:
1. profundidad='activos' (deep=False)
2. profundidad='profundo' (deep=True)
Compara Recall@5, Recall@1, MRR y lista la causa exacta de cada fallo.
"""

import sys
import os
import json
import shutil
import sqlite3

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from core.memory_store import SQLiteMemoryBioRAG

src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_diag_temp.db")
cases_file = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")

shutil.copyfile(src_db, temp_db)
db = SQLiteMemoryBioRAG(db_path=temp_db)

cases = []
with open(cases_file, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            d = json.loads(line)
            if d.get("categoria") == "por_tema":
                cases.append(d)

print(f"Total casos por_tema: {len(cases)}")

def evaluar_modo(profundidad_modo, force_active=True):
    hits_at_5 = 0
    hits_at_1 = 0
    mrr_sum = 0.0
    fallidos = []

    for case in cases:
        query = case["query"]
        expected = case["concepto_esperado"]

        if force_active and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()

        results, total = db.buscar_por_frase(query, profundidad=profundidad_modo, limite=5, ignore_peso_sinaptico=True)
        returned = [r[0] for r in results]

        if expected in returned:
            hits_at_5 += 1
            rank = returned.index(expected) + 1
            if rank == 1:
                hits_at_1 += 1
            mrr_sum += 1.0 / rank
        else:
            fallidos.append((case["id"], query, expected, returned[:3]))

    n = len(cases)
    return {
        "recall_5": round(hits_at_5 / n * 100, 2),
        "recall_1": round(hits_at_1 / n * 100, 2),
        "mrr": round(mrr_sum / n, 3),
        "hits_5": hits_at_5,
        "fallidos": fallidos
    }

res_activos = evaluar_modo("activos", force_active=False)
res_profundo = evaluar_modo("profundo", force_active=False)
res_profundo_active = evaluar_modo("profundo", force_active=True)

print("\n========================================================")
print("              RESULTADOS COMPARATIVOS por_tema          ")
print("========================================================")
print(f"Modo 1: deep=False (sin forzar activo)  -> Recall@5: {res_activos['recall_5']}% ({res_activos['hits_5']}/{len(cases)}), MRR: {res_activos['mrr']}")
print(f"Modo 2: deep=True  (sin forzar activo)  -> Recall@5: {res_profundo['recall_5']}% ({res_profundo['hits_5']}/{len(cases)}), MRR: {res_profundo['mrr']}")
print(f"Modo 3: deep=True  (forzando activo)    -> Recall@5: {res_profundo_active['recall_5']}% ({res_profundo_active['hits_5']}/{len(cases)}), MRR: {res_profundo_active['mrr']}")

db.close()
if os.path.exists(temp_db):
    os.remove(temp_db)
