#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expL_test_final.py
=============================================================================
TEST FINAL CONFIRMATORIO — MEMORYBIORAG (EXP-L)
=============================================================================
Evaluación confirmatoria ciega y determinística de 5 modelos de acceso estructural (M0..M4)
sobre los 55 casos congelados (20 A0 + 20 B + 15 C).

Modelos Evaluados:
- M0 (PPMI Solo):               Top-6 islas por Canal A (PPMI) -> Intra-isla PPMI
- M1 (A + C, PPMI + 13-D):      Top-6 islas por 0.5*MM(A) + 0.5*MM(C) -> Intra-isla PPMI
- M2 (A + D, PPMI + HDC):       Top-6 islas por 0.5*MM(A) + 0.5*MM(D) -> Intra-isla PPMI
- M3 (A + C + D Ponderado):     Top-6 islas por 0.50*MM(A) + 0.25*MM(C) + 0.25*MM(D) -> Intra-isla PPMI
- M4 (Unión Truncada AC/AD):    Top-6 islas AC union Top-6 islas AD -> Rerank Top-6 por S_merge -> Intra-isla PPMI

Parámetros Congelados (Inmutables):
- K = 6 (Islas seleccionadas)
- λ = 0.25 (Umbral intra-isla / corte de abstención)
- Desempate: 'concepto ASC' explícito y determinístico en todas las operaciones
- Snapshot DB: snapshots/qa_escape_qcr_20260811.db
- Labels: scripts/experimentos/expA_labels.json (105 comunidades semánticas)
- Dataset: docs/final_test_dataset_proposed.json (55 casos: 20 A0, 20 B, 15 C)

Protocolo:
- Ejecución única, limpia y determinística.
- Métricas formales: MRR puro sin condicionar a λ, Coverage, MRR|covered, R@1, R@5, FP@1, FP@5.
- Intervalos de confianza Wilson 95% y tests pareados de McNemar.
=============================================================================
"""

import os
import sys
import json
import math
import sqlite3
import hashlib
import time
import unicodedata
import re
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

# Rutas congeladas
DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
DATASET_PATH = "docs/final_test_dataset_proposed.json"
OUTPUT_RESULTS_PATH = "docs/expL_test_final_results.json"
OUTPUT_MANIFEST_PATH = "docs/expL_test_final_manifest.json"

# Hiperparámetros congelados
K_ISLANDS = 6
LAMBDA_THRESHOLD = 0.25
TIEBREAKER = "concepto_asc"

# Import de tokenizador interno del sistema
sys.path.insert(0, ".")
sys.path.insert(0, "core")
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar


def calcular_sha256_archivo(ruta: str) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    if not os.path.exists(ruta):
        return "ARCHIVO_NO_EXISTE"
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def min_max(s: np.ndarray) -> np.ndarray:
    """Normalización Min-Max por canal y por query."""
    mi, ma = float(np.min(s)), float(np.max(s))
    if ma - mi < 1e-12:
        return np.zeros_like(s, dtype=np.float32)
    return ((s - mi) / (ma - mi + 1e-12)).astype(np.float32)


def wilson_score_interval(hits: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calcula el intervalo de confianza de Wilson score para una proporción binomial."""
    if total == 0:
        return (0.0, 0.0)
    z = 1.959963984540054  # 95% CI
    p = hits / total
    denom = 1.0 + (z**2) / total
    center = (p + (z**2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p * (1.0 - p) / total) + (z**2) / (4.0 * (total**2)))) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (low, high)


