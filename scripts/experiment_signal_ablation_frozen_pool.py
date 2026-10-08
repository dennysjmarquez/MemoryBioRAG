#!/usr/bin/env python3
"""
scripts/experiment_signal_ablation_frozen_pool.py
=============================================================================
Ablación Contrafactual Sistemática de Señales sobre Pool de Candidatos Congelado.
Evalúa el impacto causal de cada señal en los 72 fallos Top-1 y en el benchmark completo:
- A: Baseline (Motor Actual)
- B: tematico_score = 0
- C: dim_score = 0
- D: sinonimos_ratio = 0
- E: ppmi_score = 0
- F: tematico_score + dim_score = 0 (Eje Estructural/Temático OFF)
- G: sinonimos_ratio + ppmi_score = 0 (Eje Semántico Fino OFF)
- H: grupo_score_wordnet = 0 (WordNet OFF en scoring)
- I: pred_score_srl = 0 (SRL Predicados OFF)
=============================================================================
"""

import sys
import os
import json
import re
import time
import hashlib
import sqlite3
import subprocess
import difflib
from collections import defaultdict
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG
from core.memory import constants
from scripts.evaluar_qa import (
    _clave_etiqueta,
    _restaurar_estado_nodos
)


def run_ablation_experiment(ablation_mode="A"):
    """
    ablation_mode:
      'A': Baseline
      'B': tematico_score = 0.0
      'C': dim_score = 0.0
      'D': sinonimos_ratio = 0.0
      'E': ppmi_score = 0.0
      'F': tematico_score = 0.0 and dim_score = 0.0
      'G': sinonimos_ratio = 0.0 and ppmi_score = 0.0
      'H': grupo_score = 0.0
      'I': pred_score = 0.0
    """
    snapshot_path = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
    dataset_path = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
    temp_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", f"memory_biorag_ablation_{ablation_mode}.db")
    
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass
            
    src_uri = Path(snapshot_path).expanduser().resolve().as_uri() + "?mode=ro"
    conn_src = sqlite3.connect(src_uri, uri=True)
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_src.close()
    conn_dst.close()
    
    os.environ["BIORAG_NO_LOG"] = "1"
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    
    original_calcular_score_hibrido = db._calcular_score_hibrido
    
    def ablated_calcular_score_hibrido(*args, **kwargs):
        if ablation_mode == "B":
            kwargs["tematico_score"] = 0.0
        elif ablation_mode == "C":
            kwargs["dim_score"] = 0.0
        elif ablation_mode == "D":
            kwargs["sinonimos_ratio"] = 0.0
        elif ablation_mode == "E":
            kwargs["ppmi_score"] = 0.0
        elif ablation_mode == "F":
            kwargs["tematico_score"] = 0.0
            kwargs["dim_score"] = 0.0
        elif ablation_mode == "G":
            kwargs["sinonimos_ratio"] = 0.0
            kwargs["ppmi_score"] = 0.0
        elif ablation_mode == "H":
            kwargs["grupo_score"] = 0.0
        elif ablation_mode == "I":
            kwargs["pred_score"] = 0.0
            
        return original_calcular_score_hibrido(*args, **kwargs)
        
    db._calcular_score_hibrido = ablated_calcular_score_hibrido

    cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
                
    clave_a_conceptos = defaultdict(list)
    for (_conc,) in db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
        if _conc:
            clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)
            
    def _resolver_etiqueta(esperado):
        if not esperado:
            return esperado
        row = db.cursor.execute("SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)).fetchone()
        if row:
            return esperado
        clave = _clave_etiqueta(esperado)
        candidatos = clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0]
        cercanos = difflib.get_close_matches(clave, list(clave_a_conceptos.keys()), n=3, cutoff=0.80)
        if not cercanos:
            return esperado
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = difflib.SequenceMatcher(None, clave, cercanos[1]).ratio() if len(cercanos) > 1 else 0.0
        opciones = clave_a_conceptos[mejor_clave]
        if ratio >= 0.94 and (ratio - segundo) >= 0.02 and len(opciones) == 1:
            return opciones[0]
        return esperado

    golds_por_query = defaultdict(set)
    for _c in cases:
        if _c.get("concepto_esperado"):
            golds_por_query[_c["query"].strip().lower()].add(_c["concepto_esperado"])
    queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

    estado_inicial_nodos = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall()
    }
    
    retrieval_cases = 0
    negative_cases = 0
    ambiguous_cases = 0
    fp_count = 0
    top5_hits = 0
    top1_hits = 0
    mrr_sum = 0.0
    
    by_category_r1 = defaultdict(lambda: {"hits": 0, "total": 0})
    query_results_map = {}
    
    for case in cases:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)
        
        if expected:
            expected = _resolver_etiqueta(expected)
            
        if expected and query.strip().lower() in queries_ambiguas:
            ambiguous_cases += 1
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue
            
        if expected is None:
            negative_cases += 1
            results, _ = db.buscar_por_frase(query, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
            if results and results[0][4] >= 0.60:
                fp_count += 1
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue
            
        retrieval_cases += 1
        by_category_r1[category]["total"] += 1
        
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
            
        profundidad = "profundo" if (deep or category == "dormido") else "activos"
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        
        returned = [r[0] for r in results]
        scores = [r[4] for r in results]
        
        found_at = -1
        for idx, concept in enumerate(returned[:5]):
            if concept == expected:
                found_at = idx + 1
                break
                
        if found_at != -1:
            top5_hits += 1
            mrr_sum += 1.0 / found_at
            if found_at == 1:
                top1_hits += 1
                by_category_r1[category]["hits"] += 1
                
        winner_name = returned[0] if returned else None
        winner_score = scores[0] if scores else 0.0
        gold_score = scores[found_at - 1] if found_at != -1 else 0.0
        
        query_results_map[case_id] = {
            "found_at": found_at,
            "winner": winner_name,
            "gold": expected,
            "winner_score": winner_score,
            "gold_score": gold_score,
            "category": category
        }
        
        _restaurar_estado_nodos(db, estado_inicial_nodos)

    db.conn.close()
    if os.path.exists(temp_db):
        os.remove(temp_db)

    cat_summary = {}
    for cat, d in sorted(by_category_r1.items()):
        cat_summary[cat] = {
            "hits": d["hits"],
            "total": d["total"],
            "r1_pct": round(d["hits"] / max(1, d["total"]) * 100, 2)
        }

    return {
        "mode": ablation_mode,
        "retrieval_cases": retrieval_cases,
        "top5_hits": top5_hits,
        "top1_hits": top1_hits,
        "r5_pct": round(top5_hits / retrieval_cases * 100, 2),
        "r1_pct": round(top1_hits / retrieval_cases * 100, 2),
        "mrr": round(mrr_sum / retrieval_cases, 4),
        "fp_count": fp_count,
        "misses_count": retrieval_cases - top1_hits,
        "by_category": cat_summary,
        "query_results": query_results_map
    }


if __name__ == "__main__":
    modes = [
        ("A", "Baseline (Motor Actual)"),
        ("B", "tematico_score = 0"),
        ("C", "dim_score = 0"),
        ("D", "sinonimos_ratio = 0"),
        ("E", "ppmi_score = 0"),
        ("F", "tematico + dim = 0"),
        ("G", "sinonimos + ppmi = 0"),
        ("H", "wordnet_score = 0"),
        ("I", "srl_pred_score = 0")
    ]
    
    print("=" * 80)
    print("INICIANDO EXPERIMENTO DE ABLACIÓN CONTRAFACTUAL SOBRE POOL CONGELADO")
    print("=" * 80)
    
    t0 = time.time()
    results = {}
    for code, label in modes:
        print(f"-> Evaluando Config {code}: {label}...")
        res = run_ablation_experiment(code)
        results[code] = res
        print(f"   R@5: {res['r5_pct']}% | R@1: {res['r1_pct']}% | MRR: {res['mrr']} | Misses: {res['misses_count']} | FP: {res['fp_count']}/40")
        
    elapsed = time.time() - t0
    
    baseline_res = results["A"]
    misses_A = {cid: data for cid, data in baseline_res["query_results"].items() if data["found_at"] > 1}
    hits_A = {cid: data for cid, data in baseline_res["query_results"].items() if data["found_at"] == 1}
    
    comparison_table = []
    transitions_data = {}
    
    for code, label in modes:
        res = results[code]
        gains = []
        losses = []
        
        for cid, data_A in misses_A.items():
            data_m = res["query_results"][cid]
            if data_m["found_at"] == 1:
                gains.append({
                    "case_id": cid,
                    "category": data_A["category"],
                    "gold": data_A["gold"],
                    "winner_in_A": data_A["winner"],
                    "winner_in_ablation": data_m["winner"]
                })
                
        for cid, data_A in hits_A.items():
            data_m = res["query_results"][cid]
            if data_m["found_at"] != 1:
                losses.append({
                    "case_id": cid,
                    "category": data_A["category"],
                    "gold": data_A["gold"],
                    "winner_in_ablation": data_m["winner"]
                })
                
        net_delta = len(gains) - len(losses)
        transitions_data[code] = {
            "label": label,
            "gains_count": len(gains),
            "losses_count": len(losses),
            "net_delta_r1": net_delta,
            "gains": gains,
            "losses": losses
        }
        
        comparison_table.append({
            "code": code,
            "label": label,
            "r5_pct": res["r5_pct"],
            "r1_pct": res["r1_pct"],
            "mrr": res["mrr"],
            "misses": res["misses_count"],
            "fp": res["fp_count"],
            "gains": len(gains),
            "losses": len(losses),
            "net_delta": net_delta
        })

    json_report = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_seconds": round(elapsed, 2),
            "total_cases": 921,
            "retrieval_cases": 875,
            "negative_cases": 40
        },
        "comparison_table": comparison_table,
        "by_category_detail": {code: results[code]["by_category"] for code, _ in modes},
        "transitions_detail": transitions_data
    }
    
    out_json = os.path.join(BASE_DIR, "docs", "experimento_contrafactual_pool_congelado.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
        
    print("\n" + "=" * 90)
    print("           TABLA MAESTRA DE ABLACIÓN CONTRAFACTUAL SOBRE POOL CONGELADO")
    print("=" * 90)
    print(f"{'Config':<4} | {'Descripción':<30} | {'R@5':<7} | {'R@1':<7} | {'MRR':<7} | {'Misses':<6} | {'Ganancias':<9} | {'Pérdidas':<8} | {'Δ Neto':<6}")
    print("-" * 90)
    for row in comparison_table:
        print(f"{row['code']:<4} | {row['label']:<30} | {row['r5_pct']}% | {row['r1_pct']}% | {row['mrr']:<7} | {row['misses']:<6} | {row['gains']:<9} | {row['losses']:<8} | {row['net_delta']:>+6}")
    print("=" * 90)
