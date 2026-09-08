#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expK_union_ramas_sin_poda.py
=============================================================================
Experimento Quirúrgico: UNIÓN DE RAMAS SIN PODA (A+C ∪ A+D) Y AUDITORÍA DETALLADA
Objetivos:
1. Evaluar si la unión no-destructiva de las dos mejores ramas (A+C Top-4 y A+D Top-4)
   mejora la recuperación global frente a cada rama individual o si introduce dilución.
2. Comparar exhaustivamente:
   - Rama 1: A+C Top-4 (PPMI + 13-D)
   - Rama 2: A+D Top-4 (PPMI + HDC)
   - Unión Top-2: Top-2 A+C ∪ Top-2 A+D
   - Unión Top-3: Top-3 A+C ∪ Top-3 A+D
   - Unión Top-4: Top-4 A+C ∪ Top-4 A+D
   - Unión Intercalada (Ranked Merge ponderado por concordancia sin poda)
3. Generar la matriz completa caso por caso (AC_top1..4, AD_top1..4, rankings y pertinencia)
4. Clasificar casos: AC exclusivo, AD exclusivo, ambos rescatan, ambos pierden, ganancia neta de unión, dilución de unión.
5. Medir latencia detallada por fase (proyección AC, proyección AD, intra-isla, total).
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
    proyectar_canal_D_hdc
)
from core.ppmi_hybrid_search import _tokenizar

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
VAL_DATASET_PATH = "docs/expJ_validation_dataset_frozen.json"
OUTPUT_RESULTS_PATH = "docs/expK_union_ramas_results.json"
LAMBDA_THRESHOLD = 0.25

def min_max(s: np.ndarray) -> np.ndarray:
    mi, ma = np.min(s), np.max(s)
    return (s - mi) / (ma - mi + 1e-12)