def mcnemar_exact_pvalue(b: int, c: int) -> float:
    """Calcula el p-value exacto de dos colas para el test de McNemar mediante distribución binomial."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    cum_p = 0.0
    for i in range(k + 1):
        cum_p += math.comb(n, i) * (0.5**n)
    p_val = min(1.0, 2.0 * cum_p)
    return p_val


def cargar_infraestructura(db_path: str, labels_path: str) -> Dict[str, Any]:
    """Carga todas las estructuras del grafo, centroides y vectores."""
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)

    conceptos = labels["conceptos"]
    comunidades = labels["knn_lpa"]
    com_por_concepto = dict(zip(conceptos, comunidades))
    sorted_coms = sorted(list(set(comunidades)))
    n_com = len(sorted_coms)

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    # 1. PPMI
    rows_ppmi = con.execute("SELECT concepto, vector FROM nodos ORDER BY concepto ASC").fetchall()
    ppmi_conceptos = [r[0] for r in rows_ppmi]
    ppmi_matrix = np.array([np.frombuffer(r[1], dtype=np.float32).copy() for r in rows_ppmi])
    ppmi_normas = np.linalg.norm(ppmi_matrix, axis=1, keepdims=True)
    ppmi_normas[ppmi_normas == 0] = 1.0
    ppmi_matrix = ppmi_matrix / ppmi_normas
    ppmi_map = {c: ppmi_matrix[i] for i, c in enumerate(ppmi_conceptos)}

    # Centroides PPMI
    com_ppmi_acum = defaultdict(lambda: np.zeros(ppmi_matrix.shape[1], dtype=np.float32))
    for c, com in com_por_concepto.items():
        if c in ppmi_map:
            com_ppmi_acum[com] += ppmi_map[c]

    com_ppmi_centroides = {}
    for com, vec in com_ppmi_acum.items():
        n = np.linalg.norm(vec)
        com_ppmi_centroides[com] = (vec / n) if n > 1e-10 else vec
    centro_ppmi_mat = np.array([com_ppmi_centroides.get(c, np.zeros(ppmi_matrix.shape[1], dtype=np.float32)) for c in sorted_coms])

    # 2. 13-D Dimensiones Semánticas
    rows_dims = con.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones ORDER BY concepto ASC, dimension_id ASC").fetchall()
    total_dims = 120
    dim_map = defaultdict(lambda: np.zeros(total_dims, dtype=np.float32))
    for conc, dim_id in rows_dims:
        if dim_id < total_dims:
            dim_map[conc][dim_id] = 1.0

    # Centroides 13-D
    com_dim_acum = defaultdict(lambda: np.zeros(total_dims, dtype=np.float32))
    for c, com in com_por_concepto.items():
        if c in dim_map:
            com_dim_acum[com] += dim_map[c]
    com_dim_centroides = {}
    for com, vec in com_dim_acum.items():
        n = np.linalg.norm(vec)
        com_dim_centroides[com] = (vec / n) if n > 1e-10 else vec
    centro_dim_mat = np.array([com_dim_centroides.get(c, np.zeros(total_dims, dtype=np.float32)) for c in sorted_coms])

    # 3. HDC (2048 bits)
    rows_sdm = con.execute("SELECT concepto, vector FROM nodos_sdm ORDER BY concepto ASC").fetchall()
    sdm_map = {}
    for conc, blob in rows_sdm:
        if blob:
            arr = np.unpackbits(np.frombuffer(blob, dtype=np.uint8))
            sdm_map[conc] = arr.astype(np.float32)

    # Bundles HDC
    com_hdc_bundles = {}
    for com in sorted_coms:
        members = [c for c, cc in com_por_concepto.items() if cc == com and c in sdm_map]
        if members:
            stack = np.array([sdm_map[c] for c in sorted(members)])
            mean_bits = stack.mean(axis=0)
            bundle = (mean_bits - 0.5) * 2.0
            n = np.linalg.norm(bundle)
            if n > 1e-10:
                bundle /= n
            com_hdc_bundles[com] = bundle.astype(np.float32)
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
        "ppmi_map": ppmi_map,
        "dim_map": dim_map,
        "sdm_map": sdm_map,
        "centro_ppmi_mat": centro_ppmi_mat,
        "centro_dim_mat": centro_dim_mat,
        "centro_hdc_mat": centro_hdc_mat,
        "idx_biorag": idx_biorag,
        "n_com": n_com
    }


def proyectar_canal_A(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal A: Similitud PPMI simple de la query contra centroides de isla."""
    tokens = _tokenizar(q)
    vq = data["idx_biorag"].vector_query(tokens)
    n = np.linalg.norm(vq)
    if n < 1e-10:
        return np.zeros(len(data["sorted_coms"]), dtype=np.float32)
    vq = vq / n
    return (data["centro_ppmi_mat"] @ vq).astype(np.float32)


