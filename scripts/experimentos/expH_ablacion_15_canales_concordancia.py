#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expH_ablacion_15_canales_concordancia.py
=============================================================================
Experimento Quirúrgico: ABLACIÓN DE LAS 15 COMBINACIONES DE CANALES Y CONCORDANCIA
Objetivos:
1. Evaluar exhaustivamente los 15 subconjuntos posibles de canales (A, B, C, D y sus fusiones)
   para determinar la contribución ortogonal exacta de cada señal:
   - Individuales (4): A, B, C, D
   - Pares (6): A+B, A+C, A+D, B+C, B+D, C+D
   - Tríos (4): A+B+C, A+B+D, A+C+D, B+C+D
   - Cuarteto (1): A+B+C+D
2. Medir el efecto de la CONCORDANCIA MULTICANAL (bonificación cuando 2, 3 o 4 canales coinciden en la misma isla)
3. Medir el BEAM DE ISLAS (Top-1, Top-2, Top-3, Top-5, Top-7) en recuperación global (Global R@1, R@5, MRR)
=============================================================================
"""

import os
import sys
import json
import sqlite3
import re
import itertools
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any

sys.path.insert(0, ".")
sys.path.insert(0, "core")
from scripts.experimentos.expG_llave_acceso_multicanal_islas import (
    cargar_datos_base,
    proyectar_canal_A_ppmi,
    proyectar_canal_B_ppmi_rafaga,
    proyectar_canal_C_dimensiones,
    proyectar_canal_D_hdc,
    evaluar_ranking_intra_isla
)
from core.ppmi_hybrid_search import _tokenizar

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
CASOS_BASELINE_PATH = "scripts/casos_qa_baseline_v1.jsonl"
OUTPUT_RESULTS_PATH = "docs/expH_ablacion_15_canales_results.json"

def min_max(s: np.ndarray) -> np.ndarray:
    mi, ma = np.min(s), np.max(s)
    return (s - mi) / (ma - mi + 1e-12)

def fusionar_canales(canales_dict: Dict[str, np.ndarray], subset: Tuple[str, ...], bonus_concordancia: float = 0.0) -> np.ndarray:
    """Fusiona los canales normalizados de un subconjunto con pesos equilibrados y bonus opcional de concordancia."""
    scores_norm = [min_max(canales_dict[ch]) for ch in subset]
    fused = np.mean(scores_norm, axis=0)
    
    if bonus_concordancia > 0 and len(subset) >= 2:
        # Detectar qué isla es Top-1 para cada canal
        top1_per_ch = [np.argmax(canales_dict[ch]) for ch in subset]
        counts = Counter(top1_per_ch)
        for island_idx, cnt in counts.items():
            if cnt >= 2:
                # Bonus proporcional a cuántos canales concordaron
                fused[island_idx] += bonus_concordancia * (cnt / len(subset))
                
    return fused

def run_experiment_15_combinations():
    print("[*] Cargando topología y matrices de BioRAG...")
    data = cargar_datos_base(DB_PATH, LABELS_PATH)
    print(f"[+] {len(data['conceptos'])} nodos y {data['n_com']} comunidades cargadas.")

    casos = [json.loads(l) for l in open(CASOS_BASELINE_PATH) if l.strip()]
    sin_cases = [c for c in casos if c.get("categoria") == "sinonimo"]
    
    # Precomputar proyecciones de los 4 canales para todos los casos
    precomputed_cases = []
    for c in sin_cases:
        esp = c["concepto_esperado"]
        q = c["query"]
        if esp not in data["com_por_concepto"]:
            continue
        com_target = data["com_por_concepto"][esp]
        
        sA = proyectar_canal_A_ppmi(q, data)
        sB = proyectar_canal_B_ppmi_rafaga(q, data)
        sC = proyectar_canal_C_dimensiones(q, data)
        sD = proyectar_canal_D_hdc(q, data)
        
        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)
        
        precomputed_cases.append({
            "id": c["id"],
            "query": q,
            "expected": esp,
            "target_com": com_target,
            "canales": {"A": sA, "B": sB, "C": sC, "D": sD},
            "vq": vq
        })
        
    total_eval = len(precomputed_cases)
    print(f"[+] {total_eval} casos sinonimo listos para evaluación.\n")

    # Generar los 15 subconjuntos
    channel_names = ["A", "B", "C", "D"]
    all_subsets = []
    for r in range(1, 5):
        for comb in itertools.combinations(channel_names, r):
            all_subsets.append(comb)

    # 1. EVALUAR LAS 15 COMBINACIONES PURAS (sin bonus)
    results_15 = []
    for subset in all_subsets:
        sub_name = "+".join(subset)
        hits_ir1, hits_ir5 = 0, 0
        hits_gr1, hits_gr5 = 0, 0
        mrr_sum = 0.0
        
        for item in precomputed_cases:
            target_com = item["target_com"]
            esp = item["expected"]
            vq = item["vq"]
            
            fused_scores = fusionar_canales(item["canales"], subset, bonus_concordancia=0.0)
            sorted_islands = [data["sorted_coms"][i] for i in np.argsort(-fused_scores)]
            
            top1_com = sorted_islands[0]
            top5_coms = sorted_islands[:5]
            
            if top1_com == target_com: hits_ir1 += 1
            if target_com in top5_coms: hits_ir5 += 1
            
            # Intra-island sobre Top-1
            intra_res = evaluar_ranking_intra_isla(esp, top1_com, vq, data)
            if intra_res["intra_r1"]: hits_gr1 += 1
            if intra_res["intra_r5"]: hits_gr5 += 1
            if intra_res["rank"]: mrr_sum += 1.0 / intra_res["rank"]
            
        results_15.append({
            "subset": sub_name,
            "num_channels": len(subset),
            "island_r1": hits_ir1,
            "island_r1_pct": hits_ir1 / total_eval * 100,
            "island_r5": hits_ir5,
            "island_r5_pct": hits_ir5 / total_eval * 100,
            "global_r1": hits_gr1,
            "global_r1_pct": hits_gr1 / total_eval * 100,
            "global_r5": hits_gr5,
            "global_r5_pct": hits_gr5 / total_eval * 100,
            "mrr": mrr_sum / total_eval
        })

    # Ordenar por Island R@1 descendente
    results_15.sort(key=lambda x: (x["island_r1"], x["island_r5"]), reverse=True)

    print("===================================================================================================")
    print("TABLA DE ABLACIÓN DE LAS 15 COMBINACIONES DE CANALES (Ordenadas por Precisión de Isla R@1)")
    print("===================================================================================================")
    print(f"{'Combinación':18s} | {'Isla R@1':14s} | {'Isla R@5':14s} | {'Global R@1':14s} | {'Global R@5':14s} | {'MRR':8s}")
    print("-" * 95)
    for r in results_15:
        print(f"{r['subset']:18s} | {r['island_r1']:2d}/{total_eval:2d} ({r['island_r1_pct']:5.1f}%) | {r['island_r5']:2d}/{total_eval:2d} ({r['island_r5_pct']:5.1f}%) | {r['global_r1']:2d}/{total_eval:2d} ({r['global_r1_pct']:5.1f}%) | {r['global_r5']:2d}/{total_eval:2d} ({r['global_r5_pct']:5.1f}%) | {r['mrr']:.4f}")

    # 2. EVALUAR IMPACTO DEL BONUS DE CONCORDANCIA SOBRE EL CUARTETO (A+B+C+D) Y MEJOR TRÍO
    print("\n===================================================================================================")
    print("EVALUACIÓN DEL BONUS DE CONCORDANCIA MULTICANAL (Resonancia por Convergencia)")
    print("===================================================================================================")
    print(f"{'Configuración':30s} | {'Isla R@1':14s} | {'Isla R@5':14s} | {'Global R@5':14s} | {'MRR':8s}")
    print("-" * 90)

    concordance_results = []
    for subset in [("A", "B", "C", "D"), ("A", "B", "D"), ("A", "B", "C")]:
        sub_name = "+".join(subset)
        for bonus in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]:
            hits_ir1, hits_ir5, hits_gr5 = 0, 0, 0
            mrr_sum = 0.0
            for item in precomputed_cases:
                target_com = item["target_com"]
                esp = item["expected"]
                vq = item["vq"]
                
                fused_scores = fusionar_canales(item["canales"], subset, bonus_concordancia=bonus)
                sorted_islands = [data["sorted_coms"][i] for i in np.argsort(-fused_scores)]
                
                top1_com = sorted_islands[0]
                top5_coms = sorted_islands[:5]
                
                if top1_com == target_com: hits_ir1 += 1
                if target_com in top5_coms: hits_ir5 += 1
                
                intra_res = evaluar_ranking_intra_isla(esp, top1_com, vq, data)
                if intra_res["intra_r5"]: hits_gr5 += 1
                if intra_res["rank"]: mrr_sum += 1.0 / intra_res["rank"]
                
            cfg_label = f"{sub_name} (bonus={bonus:.2f})"
            ir1_p = hits_ir1 / total_eval * 100
            ir5_p = hits_ir5 / total_eval * 100
            gr5_p = hits_gr5 / total_eval * 100
            mrr_v = mrr_sum / total_eval
            print(f"{cfg_label:30s} | {hits_ir1:2d}/{total_eval:2d} ({ir1_p:5.1f}%) | {hits_ir5:2d}/{total_eval:2d} ({ir5_p:5.1f}%) | {hits_gr5:2d}/{total_eval:2d} ({gr5_p:5.1f}%) | {mrr_v:.4f}")
            concordance_results.append({
                "config": cfg_label, "subset": sub_name, "bonus": bonus,
                "island_r1": hits_ir1, "island_r1_pct": ir1_p,
                "island_r5": hits_ir5, "island_r5_pct": ir5_p,
                "global_r5": hits_gr5, "global_r5_pct": gr5_p,
                "mrr": mrr_v
            })

    # 3. EVALUACIÓN DE BEAM DE ISLAS (Top-1, Top-2, Top-3, Top-5, Top-7) SOBRE EL MEJOR MODELO
    best_subset = ("A", "B", "C", "D")
    best_bonus = 0.15
    print("\n===================================================================================================")
    print(f"EVALUACIÓN DE BEAM DE ISLAS CANDIDATAS ({'+'.join(best_subset)} con bonus={best_bonus})")
    print("===================================================================================================")
    print(f"{'Beam Size':15s} | {'Candidatos Promedio':20s} | {'Global R@1':14s} | {'Global R@5':14s} | {'MRR':8s}")
    print("-" * 85)

    beam_results = []
    for k_beam in [1, 2, 3, 5, 7, 10]:
        hits_r1, hits_r5 = 0, 0
        mrr_sum = 0.0
        total_cand_count = 0
        
        for item in precomputed_cases:
            target_com = item["target_com"]
            esp = item["expected"]
            vq = item["vq"]
            
            fused_scores = fusionar_canales(item["canales"], best_subset, bonus_concordancia=best_bonus)
            sorted_islands = [data["sorted_coms"][i] for i in np.argsort(-fused_scores)]
            selected_islands = sorted_islands[:k_beam]
            
            candidate_nodes = []
            for isl in selected_islands:
                candidate_nodes.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
            candidate_nodes = list(set(candidate_nodes))
            total_cand_count += len(candidate_nodes)
            
            scores = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in candidate_nodes]
            scores.sort(key=lambda x: x[1], reverse=True)
            
            rank = next((idx for idx, (node, sc) in enumerate(scores, 1) if node == esp), None)
            if rank == 1: hits_r1 += 1
            if rank and rank <= 5: hits_r5 += 1
            if rank: mrr_sum += 1.0 / rank
            
        avg_cand = total_cand_count / total_eval
        gr1_p = hits_r1 / total_eval * 100
        gr5_p = hits_r5 / total_eval * 100
        mrr_v = mrr_sum / total_eval
        print(f"Top-{k_beam:<2d} Islas     | {avg_cand:5.1f} nodos/búsqueda   | {hits_r1:2d}/{total_eval:2d} ({gr1_p:5.1f}%) | {hits_r5:2d}/{total_eval:2d} ({gr5_p:5.1f}%) | {mrr_v:.4f}")
        beam_results.append({
            "beam_k": k_beam, "avg_candidates": avg_cand,
            "global_r1": hits_r1, "global_r1_pct": gr1_p,
            "global_r5": hits_r5, "global_r5_pct": gr5_p,
            "mrr": mrr_v
        })

    # Guardar todos los resultados en JSON
    full_output = {
        "benchmark": "expH_ablacion_15_canales_concordancia",
        "total_cases": total_eval,
        "results_15_combinations": results_15,
        "concordance_tuning": concordance_results,
        "beam_search_evaluation": beam_results
    }
    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Resultados completos guardados en: {OUTPUT_RESULTS_PATH}")

if __name__ == "__main__":
    run_experiment_15_combinations()
