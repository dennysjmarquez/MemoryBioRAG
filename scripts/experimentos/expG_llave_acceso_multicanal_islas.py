#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expG_llave_acceso_multicanal_islas.py
=============================================================================
Experimento Quirúrgico: LLAVE DE ACCESO A LA ISLA SEMÁNTICA
Compara 5 canales para proyectar una query a su comunidad semántica (105 islas):
- Canal A: PPMI actual (1 vector)
- Canal B: PPMI ráfaga multi-vista (5 proyecciones de sub-frases/términos)
- Canal C: 13-D Dimensiones Semánticas (similitud contra centroides de dimensión de isla)
- Canal D: HDC (Hipervectores de 2048 bits / Bundling de comunidad)
- Canal E: Votación Multicanal Combinada

Mide:
1. Island Recall@1 e Island Recall@5 (¿Acertamos la comunidad?)
2. Intra-Island Recall@1 y Recall@5 (Dentro de la comunidad elegida)
3. Global Retrieval Recall@1, Recall@5 y MRR (Pipeline completo)
=============================================================================
"""

import os
import sys
import json
import sqlite3
import re
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any

sys.path.insert(0, ".")
sys.path.insert(0, "core")
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
CASOS_BASELINE_PATH = "scripts/casos_qa_baseline_v1.jsonl"
OOF_DATASET_PATH = "docs/fase5_out_of_family_dataset_frozen.json"
OUTPUT_RESULTS_PATH = "docs/expG_llave_acceso_multicanal_results.json"

def cargar_datos_base(db_path: str, labels_path: str):
    labels = json.load(open(labels_path))
    conceptos = labels["conceptos"]
    comunidades = labels["knn_lpa"]
    com_por_concepto = dict(zip(conceptos, comunidades))
    idx_por_concepto = {c: i for i, c in enumerate(conceptos)}
    n_com = len(set(comunidades))

    # Cargar vectores PPMI
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows_ppmi = con.execute("SELECT concepto, vector FROM nodos").fetchall()
    ppmi_conceptos = [r[0] for r in rows_ppmi]
    ppmi_matrix = np.array([np.frombuffer(r[1], dtype=np.float32).copy() for r in rows_ppmi])
    ppmi_normas = np.linalg.norm(ppmi_matrix, axis=1, keepdims=True)
    ppmi_normas[ppmi_normas == 0] = 1.0
    ppmi_matrix = ppmi_matrix / ppmi_normas
    ppmi_map = {c: ppmi_matrix[i] for i, c in enumerate(ppmi_conceptos)}

    # Centroides PPMI por comunidad
    com_ppmi_acum = defaultdict(lambda: np.zeros(ppmi_matrix.shape[1], dtype=np.float32))
    for c, com in com_por_concepto.items():
        if c in ppmi_map:
            com_ppmi_acum[com] += ppmi_map[c]
    
    com_ppmi_centroides = {}
    for com, vec in com_ppmi_acum.items():
        n = np.linalg.norm(vec)
        com_ppmi_centroides[com] = (vec / n) if n > 1e-10 else vec
    sorted_coms = sorted(list(set(comunidades)))
    centro_ppmi_mat = np.array([com_ppmi_centroides.get(c, np.zeros(ppmi_matrix.shape[1])) for c in sorted_coms])

    # Cargar Dimensiones Semánticas (104 dimensiones en 13 tipos)
    rows_dims = con.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones").fetchall()
    total_dims = 120  # ID máximo seguro
    dim_map = defaultdict(lambda: np.zeros(total_dims, dtype=np.float32))
    for conc, dim_id in rows_dims:
        if dim_id < total_dims:
            dim_map[conc][dim_id] = 1.0

    # Centroides 13-D por comunidad
    com_dim_acum = defaultdict(lambda: np.zeros(total_dims, dtype=np.float32))
    for c, com in com_por_concepto.items():
        if c in dim_map:
            com_dim_acum[com] += dim_map[c]
    com_dim_centroides = {}
    for com, vec in com_dim_acum.items():
        n = np.linalg.norm(vec)
        com_dim_centroides[com] = (vec / n) if n > 1e-10 else vec
    centro_dim_mat = np.array([com_dim_centroides.get(c, np.zeros(total_dims)) for c in sorted_coms])

    # Cargar HDC (2048 bits / 256 bytes)
    rows_sdm = con.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()
    sdm_map = {}
    for conc, blob in rows_sdm:
        if blob:
            arr = np.unpackbits(np.frombuffer(blob, dtype=np.uint8))
            sdm_map[conc] = arr.astype(np.float32)

    # Bundling HDC por comunidad (Votación mayoritaria)
    com_hdc_bundles = {}
    for com in sorted_coms:
        members = [c for c, cc in com_por_concepto.items() if cc == com and c in sdm_map]
        if members:
            stack = np.array([sdm_map[c] for c in members])
            mean_bits = stack.mean(axis=0)
            com_hdc_bundles[com] = (mean_bits - 0.5) * 2.0
            n = np.linalg.norm(com_hdc_bundles[com])
            if n > 1e-10:
                com_hdc_bundles[com] /= n
        else:
            com_hdc_bundles[com] = np.zeros(2048, dtype=np.float32)
    centro_hdc_mat = np.array([com_hdc_bundles[c] for c in sorted_coms])

    con.close()
    idx_biorag = IndicesBioRAG(db_path)

    return {
        "conceptos": conceptos,
        "comunidades": comunidades,
        "sorted_coms": sorted_coms,
        "com_por_concepto": com_por_concepto,
        "idx_por_concepto": idx_por_concepto,
        "ppmi_map": ppmi_map,
        "dim_map": dim_map,
        "sdm_map": sdm_map,
        "centro_ppmi_mat": centro_ppmi_mat,
        "centro_dim_mat": centro_dim_mat,
        "centro_hdc_mat": centro_hdc_mat,
        "idx_biorag": idx_biorag,
        "n_com": n_com
    }

def proyectar_canal_A_ppmi(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal A: Vector PPMI simple de la query."""
    tokens = _tokenizar(q)
    vq = data["idx_biorag"].vector_query(tokens)
    n = np.linalg.norm(vq)
    if n < 1e-10:
        return np.zeros(len(data["sorted_coms"]))
    vq = vq / n
    sims = data["centro_ppmi_mat"] @ vq
    return sims

