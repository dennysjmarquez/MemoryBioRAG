#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expJ_validacion_ciega_adaptive_island_key.py
=============================================================================
Experimento Quirúrgico: VALIDACIÓN CIEGA FUERA DE MUESTRA (30 Casos + 10 Negativos)
Evalúa fuera de muestra la arquitectura adaptativa de llaves de isla:

Estrategias Comparadas:
1. A+C Solo (PPMI + 13-D)
2. A+D Solo (PPMI + HDC)
3. Adaptive A+C/A+D (Concordancia Top-1 -> 1 isla; Discrepancia -> Unión Top-4)
4. Simple Union Beam (Unión incondicional de Top-2 / Top-3 de ambas ramas)

Mide:
- Island Recall@1 e Island Recall@5
- Global Retrieval Recall@1, Recall@5 y MRR
- Nodos promedio evaluados (compresión del espacio de búsqueda)
- Tasa de Falsos Positivos en controles negativos (10 casos)
- Análisis de contingencia y casos perdidos por poda de concordancia
=============================================================================
"""

import os
import sys
import json
import sqlite3
import numpy as np
import time
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any

sys.path.insert(0, ".")
sys.path.insert(0, "core")
from scripts.experimentos.expG_llave_acceso_multicanal_islas import (
    cargar_datos_base,
    proyectar_canal_A_ppmi,
    proyectar_canal_C_dimensiones,
    proyectar_canal_D_hdc,
    evaluar_ranking_intra_isla
)
from core.ppmi_hybrid_search import _tokenizar

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
VAL_DATASET_PATH = "docs/expJ_validation_dataset_frozen.json"
OUTPUT_RESULTS_PATH = "docs/expJ_validation_blind_results.json"
LAMBDA_THRESHOLD = 0.25

def min_max(s: np.ndarray) -> np.ndarray:
    mi, ma = np.min(s), np.max(s)
    return (s - mi) / (ma - mi + 1e-12)

def run_blind_validation():
    print(f"================================================================================")
    print(f"EXP J: VALIDACIÓN CIEGA DE LA LLAVE DE ISLA ADAPTATIVA (30 Casos + 10 Negativos)")
    print(f"================================================================================")
    
    with open(VAL_DATASET_PATH, "r", encoding="utf-8") as f:
        val_data = json.load(f)
        
    pos_cases = val_data["positive_cases"]
    adv_cases = val_data["adversarial_cases"]
    dataset_sha = val_data.get("dataset_sha256")
    print(f"[*] Dataset SHA-256 congelado: {dataset_sha}")
    print(f"[*] Casos positivos ciegos: {len(pos_cases)} (15 por_tema + 15 pregunta_natural)")
    print(f"[*] Controles negativos: {len(adv_cases)}")

    data = cargar_datos_base(DB_PATH, LABELS_PATH)

    # 1. EVALUACIÓN DE CASOS POSITIVOS
    eval_records = []
    
    for c in pos_cases:
        cid = c["val_id"]
        orig_id = c["original_id"]
        cat = c["categoria"]
        q = c["query"]
        esp = c["concepto_esperado"]
        
        com_target = data["com_por_concepto"].get(esp)
        if com_target is None:
            continue
            
        sA = proyectar_canal_A_ppmi(q, data)
        sC = proyectar_canal_C_dimensiones(q, data)
        sD = proyectar_canal_D_hdc(q, data)
        
        # Rama A+C
        s_AC = 0.5 * min_max(sA) + 0.5 * min_max(sC)
        islands_AC = [data["sorted_coms"][i] for i in np.argsort(-s_AC)]
        rank_isla_AC = islands_AC.index(com_target) + 1 if com_target in islands_AC else 999
        top1_AC = islands_AC[0]
        top5_AC = islands_AC[:5]
        
        # Rama A+D
        s_AD = 0.5 * min_max(sA) + 0.5 * min_max(sD)
        islands_AD = [data["sorted_coms"][i] for i in np.argsort(-s_AD)]
        rank_isla_AD = islands_AD.index(com_target) + 1 if com_target in islands_AD else 999
        top1_AD = islands_AD[0]
        top5_AD = islands_AD[:5]
        
        same_top1 = (top1_AC == top1_AD)
        
        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)
        
        eval_records.append({
            "val_id": cid,
            "orig_id": orig_id,
            "categoria": cat,
            "query": q,
            "expected": esp,
            "target_island": com_target,
            "top1_AC": top1_AC,
            "rank_isla_AC": rank_isla_AC,
            "top1_AD": top1_AD,
            "rank_isla_AD": rank_isla_AD,
            "same_top1": same_top1,
            "islands_AC": islands_AC,
            "islands_AD": islands_AD,
            "vq": vq
        })
        
    total_pos = len(eval_records)
    
    # 2. DEFINIR LAS ESTRATEGIAS A COMPARAR
    strategies = {
        "1. A+C Solo (Top-1)": lambda r: [r["top1_AC"]],
        "2. A+C Solo (Top-4 Beam)": lambda r: r["islands_AC"][:4],
        "3. A+D Solo (Top-1)": lambda r: [r["top1_AD"]],
        "4. A+D Solo (Top-4 Beam)": lambda r: r["islands_AD"][:4],
        "5. Adaptive A+C/A+D (Top1 si coincide, Top-4 si discrepa)": lambda r: [r["top1_AC"]] if r["same_top1"] else list(dict.fromkeys(r["islands_AC"][:4] + r["islands_AD"][:4])),
        "6. Simple Union Beam (Top-2 A+C ∪ Top-2 A+D)": lambda r: list(dict.fromkeys(r["islands_AC"][:2] + r["islands_AD"][:2])),
        "7. Simple Union Beam (Top-3 A+C ∪ Top-3 A+D)": lambda r: list(dict.fromkeys(r["islands_AC"][:3] + r["islands_AD"][:3]))
    }
    
    strategy_results = {}
    
    print(f"\n====================================================================================================================")
    print(f"RESULTADOS DE LA EVALUACIÓN CIEGA FUERA DE MUESTRA ({total_pos} Casos Positivos)")
    print(f"====================================================================================================================")
    print(f"{'Estrategia Evaluada':58s} | {'Nodos Pool':11s} | {'Isla R@1':12s} | {'Isla R@5':12s} | {'Global R@1':12s} | {'Global R@5':12s} | {'MRR':7s}")
    print("-" * 135)
    
    for strat_name, island_selector in strategies.items():
        hits_ir1, hits_ir5 = 0, 0
        hits_gr1, hits_gr5 = 0, 0
        mrr_sum = 0.0
        total_cands = 0
        
        strat_case_ranks = []
        
        for r in eval_records:
            esp = r["expected"]
            target_com = r["target_island"]
            vq = r["vq"]
            
            selected_islands = island_selector(r)
            
            # Island hit metrics
            is_ir1 = (len(selected_islands) > 0 and selected_islands[0] == target_com)
            is_ir5 = (target_com in selected_islands)
            if is_ir1: hits_ir1 += 1
            if is_ir5: hits_ir5 += 1
            
            # Intra-island retrieval
            candidate_nodes = []
            for isl in selected_islands:
                candidate_nodes.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
            candidate_nodes = list(set(candidate_nodes))
            total_cands += len(candidate_nodes)
            
            scores = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in candidate_nodes]
            scores.sort(key=lambda x: x[1], reverse=True)
            
            rank = next((idx for idx, (node, sc) in enumerate(scores, 1) if node == esp), None)
            gold_score = next((sc for node, sc in scores if node == esp), 0.0)
            
            is_gr1 = (rank == 1 and gold_score >= LAMBDA_THRESHOLD)
            is_gr5 = (rank is not None and rank <= 5 and gold_score >= LAMBDA_THRESHOLD)
            
            if is_gr1: hits_gr1 += 1
            if is_gr5: hits_gr5 += 1
            if rank and gold_score >= LAMBDA_THRESHOLD: mrr_sum += 1.0 / rank
            
            strat_case_ranks.append({"val_id": r["val_id"], "rank": rank, "score": gold_score, "hit_r5": is_gr5})
            
        avg_pool = total_cands / total_pos
        ir1_p = hits_ir1 / total_pos * 100
        ir5_p = hits_ir5 / total_pos * 100
        gr1_p = hits_gr1 / total_pos * 100
        gr5_p = hits_gr5 / total_pos * 100
        mrr_val = mrr_sum / total_pos
        
        print(f"{strat_name:58s} | {avg_pool:5.1f} nodos | {hits_ir1:2d}/{total_pos:2d} ({ir1_p:4.1f}%) | {hits_ir5:2d}/{total_pos:2d} ({ir5_p:4.1f}%) | {hits_gr1:2d}/{total_pos:2d} ({gr1_p:4.1f}%) | {hits_gr5:2d}/{total_pos:2d} ({gr5_p:4.1f}%) | {mrr_val:.4f}")
        
        strategy_results[strat_name] = {
            "avg_candidate_pool": avg_pool,
            "island_r1": hits_ir1, "island_r1_pct": ir1_p,
            "island_r5": hits_ir5, "island_r5_pct": ir5_p,
            "global_r1": hits_gr1, "global_r1_pct": gr1_p,
            "global_r5": hits_gr5, "global_r5_pct": gr5_p,
            "mrr": mrr_val,
            "case_ranks": strat_case_ranks
        }

    # 3. EVALUACIÓN DE FALSOS POSITIVOS EN CONTROLES NEGATIVOS (10 CASOS)
    print(f"\n====================================================================================================================")
    print(f"EVALUACIÓN DE ROBUSTEZ Y FALSOS POSITIVOS (10 Controles Negativos)")
    print(f"====================================================================================================================")
    
    adv_eval = []
    for adv in adv_cases:
        q = adv["query"]
        cid = adv["adv_id"]
        
        sA = proyectar_canal_A_ppmi(q, data)
        sC = proyectar_canal_C_dimensiones(q, data)
        sD = proyectar_canal_D_hdc(q, data)
        
        s_AC = 0.5 * min_max(sA) + 0.5 * min_max(sC)
        s_AD = 0.5 * min_max(sA) + 0.5 * min_max(sD)
        
        isl_AC = [data["sorted_coms"][i] for i in np.argsort(-s_AC)][:4]
        isl_AD = [data["sorted_coms"][i] for i in np.argsort(-s_AD)][:4]
        
        # Adaptive selection
        same = (isl_AC[0] == isl_AD[0])
        selected_islands = [isl_AC[0]] if same else list(dict.fromkeys(isl_AC[:4] + isl_AD[:4]))
        
        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)
        
        candidate_nodes = []
        for isl in selected_islands:
            candidate_nodes.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
        candidate_nodes = list(set(candidate_nodes))
        
        scores = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in candidate_nodes]
        scores.sort(key=lambda x: x[1], reverse=True)
        top_cand = scores[0] if scores else (None, 0.0)
        
        is_fp = (top_cand[1] >= LAMBDA_THRESHOLD)
        adv_eval.append({
            "adv_id": cid, "query": q,
            "top_candidate": top_cand[0], "top_score": top_cand[1], "is_fp": is_fp
        })
        
    fp_count = sum(1 for a in adv_eval if a["is_fp"])
    print(f"[*] Falsos Positivos en Controles Negativos: {fp_count}/10 ({fp_count/10*100:.1f}%) | Abstención Válida: {10-fp_count}/10 ({(10-fp_count)/10*100:.1f}%)")

    # 4. AUDITORÍA DE CONTINGENCIA Y PODA DESTRUCTIVA DE CONCORDANCIA
    print(f"\n====================================================================================================================")
    print(f"AUDITORÍA DE CONTINGENCIA ENTRE RAMAS Y PODA DE CONCORDANCIA")
    print(f"====================================================================================================================")
    
    # Ranks under A+C solo (Top 4) vs A+D solo (Top 4) vs Adaptive
    ranks_ac4 = {c["val_id"]: c["hit_r5"] for c in strategy_results["2. A+C Solo (Top-4 Beam)"]["case_ranks"]}
    ranks_ad4 = {c["val_id"]: c["hit_r5"] for c in strategy_results["4. A+D Solo (Top-4 Beam)"]["case_ranks"]}
    ranks_adapt = {c["val_id"]: c["hit_r5"] for c in strategy_results["5. Adaptive A+C/A+D (Top1 si coincide, Top-4 si discrepa)"]["case_ranks"]}
    
    solo_ac_rescued = [r["val_id"] for r in eval_records if ranks_ac4[r["val_id"]] and not ranks_ad4[r["val_id"]]]
    solo_ad_rescued = [r["val_id"] for r in eval_records if ranks_ad4[r["val_id"]] and not ranks_ac4[r["val_id"]]]
    both_rescued = [r["val_id"] for r in eval_records if ranks_ac4[r["val_id"]] and ranks_ad4[r["val_id"]]]
    both_missed = [r["val_id"] for r in eval_records if not ranks_ac4[r["val_id"]] and not ranks_ad4[r["val_id"]]]
    
    # Casos donde la concordancia causó pérdida (alguna rama en beam 4 lo tenía, pero al concordar en Top-1 falso se perdió)
    concordance_lost = [r["val_id"] for r in eval_records if (ranks_ac4[r["val_id"]] or ranks_ad4[r["val_id"]]) and not ranks_adapt[r["val_id"]]]
    
    print(f"• Casos recuperados por AMBAS ramas (A+C y A+D):    {len(both_rescued)}/30 ({len(both_rescued)/30*100:.1f}%)")
    print(f"• Casos rescatados EXCLUSIVAMENTE por A+C (13-D):   {len(solo_ac_rescued)}/30 ({len(solo_ac_rescued)/30*100:.1f}%)")
    print(f"• Casos rescatados EXCLUSIVAMENTE por A+D (HDC):    {len(solo_ad_rescued)}/30 ({len(solo_ad_rescued)/30*100:.1f}%)")
    print(f"• Casos que AMBAS ramas pierden:                     {len(both_missed)}/30 ({len(both_missed)/30*100:.1f}%)")
    print(f"• Casos perdidos por PODA DE CONCORDANCIA (en Adaptive): {len(concordance_lost)}/30 ({len(concordance_lost)/30*100:.1f}%)")
    
    if concordance_lost:
        for cid in concordance_lost:
            c = next(x for x in eval_records if x["val_id"] == cid)
            print(f"  [!] CASO PERDIDO: {cid} | Query: '{c['query']}' -> Gold: {c['expected']} (Isla {c['target_island']}) | A+C Top1: {c['top1_AC']} vs A+D Top1: {c['top1_AD']}")

    # Guardar resultados
    def convert(o):
        if isinstance(o, (np.int64, np.int32)): return int(o)
        if isinstance(o, (np.float32, np.float64)): return float(o)
        if isinstance(o, np.bool_): return bool(o)
        if isinstance(o, np.ndarray): return o.tolist()
        return str(o)
        
    full_output = {
        "benchmark": "expJ_validacion_ciega_adaptive_island_key",
        "dataset_sha256": dataset_sha,
        "total_positive_cases": total_pos,
        "total_adversarial_cases": len(adv_cases),
        "strategies_summary": strategy_results,
        "adversarial_eval": adv_eval,
        "contingency_analysis": {
            "both_rescued": both_rescued,
            "solo_ac_rescued": solo_ac_rescued,
            "solo_ad_rescued": solo_ad_rescued,
            "both_missed": both_missed,
            "concordance_lost_cases": concordance_lost
        }
    }
    
    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False, default=convert)
    print(f"\n[+] Resultados completos guardados en: {OUTPUT_RESULTS_PATH}")

if __name__ == "__main__":
    run_blind_validation()
