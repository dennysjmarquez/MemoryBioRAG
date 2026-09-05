#!/usr/bin/env python3
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG
from core.concept_hub import expandir_query_con_hub
from core.fallback_simbolico import expandir_query_wordnet

DB_SNAPSHOT = "snapshots/qa_escape_qcr_20260811.db"
CASOS_FILE = "scripts/casos_qa_baseline_v1.jsonl"

with open(CASOS_FILE) as f:
    casos = {json.loads(line)["id"]: json.loads(line) for line in f if line.strip()}

target_ids = ["0513", "0744", "0848", "0763"]

configs = {
    "D": {"hub": "0", "wn": "0", "nombre": "Run D (Hub OFF / WN OFF)"},
    "C": {"hub": "1", "wn": "0", "nombre": "Run C (Hub ON / WN OFF)"},
    "B": {"hub": "0", "wn": "1", "nombre": "Run B (Hub OFF / WN ON)"},
    "A": {"hub": "1", "wn": "1", "nombre": "Run A (Hub ON / WN ON)"},
}

print("="*80)
print("AUDITORÍA DE TRAZABILIDAD EXACTA PARA LOS 4 CASOS AFECTADOS")
print("="*80)

for tid in target_ids:
    c = casos[tid]
    q = c["query"]
    gold = c.get("concepto_esperado") or c.get("expected")
    cat = c["categoria"]
    
    print(f"\n[{tid}] Categoria: {cat} | Query: '{q}' | Gold: {gold}")
    print("-" * 80)
    
    import sqlite3
    conn_tmp = sqlite3.connect(DB_SNAPSHOT)
    exp_hub = expandir_query_con_hub(q, conn_tmp)
    conn_tmp.close()
    print(f"  • Expansión Concept Hub: {exp_hub}")
    from core.fallback_simbolico import _tokenizar_normalizado
    q_tokens = set(_tokenizar_normalizado(q))
    exp_wn = expandir_query_wordnet(q_tokens)
    print(f"  • Expansión WordNet:     {list(exp_wn)}")
    
    for cfg_id, cfg in configs.items():
        os.environ["BIORAG_HUB_ENABLED"] = cfg["hub"]
        os.environ["BIORAG_WORDNET_ENABLED"] = cfg["wn"]
        os.environ["BIORAG_NO_LOG"] = "1"
        os.environ["BIORAG_ORDEN_MONOTONICO"] = "1"
        
        profundidad = "profundo" if (c.get("deep") or cat in ("dormido", "negativo")) else "activos"
        cerebro = SQLiteMemoryBioRAG(db_path=DB_SNAPSHOT)
        if cat == "dormido" and gold:
            cerebro.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (gold,))
        elif gold:
            cerebro.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (gold,))
        
        results, total = cerebro.buscar_por_frase(q, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        cerebro.conn.close()
        
        cands = [r[0] for r in results]
        scores = [round(r[4], 4) for r in results]
        gold_pos = -1
        for idx, cand in enumerate(cands):
            if cand == gold or (isinstance(gold, list) and cand in gold):
                gold_pos = idx + 1
                break
        
        top5_str = ", ".join([f"{c} ({s})" for c, s in zip(cands, scores)])
        pos_str = f"TOP-{gold_pos}" if gold_pos > 0 else "NO EN TOP-5 (FALLO)"
        print(f"  [{cfg_id}] {cfg['nombre']:<25} -> Gold: {pos_str:<18} | Top-5: [{top5_str}]")

print("\n" + "="*80)
print("TAXONOMÍA DE LOS 24 FALLOS RESIDUALES EN RUN A (BASELINE OFICIAL v30.2)")
print("="*80)

with open("docs/casos_fallidos_ablation_A.jsonl") as f:
    fallos_a = [json.loads(line) for line in f if line.strip()]

for fa in fallos_a:
    fid = fa["id"]
    q = fa["query"]
    gold = fa["expected"]
    cat = fa["categoria"]
    ret = fa.get("returned", [])
    scores = fa.get("scores", [])
    print(f"ID {fid} | {cat:<20} | Query: '{q}' -> Gold: {gold}")
    print(f"      Top devuelto: {list(zip(ret[:3], scores[:3]))}")