def proyectar_canal_C(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal C: Perfil 13-D de la query proyectado contra centroides de isla."""
    tokens = _tokenizar(q)
    v_dim = np.zeros(120, dtype=np.float32)
    for t in tokens:
        for conc in sorted(data["dim_map"].keys()):
            if t in conc.lower():
                v_dim += data["dim_map"][conc]
    n = np.linalg.norm(v_dim)
    if n < 1e-10:
        return np.zeros(len(data["sorted_coms"]), dtype=np.float32)
    v_dim /= n
    return (data["centro_dim_mat"] @ v_dim).astype(np.float32)


def proyectar_canal_D(q: str, data: Dict[str, Any]) -> np.ndarray:
    """Canal D: Hipervector HDC de la query proyectado contra centroides de isla."""
    tokens = _tokenizar(q)
    v_hdc = np.zeros(2048, dtype=np.float32)
    count = 0
    for t in tokens:
        for conc in sorted(data["sdm_map"].keys()):
            if t in conc.lower():
                v_hdc += (data["sdm_map"][conc] - 0.5) * 2.0
                count += 1
                if count >= 10:
                    break
        if count >= 10:
            break
    n = np.linalg.norm(v_hdc)
    if n < 1e-10:
        return np.zeros(len(data["sorted_coms"]), dtype=np.float32)
    v_hdc /= n
    return (data["centro_hdc_mat"] @ v_hdc).astype(np.float32)


def buscar_intra_islas(q: str, islands: List[int], data: Dict[str, Any]) -> List[Tuple[str, float]]:
    """Búsqueda determinística intra-isla por similitud coseno PPMI con desempate 'concepto ASC'."""
    tokens = _tokenizar(q)
    vq = data["idx_biorag"].vector_query(tokens)
    n = np.linalg.norm(vq)
    vq = (vq / n) if n > 1e-10 else np.zeros(100, dtype=np.float32)

    cands_set = set()
    for isl in islands:
        for conc, com in data["com_por_concepto"].items():
            if com == isl and conc in data["ppmi_map"]:
                cands_set.add(conc)

    cands_list = sorted(list(cands_set))
    if not cands_list:
        return []

    scored_cands = []
    for conc in cands_list:
        score = float(np.dot(vq, data["ppmi_map"][conc]))
        scored_cands.append((conc, score))

    # Orden descendente por score, desempate lexicográfico por concepto ASC
    scored_cands.sort(key=lambda x: (-x[1], x[0]))
    return scored_cands


def seleccionar_topk_islas(scores: np.ndarray, sorted_coms: List[int], k: int) -> List[int]:
    """Selecciona las Top-K islas ordenando por score DESC y com_id ASC en caso de empate."""
    indexed = list(zip(sorted_coms, scores))
    indexed.sort(key=lambda x: (-x[1], x[0]))
    return [com for com, sc in indexed[:k]]


def ejecutar_evaluacion():
    print("===================================================================================================")
    print("INICIANDO EXP-L: EVALUACIÓN CONFIRMATORIA FINAL DE ACCESO ESTRUCTURAL (M0..M4)")
    print("===================================================================================================")

    # 1. Hashes y verificación criptográfica
    sha_db = calcular_sha256_archivo(DB_PATH)
    sha_labels = calcular_sha256_archivo(LABELS_PATH)
    sha_dataset = calcular_sha256_archivo(DATASET_PATH)
    sha_script = calcular_sha256_archivo(__file__)

    print(f"• Git HEAD Commit:       999d3efb84d6ac9c24756b888f6e0f1b83739e3f")
    print(f"• DB Snapshot SHA-256:   {sha_db}")
    print(f"• Labels SHA-256:        {sha_labels}")
    print(f"• Test Dataset SHA-256:  {sha_dataset}")
    print(f"• Evaluator SHA-256:     {sha_script}")

    # 2. Cargar Dataset de 55 Casos Congelados
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        ds_raw = json.load(f)

    a0_cases = ds_raw["cases_by_stratum"]["A0_zero_overlap_estricto"]
    b_cases = ds_raw["cases_by_stratum"]["B_asociacion_tematica"]
    c_cases = ds_raw["cases_by_stratum"]["C_negativo"]

    eval_cases = []
    for cs in a0_cases:
        eval_cases.append({"case_id": cs["candidate_id"], "query": cs["query"], "gold": cs["gold"], "stratum": "A0"})
    for cs in b_cases:
        eval_cases.append({"case_id": cs["candidate_id"], "query": cs["query"], "gold": cs["gold"], "stratum": "B"})
    for cs in c_cases:
        eval_cases.append({"case_id": cs["candidate_id"], "query": cs["query"], "gold": cs["gold"], "stratum": "C"})

    print(f"\n[+] Total casos congelados en evaluación: {len(eval_cases)} (A0={len(a0_cases)}, B={len(b_cases)}, C={len(c_cases)})")

    # 3. Cargar Infraestructura
    t0_load = time.perf_counter()
    data = cargar_infraestructura(DB_PATH, LABELS_PATH)
    t_load = (time.perf_counter() - t0_load) * 1000
    print(f"[+] Infraestructura cargada en {t_load:.2f} ms ({len(data['conceptos'])} nodos, {data['n_com']} islas).")

    # 4. Declarar Modelos M0..M4
    modelos = ["M0_PPMI_solo", "M1_AC_PPMI_13D", "M2_AD_PPMI_HDC", "M3_ACD_ponderado", "M4_union_truncada_Top6"]

    resultados_por_modelo = {m: [] for m in modelos}
    metricas_resumen = {}

    # 5. Ejecución Caso por Caso sobre los 55 casos congelados
    print("\n[+] Ejecutando inferencia determinística caso por caso...")

    for idx, cs in enumerate(eval_cases):
        cid = cs["case_id"]
        q = cs["query"]
        gold = cs["gold"]
        strat = cs["stratum"]

        # Proyecciones base por query
        t0_proj = time.perf_counter()
        sA = proyectar_canal_A(q, data)
        sC = proyectar_canal_C(q, data)
        sD = proyectar_canal_D(q, data)
        t_proj_all = (time.perf_counter() - t0_proj) * 1000

        mm_sA = min_max(sA)
        mm_sC = min_max(sC)
        mm_sD = min_max(sD)

        # Canal AC y Canal AD
        s_AC = 0.5 * mm_sA + 0.5 * mm_sC
        s_AD = 0.5 * mm_sA + 0.5 * mm_sD

        # Top-6 AC y Top-6 AD para M4
        top6_islands_AC = seleccionar_topk_islas(s_AC, data["sorted_coms"], K_ISLANDS)
        top6_islands_AD = seleccionar_topk_islas(s_AD, data["sorted_coms"], K_ISLANDS)

        # M0: PPMI Solo
        s_M0 = mm_sA
        islands_M0 = seleccionar_topk_islas(s_M0, data["sorted_coms"], K_ISLANDS)

        # M1: A + C
        s_M1 = s_AC
        islands_M1 = top6_islands_AC

        # M2: A + D
        s_M2 = s_AD
        islands_M2 = top6_islands_AD

        # M3: A + C + D ponderado
        s_M3 = 0.50 * mm_sA + 0.25 * mm_sC + 0.25 * mm_sD
        islands_M3 = seleccionar_topk_islas(s_M3, data["sorted_coms"], K_ISLANDS)

        # M4: Unión Truncada Top-6 AC/AD con Reranking S_merge
        union_islands_pool = sorted(list(set(top6_islands_AC + top6_islands_AD)))
        s_merged = 0.5 * s_AC + 0.5 * s_AD
        indexed_union = [(isl, s_merged[data["sorted_coms"].index(isl)]) for isl in union_islands_pool]
        indexed_union.sort(key=lambda x: (-x[1], x[0]))
        islands_M4 = [isl for isl, sc in indexed_union[:K_ISLANDS]]

        # Diccionario de islas seleccionadas por modelo
        model_islands = {
            "M0_PPMI_solo": islands_M0,
            "M1_AC_PPMI_13D": islands_M1,
            "M2_AD_PPMI_HDC": islands_M2,
            "M3_ACD_ponderado": islands_M3,
            "M4_union_truncada_Top6": islands_M4
        }

        # Ejecutar intra-isla y registrar resultados
        for m in modelos:
            t0_intra = time.perf_counter()
            ranked_cands = buscar_intra_islas(q, model_islands[m], data)
            t_intra = (time.perf_counter() - t0_intra) * 1000
            t_total_q = t_proj_all + t_intra

            pool_size = len(ranked_cands)
            top1_score = ranked_cands[0][1] if ranked_cands else 0.0

            # Evaluación según estrato
            if strat in ["A0", "B"]:
                gold_rank = None
                gold_score = 0.0
                for r_idx, (conc, sc) in enumerate(ranked_cands, 1):
                    if conc == gold:
                        gold_rank = r_idx
                        gold_score = sc
                        break

                pure_rr = (1.0 / gold_rank) if gold_rank is not None else 0.0
                covered = (pool_size > 0 and top1_score >= LAMBDA_THRESHOLD)
                hit_r1 = (gold_rank == 1 and gold_score >= LAMBDA_THRESHOLD)
                hit_r5 = (gold_rank is not None and gold_rank <= 5 and gold_score >= LAMBDA_THRESHOLD)
                pure_r1 = (gold_rank == 1)
                pure_r5 = (gold_rank is not None and gold_rank <= 5)

                resultados_por_modelo[m].append({
                    "case_id": cid,
                    "query": q,
                    "gold": gold,
                    "stratum": strat,
                    "islands_selected": model_islands[m],
                    "pool_size": pool_size,
                    "top1_candidate": ranked_cands[0][0] if ranked_cands else None,
                    "top1_score": top1_score,
                    "gold_rank": gold_rank,
                    "gold_score": gold_score,
                    "pure_rr": pure_rr,
                    "covered": covered,
                    "hit_r1": hit_r1,
                    "hit_r5": hit_r5,
                    "pure_r1": pure_r1,
                    "pure_r5": pure_r5,
                    "latency_ms": t_total_q
                })
            else:  # Estrato C (Negativo)
                fp_at_1 = (pool_size >= 1 and top1_score >= LAMBDA_THRESHOLD)
                fp_at_5 = any(sc >= LAMBDA_THRESHOLD for conc, sc in ranked_cands[:5])
                abstention = not fp_at_1

                resultados_por_modelo[m].append({
                    "case_id": cid,
                    "query": q,
                    "gold": None,
                    "stratum": strat,
                    "islands_selected": model_islands[m],
                    "pool_size": pool_size,
                    "top1_candidate": ranked_cands[0][0] if ranked_cands else None,
                    "top1_score": top1_score,
                    "fp_at_1": fp_at_1,
                    "fp_at_5": fp_at_5,
                    "abstention": abstention,
                    "latency_ms": t_total_q
                })

    # 6. Cálculo Exhaustivo de Métricas por Estrato
    print("\n===================================================================================================")
    print("RESUMEN DE RESULTADOS — EXP-L TEST FINAL CONFIRMATORIO")
    print("===================================================================================================")

    for m in modelos:
        res_m = resultados_por_modelo[m]
        res_a0 = [r for r in res_m if r["stratum"] == "A0"]
        res_b = [r for r in res_m if r["stratum"] == "B"]
        res_c = [r for r in res_m if r["stratum"] == "C"]

        def calcular_stats_pos(res_list: List[Dict[str, Any]]) -> Dict[str, Any]:
            n = len(res_list)
            if n == 0:
                return {}
            hits_r1 = sum(1 for r in res_list if r["hit_r1"])
            hits_r5 = sum(1 for r in res_list if r["hit_r5"])
            pure_r1_cnt = sum(1 for r in res_list if r["pure_r1"])
            pure_r5_cnt = sum(1 for r in res_list if r["pure_r5"])
            cov_cnt = sum(1 for r in res_list if r["covered"])
            mrr_pure = float(np.mean([r["pure_rr"] for r in res_list]))
            covered_rr = [r["pure_rr"] for r in res_list if r["covered"]]
            mrr_covered = float(np.mean(covered_rr)) if covered_rr else 0.0
            avg_lat = float(np.mean([r["latency_ms"] for r in res_list]))
            avg_pool = float(np.mean([r["pool_size"] for r in res_list]))
            wilson_low, wilson_high = wilson_score_interval(hits_r5, n, 0.95)

            return {
                "n": n,
                "hits_r1": hits_r1,
                "r1_pct": round(hits_r1 / n * 100.0, 2),
                "hits_r5": hits_r5,
                "r5_pct": round(hits_r5 / n * 100.0, 2),
                "pure_r1": pure_r1_cnt,
                "pure_r5": pure_r5_cnt,
                "mrr_global_puro": round(mrr_pure, 4),
                "coverage_cnt": cov_cnt,
                "coverage_pct": round(cov_cnt / n * 100.0, 2),
                "mrr_covered": round(mrr_covered, 4),
                "wilson_95_ci_r5": [round(wilson_low * 100.0, 2), round(wilson_high * 100.0, 2)],
                "avg_latency_ms": round(avg_lat, 2),
                "avg_pool_size": round(avg_pool, 1)
            }

        def calcular_stats_neg(res_list: List[Dict[str, Any]]) -> Dict[str, Any]:
            n = len(res_list)
            if n == 0:
                return {}
            fp1_cnt = sum(1 for r in res_list if r["fp_at_1"])
            fp5_cnt = sum(1 for r in res_list if r["fp_at_5"])
            abs_cnt = sum(1 for r in res_list if r["abstention"])
            avg_lat = float(np.mean([r["latency_ms"] for r in res_list]))
            return {
                "n": n,
                "fp1_cnt": fp1_cnt,
                "fp1_pct": round(fp1_cnt / n * 100.0, 2),
                "fp5_cnt": fp5_cnt,
                "fp5_pct": round(fp5_cnt / n * 100.0, 2),
                "abstention_cnt": abs_cnt,
                "abstention_pct": round(abs_cnt / n * 100.0, 2),
                "avg_latency_ms": round(avg_lat, 2)
            }

        stats_a0 = calcular_stats_pos(res_a0)
        stats_b = calcular_stats_pos(res_b)
        stats_c = calcular_stats_neg(res_c)

        metricas_resumen[m] = {
            "A0_zero_overlap": stats_a0,
            "B_asociacion_tematica": stats_b,
            "C_negativos": stats_c
        }

        print(f"\n--- MODELO: {m} ---")
        print(f"  [A0 N=20] R@1: {stats_a0['hits_r1']}/20 ({stats_a0['r1_pct']}%) | R@5: {stats_a0['hits_r5']}/20 ({stats_a0['r5_pct']}%) [CI: {stats_a0['wilson_95_ci_r5']}%] | MRR Puro: {stats_a0['mrr_global_puro']} | Cov: {stats_a0['coverage_pct']}%")
        print(f"  [B  N=20] R@1: {stats_b['hits_r1']}/20 ({stats_b['r1_pct']}%) | R@5: {stats_b['hits_r5']}/20 ({stats_b['r5_pct']}%) [CI: {stats_b['wilson_95_ci_r5']}%] | MRR Puro: {stats_b['mrr_global_puro']} | Cov: {stats_b['coverage_pct']}%")
        print(f"  [C  N=15] FP@1: {stats_c['fp1_cnt']}/15 ({stats_c['fp1_pct']}%) | FP@5: {stats_c['fp5_cnt']}/15 ({stats_c['fp5_pct']}%) | Abstención: {stats_c['abstention_pct']}%")

    # 7. Comparaciones Pareadas de McNemar sobre R@5
    print("\n===================================================================================================")
    print("TESTS PAREADOS DE MCNEMAR SOBRE R@5 (A0 y B)")
    print("===================================================================================================")

    comparaciones_mcnemar = {}
    pares = [
        ("M0_PPMI_solo", "M1_AC_PPMI_13D"),
        ("M0_PPMI_solo", "M2_AD_PPMI_HDC"),
        ("M0_PPMI_solo", "M3_ACD_ponderado"),
        ("M0_PPMI_solo", "M4_union_truncada_Top6"),
        ("M1_AC_PPMI_13D", "M3_ACD_ponderado"),
        ("M2_AD_PPMI_HDC", "M3_ACD_ponderado"),
        ("M3_ACD_ponderado", "M4_union_truncada_Top6")
    ]

    for m1, m2 in pares:
        for strat in ["A0", "B"]:
            res_m1 = [r for r in resultados_por_modelo[m1] if r["stratum"] == strat]
            res_m2 = [r for r in resultados_por_modelo[m2] if r["stratum"] == strat]

            b = 0  # m1 acierta, m2 falla
            c = 0  # m1 falla, m2 acierta
            for r1, r2 in zip(res_m1, res_m2):
                h1 = r1["hit_r5"]
                h2 = r2["hit_r5"]
                if h1 and not h2:
                    b += 1
                elif not h1 and h2:
                    c += 1

            p_val = mcnemar_exact_pvalue(b, c)
            key = f"{m1}_vs_{m2}_{strat}"
            comparaciones_mcnemar[key] = {
                "m1": m1, "m2": m2, "stratum": strat,
                "m1_solo_acierta": b, "m2_solo_acierta": c,
                "p_value_exacto": round(p_val, 4)
            }
            print(f"• {m1} vs {m2} [{strat}]: b(M1 sólo)={b}, c(M2 sólo)={c} -> McNemar p-value = {p_val:.4f}")

    # 8. Guardar Resultados y Generar Manifest
    output_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_name": "EXP-L Test Final Confirmatorio (M0..M4)",
        "protocol": "Single-Run Deterministic Freeze Audit",
        "hashes": {
            "git_head": "999d3efb84d6ac9c24756b888f6e0f1b83739e3f",
            "db_snapshot_sha256": sha_db,
            "labels_sha256": sha_labels,
            "dataset_sha256": sha_dataset,
            "evaluator_script_sha256": sha_script
        },
        "hyperparameters_frozen": {
            "K_islands": K_ISLANDS,
            "lambda_threshold": LAMBDA_THRESHOLD,
            "tiebreaker": TIEBREAKER,
            "weights_M1": {"A": 0.5, "C": 0.5},
            "weights_M2": {"A": 0.5, "D": 0.5},
            "weights_M3": {"A": 0.50, "C": 0.25, "D": 0.25},
            "M4_architecture": "Union of Truncated Top-6 Lists (AC, AD) with S_merge Interleaved Rerank"
        },
        "metrics_summary": metricas_resumen,
        "mcnemar_pairwise_tests": comparaciones_mcnemar,
        "detailed_results_by_model": resultados_por_modelo
    }

    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Resultados completos guardados en: {OUTPUT_RESULTS_PATH}")

    # Generar Manifest Criptográfico
    manifest_payload = {
        "manifest_name": "EXP-L Test Final Frozen Cryptographic Manifest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": "999d3efb84d6ac9c24756b888f6e0f1b83739e3f",
        "artifacts_sha256": {
            "snapshots/qa_escape_qcr_20260811.db": sha_db,
            "scripts/experimentos/expA_labels.json": sha_labels,
            "docs/final_test_dataset_proposed.json": sha_dataset,
            "scripts/experimentos/expL_test_final.py": sha_script
        },
        "models_evaluated": modelos,
        "total_test_cases": len(eval_cases),
        "status": "FROZEN_AND_EXECUTED"
    }

    with open(OUTPUT_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2, ensure_ascii=False)

    print(f"[+] Manifest criptográfico guardado en: {OUTPUT_MANIFEST_PATH}")
    print("===================================================================================================")


if __name__ == "__main__":
    ejecutar_evaluacion()
