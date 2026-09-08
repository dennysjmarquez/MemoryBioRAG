#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expI_auditoria_AC_vs_AD_union.py
=============================================================================
Auditoría Quirúrgica Caso por Caso: Rama Precisión (A+C) vs Rama Cobertura (A+D)
Pregunta Central: ¿A+C (PPMI+13D) y A+D (PPMI+HDC) rescatan conjuntos complementarios?

Mide:
1. Tabla caso por caso (61 casos)
2. Unión e Intersección (Union R@1, Union R@5, Intersection R@1, Intersection R@5)
3. Concordancia (Casos donde A+C y A+D apuntan a la misma isla)
4. Beam Search comparativo: A+C solo vs A+D solo vs Unión Adaptativa (A+C ∪ A+D)
=============================================================================
"""

import os
import sys
import json
import sqlite3
import numpy as np
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
CASOS_BASELINE_PATH = "scripts/casos_qa_baseline_v1.jsonl"
OUTPUT_JSON_PATH = "docs/expI_auditoria_AC_vs_AD_results.json"

def min_max(s: np.ndarray) -> np.ndarray:
    mi, ma = np.min(s), np.max(s)
    return (s - mi) / (ma - mi + 1e-12)

def run_audit():
    print("[*] Cargando topología y matrices de BioRAG...")
    data = cargar_datos_base(DB_PATH, LABELS_PATH)
    print(f"[+] {len(data['conceptos'])} nodos y {data['n_com']} comunidades cargadas.")

    casos = [json.loads(l) for l in open(CASOS_BASELINE_PATH) if l.strip()]
    sin_cases = [c for c in casos if c.get("categoria") == "sinonimo"]

    case_details = []
    
    ac_top1_count = 0
    ad_top1_count = 0
    ac_top5_count = 0
    ad_top5_count = 0
    
    concordance_count = 0
    union_top1_count = 0
    inter_top1_count = 0
    union_top5_count = 0
    inter_top5_count = 0

    for c in sin_cases:
        cid = c["id"]
        q = c["query"]
        esp = c["concepto_esperado"]
        if esp not in data["com_por_concepto"]:
            continue
        com_target = data["com_por_concepto"][esp]

        sA = proyectar_canal_A_ppmi(q, data)
        sC = proyectar_canal_C_dimensiones(q, data)
        sD = proyectar_canal_D_hdc(q, data)

        # Rama Precisión: A + C
        s_AC = 0.5 * min_max(sA) + 0.5 * min_max(sC)
        islands_AC = [data["sorted_coms"][i] for i in np.argsort(-s_AC)]
        rank_com_AC = islands_AC.index(com_target) + 1 if com_target in islands_AC else 999
        top1_AC = islands_AC[0]
        top5_AC = islands_AC[:5]
        ac_hit_t1 = (top1_AC == com_target)
        ac_hit_t5 = (com_target in top5_AC)

        # Rama Cobertura: A + D
        s_AD = 0.5 * min_max(sA) + 0.5 * min_max(sD)
        islands_AD = [data["sorted_coms"][i] for i in np.argsort(-s_AD)]
        rank_com_AD = islands_AD.index(com_target) + 1 if com_target in islands_AD else 999
        top1_AD = islands_AD[0]
        top5_AD = islands_AD[:5]
        ad_hit_t1 = (top1_AD == com_target)
        ad_hit_t5 = (com_target in top5_AD)

        # Análisis comparativo
        same_top1 = (top1_AC == top1_AD)
        at_least_one_t1 = (ac_hit_t1 or ad_hit_t1)
        both_t1 = (ac_hit_t1 and ad_hit_t1)
        at_least_one_t5 = (ac_hit_t5 or ad_hit_t5)
        both_t5 = (ac_hit_t5 and ad_hit_t5)

        if ac_hit_t1: ac_top1_count += 1
        if ad_hit_t1: ad_top1_count += 1
        if ac_hit_t5: ac_top5_count += 1
        if ad_hit_t5: ad_top5_count += 1
        
        if same_top1: concordance_count += 1
        if at_least_one_t1: union_top1_count += 1
        if both_t1: inter_top1_count += 1
        if at_least_one_t5: union_top5_count += 1
        if both_t5: inter_top5_count += 1

        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)

        case_details.append({
            "id": cid,
            "query": q,
            "expected": esp,
            "gold_island": com_target,
            "top1_AC": top1_AC,
            "rank_AC": rank_com_AC,
            "top1_AD": top1_AD,
            "rank_AD": rank_com_AD,
            "ac_hit_t1": ac_hit_t1,
            "ad_hit_t1": ad_hit_t1,
            "ac_hit_t5": ac_hit_t5,
            "ad_hit_t5": ad_hit_t5,
            "same_top1": same_top1,
            "union_t1": at_least_one_t1,
            "inter_t1": both_t1,
            "union_t5": at_least_one_t5,
            "inter_t5": both_t5,
            "vq": vq,
            "islands_AC": islands_AC,
            "islands_AD": islands_AD
        })

    total_eval = len(case_details)
    
    print(f"\n===================================================================================================")
    print(f"RESUMEN DE AUDITORÍA COMPARATIVA: RAMA PRECISIÓN (A+C) vs RAMA COBERTURA (A+D) ({total_eval} Casos)")
    print(f"===================================================================================================")
    print(f"• A+C (PPMI + 13-D) Island R@1:       {ac_top1_count:2d}/{total_eval} ({ac_top1_count/total_eval*100:5.1f}%) | Island R@5: {ac_top5_count:2d}/{total_eval} ({ac_top5_count/total_eval*100:5.1f}%)")
    print(f"• A+D (PPMI + HDC)  Island R@1:       {ad_top1_count:2d}/{total_eval} ({ad_top1_count/total_eval*100:5.1f}%) | Island R@5: {ad_top5_count:2d}/{total_eval} ({ad_top5_count/total_eval*100:5.1f}%)")
    print(f"---------------------------------------------------------------------------------------------------")
    print(f"• Concordancia Top-1 (Misma isla):     {concordance_count:2d}/{total_eval} ({concordance_count/total_eval*100:5.1f}%)")
    print(f"• Intersección Top-1 (Ambos aciertan): {inter_top1_count:2d}/{total_eval} ({inter_top1_count/total_eval*100:5.1f}%)")
    print(f"• UNIÓN TOP-1 (Al menos uno acierta):  {union_top1_count:2d}/{total_eval} ({union_top1_count/total_eval*100:5.1f}%)  <-- ¡POTENCIAL MÁXIMO TOP-1!")
    print(f"• UNIÓN TOP-5 (Al menos uno acierta):  {union_top5_count:2d}/{total_eval} ({union_top5_count/total_eval*100:5.1f}%)  <-- ¡POTENCIAL MÁXIMO TOP-5!")
    print(f"• Intersección Top-5 (Ambos en Top-5): {inter_top5_count:2d}/{total_eval} ({inter_top5_count/total_eval*100:5.1f}%)")

    # Casos donde A+C acierta pero A+D falla
    solo_ac = [c for c in case_details if c["ac_hit_t1"] and not c["ad_hit_t1"]]
    # Casos donde A+D acierta pero A+C falla
    solo_ad = [c for c in case_details if c["ad_hit_t1"] and not c["ac_hit_t1"]]

    print(f"\n--- ANÁLISIS DE ORTOGONALIDAD / COMPLEMENTARIEDAD ---")
    print(f"• Casos rescatados EXCLUSIVAMENTE por A+C (13-D): {len(solo_ac)}")
    for c in solo_ac:
        print(f"  ID: {c['id']} | Query: '{c['query']}' -> Gold: {c['expected']} (Isla {c['gold_island']}) | A+C rank: {c['rank_AC']} vs A+D rank: {c['rank_AD']}")
        
    print(f"\n• Casos rescatados EXCLUSIVAMENTE por A+D (HDC):  {len(solo_ad)}")
    for c in solo_ad:
        print(f"  ID: {c['id']} | Query: '{c['query']}' -> Gold: {c['expected']} (Isla {c['gold_island']}) | A+D rank: {c['rank_AD']} vs A+C rank: {c['rank_AC']}")

    # 3. EVALUACIÓN DE BEAM ADAPTATIVO POR CONCORDANCIA
    print(f"\n===================================================================================================")
    print("EVALUACIÓN DE BEAM ADAPTATIVO BASADO EN CONCORDANCIA A+C vs A+D")
    print("Regla Adaptativa: Si A+C y A+D coinciden en Top-1 -> Beam 1 isla. Si discrepan -> Beam Unión Top-K.")
    print("===================================================================================================")
    print(f"{'Estrategia de Beam':35s} | {'Candidatos Promedio':20s} | {'Global R@1':14s} | {'Global R@5':14s} | {'MRR':8s}")
    print("-" * 95)

    for k_disagree in [1, 2, 3, 4, 5]:
        hits_r1, hits_r5 = 0, 0
        mrr_sum = 0.0
        total_cands = 0
        
        for c in case_details:
            esp = c["expected"]
            vq = c["vq"]
            
            if c["same_top1"]:
                # Alta confianza: solo la isla concordante
                selected_islands = [c["top1_AC"]]
            else:
                # Discrepancia: unión de las mejores k islas de A+C y A+D
                union_islands = []
                for i in range(k_disagree):
                    if i < len(c["islands_AC"]): union_islands.append(c["islands_AC"][i])
                    if i < len(c["islands_AD"]): union_islands.append(c["islands_AD"][i])
                selected_islands = list(dict.fromkeys(union_islands)) # Preservar orden único
                
            candidate_nodes = []
            for isl in selected_islands:
                candidate_nodes.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
            candidate_nodes = list(set(candidate_nodes))
            total_cands += len(candidate_nodes)
            
            scores = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in candidate_nodes]
            scores.sort(key=lambda x: x[1], reverse=True)
            
            rank = next((idx for idx, (node, sc) in enumerate(scores, 1) if node == esp), None)
            if rank == 1: hits_r1 += 1
            if rank and rank <= 5: hits_r5 += 1
            if rank: mrr_sum += 1.0 / rank
            
        avg_c = total_cands / total_eval
        gr1_p = hits_r1 / total_eval * 100
        gr5_p = hits_r5 / total_eval * 100
        mrr_v = mrr_sum / total_eval
        strat_name = f"Concordante Top1 + Discrepante Top-{k_disagree}"
        print(f"{strat_name:35s} | {avg_c:5.1f} nodos/búsqueda   | {hits_r1:2d}/{total_eval:2d} ({gr1_p:5.1f}%) | {hits_r5:2d}/{total_eval:2d} ({gr5_p:5.1f}%) | {mrr_v:.4f}")

    # Guardar resultados
    def convert(o):
        if isinstance(o, (np.int64, np.int32)): return int(o)
        if isinstance(o, (np.float32, np.float64)): return float(o)
        if isinstance(o, np.bool_): return bool(o)
        if isinstance(o, np.ndarray): return o.tolist()
        return str(o)

    output_data = {
        "benchmark": "expI_auditoria_AC_vs_AD",
        "total_cases": int(total_eval),
        "metrics": {
            "ac_top1": int(ac_top1_count),
            "ad_top1": int(ad_top1_count),
            "ac_top5": int(ac_top5_count),
            "ad_top5": int(ad_top5_count),
            "concordance_top1": int(concordance_count),
            "union_top1": int(union_top1_count),
            "union_top1_pct": float(union_top1_count / total_eval * 100),
            "union_top5": int(union_top5_count),
            "union_top5_pct": float(union_top5_count / total_eval * 100),
            "intersection_top1": int(inter_top1_count),
            "intersection_top5": int(inter_top5_count)
        },
        "solo_ac_cases": [{k: (int(v) if isinstance(v, (np.integer, int)) else v) for k, v in c.items() if k not in ["vq", "islands_AC", "islands_AD"]} for c in solo_ac],
        "solo_ad_cases": [{k: (int(v) if isinstance(v, (np.integer, int)) else v) for k, v in c.items() if k not in ["vq", "islands_AC", "islands_AD"]} for c in solo_ad],
        "case_details": [{k: (bool(v) if isinstance(v, (np.bool_, bool)) else int(v) if isinstance(v, (np.integer, int)) else v) for k, v in c.items() if k not in ["vq", "islands_AC", "islands_AD"]} for c in case_details]
    }
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False, default=convert)
    print(f"\n[+] Resultados guardados en: {OUTPUT_JSON_PATH}")

if __name__ == "__main__":
    run_audit()