def proyectar_canal_B_ppmi_rafaga(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal B: Ráfaga de 5 vistas PPMI generadas internamente."""
    tokens = _tokenizar(q)
    if not tokens:
        return np.zeros(len(data["sorted_coms"]))
    
    views = [tokens]
    if len(tokens) >= 2:
        views.append(tokens[:len(tokens)//2])
        views.append(tokens[len(tokens)//2:])
    for t in tokens[:3]:
        views.append([t])
    
    sims_acum = np.zeros(len(data["sorted_coms"]))
    valid_views = 0
    for v in views[:5]:
        vq = data["idx_biorag"].vector_query(v)
        n = np.linalg.norm(vq)
        if n > 1e-10:
            sims_acum += (data["centro_ppmi_mat"] @ (vq / n))
            valid_views += 1
            
    if valid_views > 0:
        sims_acum /= valid_views
    return sims_acum

def proyectar_canal_C_dimensiones(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal C: Perfil de 13 dimensiones semánticas proyectadas a centroides de dimensión."""
    tokens = _tokenizar(q)
    v_dim = np.zeros(120, dtype=np.float32)
    for t in tokens:
        for conc, dvec in data["dim_map"].items():
            if t in conc.lower():
                v_dim += dvec
    n = np.linalg.norm(v_dim)
    if n < 1e-10:
        return np.zeros(len(data["sorted_coms"]))
    v_dim /= n
    sims = data["centro_dim_mat"] @ v_dim
    return sims

def proyectar_canal_D_hdc(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal D: Hipervector HDC superpuesto de los tokens de la query."""
    tokens = _tokenizar(q)
    v_hdc = np.zeros(2048, dtype=np.float32)
    count = 0
    for t in tokens:
        for conc, hvec in data["sdm_map"].items():
            if t in conc.lower():
                v_hdc += (hvec - 0.5) * 2.0
                count += 1
                if count >= 10:
                    break
    n = np.linalg.norm(v_hdc)
    if n < 1e-10:
        return np.zeros(len(data["sorted_coms"]))
    v_hdc /= n
    sims = data["centro_hdc_mat"] @ v_hdc
    return sims

def proyectar_canal_E_multicanal(sims_A: np.ndarray, sims_B: np.ndarray, sims_C: np.ndarray, sims_D: np.ndarray) -> np.ndarray:
    """Canal E: Fusión ponderada de los 4 canales."""
    def min_max(s):
        mi, ma = np.min(s), np.max(s)
        return (s - mi) / (ma - mi + 1e-12)
    
    nA = min_max(sims_A)
    nB = min_max(sims_B)
    nC = min_max(sims_C)
    nD = min_max(sims_D)
    
    return 0.35 * nA + 0.35 * nB + 0.15 * nC + 0.15 * nD

def evaluar_ranking_intra_isla(target_gold: str, island_id: int, q_vec: np.ndarray, data: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa el ranking del target Gold dentro de la isla elegida."""
    members = [c for c, cc in data["com_por_concepto"].items() if cc == island_id and c in data["ppmi_map"]]
    if not members or target_gold not in members:
        return {"in_island": False, "rank": None, "intra_r1": False, "intra_r5": False, "island_size": len(members)}
    
    scores = []
    for m in members:
        vm = data["ppmi_map"][m]
        sc = float(np.dot(q_vec, vm))
        scores.append((m, sc))
    scores.sort(key=lambda x: x[1], reverse=True)
    
    gold_rank = next((idx for idx, (m, s) in enumerate(scores, 1) if m == target_gold), None)
    return {
        "in_island": True,
        "rank": gold_rank,
        "intra_r1": gold_rank == 1,
        "intra_r5": gold_rank is not None and gold_rank <= 5,
        "island_size": len(members)
    }

def run_experiment():
    print("[*] Cargando topología y matrices de BioRAG...")
    data = cargar_datos_base(DB_PATH, LABELS_PATH)
    print(f"[+] {len(data['conceptos'])} nodos y {data['n_com']} comunidades cargadas.")

    # 1. Batería de Regresión (61 Casos Sinonimia Originales)
    casos = [json.loads(l) for l in open(CASOS_BASELINE_PATH) if l.strip()]
    sin_cases = [c for c in casos if c.get("categoria") == "sinonimo"]
    print(f"\n[*] Evaluando Batería de Regresión (61 Casos Sinonimia)...")

    results_channels = {
        "Canal_A_PPMI": {"island_r1": 0, "island_r5": 0, "global_r1": 0, "global_r5": 0, "mrr": 0.0},
        "Canal_B_Rafaga": {"island_r1": 0, "island_r5": 0, "global_r1": 0, "global_r5": 0, "mrr": 0.0},
        "Canal_C_13D": {"island_r1": 0, "island_r5": 0, "global_r1": 0, "global_r5": 0, "mrr": 0.0},
        "Canal_D_HDC": {"island_r1": 0, "island_r5": 0, "global_r1": 0, "global_r5": 0, "mrr": 0.0},
        "Canal_E_Multicanal": {"island_r1": 0, "island_r5": 0, "global_r1": 0, "global_r5": 0, "mrr": 0.0}
    }

    eval_details = []

    for c in sin_cases:
        cid = c["id"]
        q = c["query"]
        esp = c["concepto_esperado"]
        if esp not in data["com_por_concepto"]:
            continue
        com_target = data["com_por_concepto"][esp]

        sA = proyectar_canal_A_ppmi(q, data)
        sB = proyectar_canal_B_ppmi_rafaga(q, data)
        sC = proyectar_canal_C_dimensiones(q, data)
        sD = proyectar_canal_D_hdc(q, data)
        sE = proyectar_canal_E_multicanal(sA, sB, sC, sD)

        channel_scores = {
            "Canal_A_PPMI": sA,
            "Canal_B_Rafaga": sB,
            "Canal_C_13D": sC,
            "Canal_D_HDC": sD,
            "Canal_E_Multicanal": sE
        }

        vq = data["idx_biorag"].vector_query(_tokenizar(q))
        n = np.linalg.norm(vq)
        vq = (vq / n) if n > 1e-10 else np.zeros(100)

        case_row = {"id": cid, "query": q, "expected": esp, "target_com": com_target, "channels": {}}

        for ch_name, scores in channel_scores.items():
            sorted_islands = [data["sorted_coms"][i] for i in np.argsort(-scores)]
            top1_com = sorted_islands[0]
            top5_coms = sorted_islands[:5]

            is_island_r1 = (top1_com == com_target)
            is_island_r5 = (com_target in top5_coms)

            if is_island_r1:
                results_channels[ch_name]["island_r1"] += 1
            if is_island_r5:
                results_channels[ch_name]["island_r5"] += 1

            intra_res = evaluar_ranking_intra_isla(esp, top1_com, vq, data)
            is_global_r1 = intra_res["intra_r1"]
            is_global_r5 = intra_res["intra_r5"]
            grank = intra_res["rank"]

            if is_global_r1:
                results_channels[ch_name]["global_r1"] += 1
            if is_global_r5:
                results_channels[ch_name]["global_r5"] += 1
            if grank:
                results_channels[ch_name]["mrr"] += 1.0 / grank

            case_row["channels"][ch_name] = {
                "top1_island": top1_com,
                "island_r1": is_island_r1,
                "island_r5": is_island_r5,
                "intra_rank": grank,
                "global_r1": is_global_r1,
                "global_r5": is_global_r5
            }

        eval_details.append(case_row)

    total_eval = len(eval_details)
    print(f"\n=========================================================================================")
    print(f"RESULTADOS DE LA LLAVE DE ACCESO A ISLAS (Batería de {total_eval} Casos de Sinonimia)")
    print(f"=========================================================================================")
    print(f"{'Método / Canal':25s} | {'Isla R@1':12s} | {'Isla R@5':12s} | {'Global R@1':12s} | {'Global R@5':12s} | {'MRR':8s}")
    print("-" * 90)

    summary_table = {}
    for ch_name, res in results_channels.items():
        ir1_pct = res["island_r1"] / total_eval * 100
        ir5_pct = res["island_r5"] / total_eval * 100
        gr1_pct = res["global_r1"] / total_eval * 100
        gr5_pct = res["global_r5"] / total_eval * 100
        mrr_val = res["mrr"] / total_eval

        print(f"{ch_name:25s} | {res['island_r1']:2d}/{total_eval:2d} ({ir1_pct:4.1f}%) | {res['island_r5']:2d}/{total_eval:2d} ({ir5_pct:4.1f}%) | {res['global_r1']:2d}/{total_eval:2d} ({gr1_pct:4.1f}%) | {res['global_r5']:2d}/{total_eval:2d} ({gr5_pct:4.1f}%) | {mrr_val:.4f}")
        
        summary_table[ch_name] = {
            "island_r1": res["island_r1"],
            "island_r1_pct": ir1_pct,
            "island_r5": res["island_r5"],
            "island_r5_pct": ir5_pct,
            "global_r1": res["global_r1"],
            "global_r1_pct": gr1_pct,
            "global_r5": res["global_r5"],
            "global_r5_pct": gr5_pct,
            "mrr": mrr_val
        }

    output_payload = {
        "benchmark": "expG_llave_acceso_multicanal_islas",
        "total_cases": total_eval,
        "summary": summary_table,
        "details": eval_details
    }
    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Resultados guardados en: {OUTPUT_RESULTS_PATH}")

if __name__ == "__main__":
    run_experiment()