def run_expK():
    print(f"===================================================================================================")
    print(f"EXP K: EVALUACIÓN DE UNIÓN DE RAMAS SIN PODA (A+C ∪ A+D) Y AUDITORÍA DE LATENCIA")
    print(f"===================================================================================================")

    with open(VAL_DATASET_PATH, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    pos_cases = val_data["positive_cases"]
    adv_cases = val_data["adversarial_cases"]
    dataset_sha = val_data.get("dataset_sha256")
    print(f"[*] Dataset SHA-256 (30 fuera de muestra + 10 negativos): {dataset_sha}")

    t0_load = time.perf_counter()
    data = cargar_datos_base(DB_PATH, LABELS_PATH)
    t_load = (time.perf_counter() - t0_load) * 1000
    print(f"[+] Datos cargados en {t_load:.2f} ms ({len(data['conceptos'])} nodos, {data['n_com']} islas).")

    # 1. EVALUAR Y MEDIR TIEMPOS CASO POR CASO
    case_rows = []
    latencies = {
        "t_proj_AC": [],
        "t_proj_AD": [],
        "t_intra_retrieval": [],
        "t_total_query": []
    }

    for c in pos_cases:
        cid = c["val_id"]
        orig_id = c["original_id"]
        cat = c["categoria"]
        q = c["query"]
        esp = c["concepto_esperado"]
        target_com = data["com_por_concepto"].get(esp)
        if target_com is None:
            continue

        t0_q = time.perf_counter()

        # Canal A, C, D
        sA = proyectar_canal_A_ppmi(q, data)
        
        t0_c = time.perf_counter()
        sC = proyectar_canal_C_dimensiones(q, data)
        s_AC = 0.5 * min_max(sA) + 0.5 * min_max(sC)
        t_ac = (time.perf_counter() - t0_c) * 1000

        t0_d = time.perf_counter()
        sD = proyectar_canal_D_hdc(q, data)
        s_AD = 0.5 * min_max(sA) + 0.5 * min_max(sD)
        t_ad = (time.perf_counter() - t0_d) * 1000

        islands_AC = [data["sorted_coms"][i] for i in np.argsort(-s_AC)]
        islands_AD = [data["sorted_coms"][i] for i in np.argsort(-s_AD)]

        ac_top4 = islands_AC[:4]
        ad_top4 = islands_AD[:4]

        # Unión Top-4
        union_top4 = list(dict.fromkeys(ac_top4 + ad_top4))

        # Unión Intercalada con score fusionado
        s_merged = 0.5 * s_AC + 0.5 * s_AD
        islands_interleaved = [data["sorted_coms"][i] for i in np.argsort(-s_merged)][:6]

        # Verificación de presencia de isla
        gold_in_ac4 = (target_com in ac_top4)
        gold_in_ad4 = (target_com in ad_top4)
        gold_in_union = (target_com in union_top4)

        # Intra-island retrieval
        t0_intra = time.perf_counter()
        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)

        def retrieve_in_islands(isl_list: List[int]) -> Tuple[Any, float, int]:
            cands = []
            for isl in isl_list:
                cands.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
            cands = list(set(cands))
            scs = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in cands]
            scs.sort(key=lambda x: x[1], reverse=True)
            rank = next((idx for idx, (node, sc) in enumerate(scs, 1) if node == esp), None)
            gscore = next((sc for node, sc in scs if node == esp), 0.0)
            return rank, gscore, len(cands)

        rank_ac, score_ac, pool_ac = retrieve_in_islands(ac_top4)
        rank_ad, score_ad, pool_ad = retrieve_in_islands(ad_top4)
        rank_union, score_union, pool_union = retrieve_in_islands(union_top4)
        rank_inter, score_inter, pool_inter = retrieve_in_islands(islands_interleaved)

        t_intra = (time.perf_counter() - t0_intra) * 1000
        t_total = (time.perf_counter() - t0_q) * 1000

        latencies["t_proj_AC"].append(t_ac)
        latencies["t_proj_AD"].append(t_ad)
        latencies["t_intra_retrieval"].append(t_intra)
        latencies["t_total_query"].append(t_total)

        hit_ac_r5 = (rank_ac is not None and rank_ac <= 5 and score_ac >= LAMBDA_THRESHOLD)
        hit_ad_r5 = (rank_ad is not None and rank_ad <= 5 and score_ad >= LAMBDA_THRESHOLD)
        hit_union_r5 = (rank_union is not None and rank_union <= 5 and score_union >= LAMBDA_THRESHOLD)
        hit_inter_r5 = (rank_inter is not None and rank_inter <= 5 and score_inter >= LAMBDA_THRESHOLD)

        case_rows.append({
            "val_id": cid,
            "orig_id": orig_id,
            "query": q,
            "expected": esp,
            "gold_island": target_com,
            "AC_top4": ac_top4,
            "AD_top4": ad_top4,
            "union_top4": union_top4,
            "gold_in_AC_top4": gold_in_ac4,
            "gold_in_AD_top4": gold_in_ad4,
            "gold_in_union": gold_in_union,
            "global_rank_AC": rank_ac,
            "global_score_AC": score_ac,
            "hit_AC_r5": hit_ac_r5,
            "global_rank_AD": rank_ad,
            "global_score_AD": score_ad,
            "hit_AD_r5": hit_ad_r5,
            "global_rank_union": rank_union,
            "global_score_union": score_union,
            "hit_union_r5": hit_union_r5,
            "global_rank_inter": rank_inter,
            "hit_inter_r5": hit_inter_r5,
            "pool_AC": pool_ac,
            "pool_AD": pool_ad,
            "pool_union": pool_union,
            "islands_AC_all": islands_AC,
            "islands_AD_all": islands_AD,
            "vq": vq
        })

    total_pos = len(case_rows)

    # 2. DEFINIR Y EVALUAR LAS 6 ESTRATEGIAS
    strategies = {
        "1. A+C Solo (Top-4)": lambda r: r["AC_top4"],
        "2. A+D Solo (Top-4)": lambda r: r["AD_top4"],
        "3. Unión Top-2 (Top-2 AC ∪ Top-2 AD)": lambda r: list(dict.fromkeys(r["islands_AC_all"][:2] + r["islands_AD_all"][:2])),
        "4. Unión Top-3 (Top-3 AC ∪ Top-3 AD)": lambda r: list(dict.fromkeys(r["islands_AC_all"][:3] + r["islands_AD_all"][:3])),
        "5. Unión Top-4 (Top-4 AC ∪ Top-4 AD)": lambda r: r["union_top4"],
        "6. Unión Intercalada (Ranked Top-6)": lambda r: [data["sorted_coms"][i] for i in np.argsort(-(0.5*min_max(proyectar_canal_A_ppmi(r["query"], data) + proyectar_canal_C_dimensiones(r["query"], data)) + 0.5*min_max(proyectar_canal_A_ppmi(r["query"], data) + proyectar_canal_D_hdc(r["query"], data))))][:6]
    }

    strategy_stats = {}
    print(f"\n====================================================================================================================")
    print(f"TABLA COMPARATIVA DE ESTRATEGIAS DE UNIÓN SIN PODA ({total_pos} Casos Fuera de Muestra)")
    print(f"====================================================================================================================")
    print(f"{'Estrategia Evaluada':40s} | {'Nodos Pool':11s} | {'Isla R@1':12s} | {'Isla R@5':12s} | {'Global R@1':12s} | {'Global R@5':12s} | {'MRR':7s}")
    print("-" * 120)

    for strat_name, island_selector in strategies.items():
        hits_ir1, hits_ir5 = 0, 0
        hits_gr1, hits_gr5 = 0, 0
        mrr_sum = 0.0
        total_pool = 0

        for r in case_rows:
            esp = r["expected"]
            target_com = r["gold_island"]
            vq = r["vq"]
            q = r["query"]

            islands = island_selector(r)
            is_ir1 = (len(islands) > 0 and islands[0] == target_com)
            is_ir5 = (target_com in islands[:5])
            if is_ir1: hits_ir1 += 1
            if is_ir5: hits_ir5 += 1

            cands = []
            for isl in islands:
                cands.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
            cands = list(set(cands))
            total_pool += len(cands)

            scs = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in cands]
            scs.sort(key=lambda x: x[1], reverse=True)

            rank = next((idx for idx, (node, sc) in enumerate(scs, 1) if node == esp), None)
            gscore = next((sc for node, sc in scs if node == esp), 0.0)

            is_gr1 = (rank == 1 and gscore >= LAMBDA_THRESHOLD)
            is_gr5 = (rank is not None and rank <= 5 and gscore >= LAMBDA_THRESHOLD)

            if is_gr1: hits_gr1 += 1
            if is_gr5: hits_gr5 += 1
            if rank and gscore >= LAMBDA_THRESHOLD: mrr_sum += 1.0 / rank

        avg_p = total_pool / total_pos
        ir1_p = hits_ir1 / total_pos * 100
        ir5_p = hits_ir5 / total_pos * 100
        gr1_p = hits_gr1 / total_pos * 100
        gr5_p = hits_gr5 / total_pos * 100
        mrr_v = mrr_sum / total_pos

        print(f"{strat_name:40s} | {avg_p:5.1f} nodos | {hits_ir1:2d}/{total_pos:2d} ({ir1_p:4.1f}%) | {hits_ir5:2d}/{total_pos:2d} ({ir5_p:4.1f}%) | {hits_gr1:2d}/{total_pos:2d} ({gr1_p:4.1f}%) | {hits_gr5:2d}/{total_pos:2d} ({gr5_p:4.1f}%) | {mrr_v:.4f}")
        strategy_stats[strat_name] = {
            "avg_pool": avg_p,
            "island_r1": hits_ir1, "island_r1_pct": ir1_p,
            "island_r5": hits_ir5, "island_r5_pct": ir5_p,
            "global_r1": hits_gr1, "global_r1_pct": gr1_p,
            "global_r5": hits_gr5, "global_r5_pct": gr5_p,
            "mrr": mrr_v
        }

    # 3. ANÁLISIS DE CONTINGENCIA DETALLADO
    print(f"\n====================================================================================================================")
    print(f"ANÁLISIS DE CONTINGENCIA Y COMPLEMENTARIEDAD ENTRE RAMAS (N=30)")
    print(f"====================================================================================================================")

    both_rescued = [r for r in case_rows if r["hit_AC_r5"] and r["hit_AD_r5"]]
    solo_ac_rescued = [r for r in case_rows if r["hit_AC_r5"] and not r["hit_AD_r5"]]
    solo_ad_rescued = [r for r in case_rows if r["hit_AD_r5"] and not r["hit_AC_r5"]]
    both_missed = [r for r in case_rows if not r["hit_AC_r5"] and not r["hit_AD_r5"]]

    # Casos donde la Unión rescata pero individuales perdían
    union_rescued_new = [r for r in case_rows if r["hit_union_r5"] and not (r["hit_AC_r5"] or r["hit_AD_r5"])]
    # Casos donde la Unión perjudica (dilución: el nodo estaba en Top-5 individual pero bajó a >5 en Unión)
    union_diluted = [r for r in case_rows if (r["hit_AC_r5"] or r["hit_AD_r5"]) and not r["hit_union_r5"]]

    print(f"• Casos recuperados por AMBAS ramas (AC y AD):             {len(both_rescued):2d}/30 ({len(both_rescued)/30*100:4.1f}%)")
    print(f"• Casos rescatados EXCLUSIVAMENTE por AC (13-D):          {len(solo_ac_rescued):2d}/30 ({len(solo_ac_rescued)/30*100:4.1f}%)")
    print(f"• Casos rescatados EXCLUSIVAMENTE por AD (HDC):           {len(solo_ad_rescued):2d}/30 ({len(solo_ad_rescued)/30*100:4.1f}%)")
    print(f"• Casos que AMBAS ramas pierden:                          {len(both_missed):2d}/30 ({len(both_missed)/30*100:4.1f}%)")
    print(f"• Casos donde la Unión rescata y las individuales perdían: {len(union_rescued_new):2d}/30 ({len(union_rescued_new)/30*100:4.1f}%)")
    print(f"• Casos donde la Unión perjudica por dilución de pool:    {len(union_diluted):2d}/30 ({len(union_diluted)/30*100:4.1f}%)")

    # 4. MATRIZ DETALLADA POR CASO
    print(f"\n====================================================================================================================")
    print(f"MATRIZ DETALLADA POR CASO (Muestra de 10 casos)")
    print(f"====================================================================================================================")
    print(f"{'ID':12s} | {'Gold Isl':8s} | {'AC Top-4':16s} | {'AD Top-4':16s} | {'In AC?':6s} | {'In AD?':6s} | {'Rank AC':8s} | {'Rank AD':8s} | {'Rank Unión':10s}")
    print("-" * 115)
    for r in case_rows[:12]:
        ac_str = str(r["AC_top4"])
        ad_str = str(r["AD_top4"])
        in_ac_s = "SÍ" if r["gold_in_AC_top4"] else "NO"
        in_ad_s = "SÍ" if r["gold_in_AD_top4"] else "NO"
        rac_s = str(r["global_rank_AC"]) if r["global_rank_AC"] else "None"
        rad_s = str(r["global_rank_AD"]) if r["global_rank_AD"] else "None"
        run_s = str(r["global_rank_union"]) if r["global_rank_union"] else "None"
        print(f"{r['val_id']:12s} | {r['gold_island']:<8d} | {ac_str:16s} | {ad_str:16s} | {in_ac_s:6s} | {in_ad_s:6s} | {rac_s:8s} | {rad_s:8s} | {run_s:10s}")

    # 5. MEDIDAS DE LATENCIA DETALLADAS
    print(f"\n====================================================================================================================")
    print(f"MEDICIÓN DE LATENCIAS Y TIEMPOS DE PROCESAMIENTO (Milisegundos por Consulta)")
    print(f"====================================================================================================================")
    avg_t_ac = np.mean(latencies["t_proj_AC"])
    avg_t_ad = np.mean(latencies["t_proj_AD"])
    avg_t_intra = np.mean(latencies["t_intra_retrieval"])
    avg_t_total = np.mean(latencies["t_total_query"])

    print(f"• Tiempo de proyección Rama A+C (PPMI + 13-D):   {avg_t_ac:6.2f} ms")
    print(f"• Tiempo de proyección Rama A+D (PPMI + HDC):    {avg_t_ad:6.2f} ms")
    print(f"• Tiempo de recuperación Intra-Isla (PPMI+vec):  {avg_t_intra:6.2f} ms")
    print(f"• TIEMPO TOTAL POR CONSULTA (Pipeline Completo): {avg_t_total:6.2f} ms")

    # 6. EVALUACIÓN DE CONTROLES NEGATIVOS EN UNIÓN TOP-4 (10 CASOS)
    adv_results = []
    for adv in adv_cases:
        q = adv["query"]
        cid = adv["adv_id"]

        sA = proyectar_canal_A_ppmi(q, data)
        sC = proyectar_canal_C_dimensiones(q, data)
        sD = proyectar_canal_D_hdc(q, data)

        s_AC = 0.5 * min_max(sA) + 0.5 * min_max(sC)
        s_AD = 0.5 * min_max(sA) + 0.5 * min_max(sD)

        isl_ac = [data["sorted_coms"][i] for i in np.argsort(-s_AC)][:4]
        isl_ad = [data["sorted_coms"][i] for i in np.argsort(-s_AD)][:4]
        union_isl = list(dict.fromkeys(isl_ac + isl_ad))

        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)

        cands = []
        for isl in union_isl:
            cands.extend([node for node, com in data["com_por_concepto"].items() if com == isl and node in data["ppmi_map"]])
        cands = list(set(cands))

        scs = [(node, float(np.dot(vq, data["ppmi_map"][node]))) for node in cands]
        scs.sort(key=lambda x: x[1], reverse=True)
        top_cand = scs[0] if scs else (None, 0.0)

        is_fp = (top_cand[1] >= LAMBDA_THRESHOLD)
        adv_results.append({"adv_id": cid, "top_candidate": top_cand[0], "top_score": top_cand[1], "is_fp": is_fp})

    fp_count = sum(1 for a in adv_results if a["is_fp"])
    print(f"\n[*] Falsos Positivos en Controles Negativos (Unión Top-4): {fp_count}/10 ({fp_count/10*100:.1f}%) | Abstención Válida: {10-fp_count}/10 ({(10-fp_count)/10*100:.1f}%)")

    # Guardar resultados
    def convert(o):
        if isinstance(o, (np.int64, np.int32)): return int(o)
        if isinstance(o, (np.float32, np.float64)): return float(o)
        if isinstance(o, np.bool_): return bool(o)
        if isinstance(o, np.ndarray): return o.tolist()
        return str(o)

    clean_case_rows = []
    for r in case_rows:
        row_dict = {k: v for k, v in r.items() if k not in ["vq", "islands_AC_all", "islands_AD_all"]}
        clean_case_rows.append(row_dict)

    full_output = {
        "benchmark": "expK_union_ramas_sin_poda",
        "dataset_sha256": dataset_sha,
        "total_positive_cases": total_pos,
        "total_adversarial_cases": len(adv_cases),
        "strategies": strategy_stats,
        "contingency": {
            "both_rescued_count": len(both_rescued),
            "solo_ac_count": len(solo_ac_rescued),
            "solo_ad_count": len(solo_ad_rescued),
            "both_missed_count": len(both_missed),
            "union_rescued_new_count": len(union_rescued_new),
            "union_diluted_count": len(union_diluted)
        },
        "latencies_ms": {
            "t_proj_AC": avg_t_ac,
            "t_proj_AD": avg_t_ad,
            "t_intra_retrieval": avg_t_intra,
            "t_total_query": avg_t_total
        },
        "adversarial_fps": fp_count,
        "case_matrix": clean_case_rows
    }

    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False, default=convert)
    print(f"\n[+] Resultados completos guardados en: {OUTPUT_RESULTS_PATH}")

if __name__ == "__main__":
    run_expK()
