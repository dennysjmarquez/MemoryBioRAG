#!/usr/bin/env python3
"""
scripts/ejecutar_fases_1_y_2_aureon.py
=============================================================================
Ejecución rigurosa de las Fases 1 y 2 según el Plan de Mejora Top-1 (v4.1).

Requisitos aprobados por Aureon:
1. Trazabilidad Criptográfica: SHA-256 de snapshot, dataset y script.
2. Controles Negativos Separados: 20 desarrollo / 20 reservados deterministas.
3. Tres Ejecuciones de Referencia Obligatorias:
   - A. Baseline oficial (debe verificar 803/875 Top-1, 875/875 Top-5, 72 misses).
   - B. v32.7 histórico (lógica original con umbral binario).
   - C. Candidata continua piloto (1 config media de prueba).
4. Fase 1: Diagnóstico de los 72 Misses (JSON con variables, contribuciones,
   márgenes y rescatable_aritmetico para 64 configs continuas).
5. Fase 2: Simulación sobre pipeline completo (Discovery 442 casos).
   Registro de rescatable_aritmetico vs rescatable_pipeline por caso.
   Preservación de las 64 configuraciones completas.
6. Cero modificaciones a core/.
=============================================================================
"""

import os
import sys
import json
import time
import math
import hashlib
import sqlite3
import argparse
import unicodedata
import re
import difflib
from collections import defaultdict
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG
from core.memory import constants

SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
SEED = "biorag_split_seed_20261008_deterministic"

def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def _normalizar_token(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)).lower()

def _clave_etiqueta(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', _normalizar_token(texto))

def _restaurar_estado_nodos(db, estado_inicial):
    actual = db.cursor.execute(
        "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
    ).fetchall()
    cambios = []
    for concepto, estado, peso in actual:
        original = estado_inicial.get(concepto)
        if original and (original[0] != estado or original[1] != peso):
            cambios.append((original[0], original[1], concepto))
    if not cambios:
        return 0
    db.cursor.executemany(
        "UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?",
        cambios,
    )
    db.conn.commit()
    return len(cambios)

def get_hash_key(case_id: str, seed: str) -> str:
    return hashlib.sha256(f"{case_id}_{seed}".encode("utf-8")).hexdigest()

def create_deterministic_splits(qa_cases, baseline_results, neg_cases):
    # 1. Estratificación por (categoría, hit_top1_en_A)
    strata = defaultdict(list)
    for c in qa_cases:
        cid = c["id"]
        cat = c["categoria"]
        is_hit = baseline_results[cid]["found_at"] == 1
        strata[(cat, is_hit)].append(c)

    discovery = []
    validation = []
    for (cat, is_hit), items in sorted(strata.items(), key=lambda x: (x[0][0], x[0][1])):
        sorted_items = sorted(items, key=lambda x: get_hash_key(x["id"], SEED))
        for idx, item in enumerate(sorted_items):
            if idx % 2 == 0:
                discovery.append(item)
            else:
                validation.append(item)

    # 2. Split determinista de controles negativos: 20 dev / 20 reservados
    sorted_negs = sorted(neg_cases, key=lambda x: get_hash_key(x["id"], SEED))
    neg_dev = []
    neg_reserved = []
    for idx, item in enumerate(sorted_negs):
        if idx % 2 == 0:
            neg_dev.append(item)
        else:
            neg_reserved.append(item)

    return discovery, validation, neg_dev, neg_reserved

def setup_temp_db():
    temp_db = f"/tmp/memory_biorag_aureon_{os.getpid()}_{int(time.time())}.db"
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass

    src_uri = Path(SNAPSHOT_PATH).expanduser().resolve().as_uri() + "?mode=ro"
    conn_src = sqlite3.connect(src_uri, uri=True)
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_src.close()
    conn_dst.close()
    return temp_db

def load_cases():
    cases = []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases

class BioRAGExperimentHarness:
    def __init__(self, temp_db, cases):
        self.temp_db = temp_db
        self.cases = cases
        os.environ["BIORAG_NO_LOG"] = "1"
        os.environ["BIORAG_RERANKING_JACCARD_ENABLED"] = "0"
        self.db = SQLiteMemoryBioRAG(db_path=temp_db)

        # Mapeo para resolver etiquetas
        self.clave_a_conceptos = defaultdict(list)
        for (_conc,) in self.db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
            if _conc:
                self.clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)

        self.UMBRAL_DIFUSO = 0.94
        self.MARGEN_DIFUSO = 0.02

        # Detectar queries ambiguas
        golds_por_query = defaultdict(set)
        for _c in cases:
            if _c.get("concepto_esperado"):
                golds_por_query[_c["query"].strip().lower()].add(_c["concepto_esperado"])
        self.queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

        self.estado_inicial_nodos = {
            r[0]: (r[1], r[2])
            for r in self.db.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall()
        }
        self.original_calcular = self.db._calcular_score_hibrido

    def resolver_etiqueta(self, esperado):
        if not esperado:
            return esperado, ""
        row = self.db.cursor.execute("SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)).fetchone()
        if row:
            return esperado, ""
        clave = _clave_etiqueta(esperado)
        candidatos = self.clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0], "obsoleta_resuelta"
        cercanos = difflib.get_close_matches(clave, list(self.clave_a_conceptos.keys()), n=3, cutoff=0.80)
        if not cercanos:
            return esperado, "inexistente"
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = difflib.SequenceMatcher(None, clave, cercanos[1]).ratio() if len(cercanos) > 1 else 0.0
        opciones = self.clave_a_conceptos[mejor_clave]
        if ratio < self.UMBRAL_DIFUSO:
            return esperado, "inexistente"
        if (ratio - segundo) < self.MARGEN_DIFUSO:
            return esperado, "obsoleta_ambigua_difusa"
        if len(opciones) > 1:
            return esperado, "obsoleta_ambigua"
        return opciones[0], "obsoleta_resuelta_difusa"

    def execute_eval(self, gate_fn=None, target_cases=None, capture_telemetry=False):
        telemetry = {}
        current_case_id = [None]
        case_cands_map = defaultdict(dict)

        if gate_fn is not None or capture_telemetry:
            def instrumented_scoring(*args, **kwargs):
                try:
                    caller_locals = sys._getframe(1).f_locals
                    concepto = caller_locals.get("concepto", "unknown")
                except Exception:
                    concepto = "unknown"

                raw_sigs = {
                    "bm25_norm": kwargs.get("bm25_norm", 0.0),
                    "dim_score": kwargs.get("dim_score", 0.0),
                    "concepto_ratio": kwargs.get("concepto_ratio", 0.0),
                    "sinonimos_ratio": kwargs.get("sinonimos_ratio", 0.0),
                    "peso_sinaptico": kwargs.get("peso_sinaptico", 0.0),
                    "jaccard": max(kwargs.get("score_latente", 0.0), kwargs.get("score_cadena", 0.0)),
                    "grupo_score": kwargs.get("grupo_score", 0.0),
                    "tematico_score": kwargs.get("tematico_score", 0.0),
                    "jsd_score": kwargs.get("jsd_score", 0.0),
                    "pred_score": kwargs.get("pred_score", 0.0),
                    "ppmi_score": kwargs.get("ppmi_score", 0.0),
                    "hub_match": kwargs.get("hub_match", 0.0),
                    "ncd_score": kwargs.get("ncd_score", 0.0),
                    "match_exacto": kwargs.get("match_exacto", False)
                }

                mod_kwargs = dict(kwargs)
                if gate_fn is not None:
                    mod_kwargs = gate_fn(mod_kwargs, concepto=concepto)

                sc = self.original_calcular(*args, **mod_kwargs)

                if capture_telemetry and current_case_id[0]:
                    case_cands_map[current_case_id[0]][concepto] = {
                        "concepto": concepto,
                        "raw_signals": raw_sigs,
                        "score_eval": sc
                    }
                return sc
            self.db._calcular_score_hibrido = instrumented_scoring
        else:
            self.db._calcular_score_hibrido = self.original_calcular

        cases_to_run = target_cases if target_cases is not None else self.cases
        results_map = {}
        top1_hits = 0
        top5_hits = 0
        rr_sum = 0.0
        retrieval_count = 0

        for case in cases_to_run:
            case_id = case["id"]
            current_case_id[0] = case_id
            category = case["categoria"]
            query = case["query"]
            expected = case.get("concepto_esperado")
            deep = case.get("deep", False)

            if expected:
                esperado_resuelto, motivo = self.resolver_etiqueta(expected)
                if motivo.startswith("obsoleta_resuelta"):
                    expected = esperado_resuelto

            if expected and query.strip().lower() in self.queries_ambiguas:
                _restaurar_estado_nodos(self.db, self.estado_inicial_nodos)
                continue

            if expected is None:
                _restaurar_estado_nodos(self.db, self.estado_inicial_nodos)
                continue

            retrieval_count += 1

            if category == "dormido" and expected:
                self.db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
                self.db.conn.commit()
            elif expected:
                self.db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
                self.db.conn.commit()

            profundidad = "profundo" if (deep or category == "dormido") else "activos"
            results, total = self.db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)

            _restaurar_estado_nodos(self.db, self.estado_inicial_nodos)

            returned = [r[0] for r in results] if results else []
            scores = [r[4] for r in results] if results else []

            found_at = -1
            for idx, concept in enumerate(returned[:5]):
                if concept == expected:
                    found_at = idx + 1
                    break

            if found_at != -1:
                top5_hits += 1
                if found_at == 1:
                    top1_hits += 1
                rr_sum += 1.0 / found_at

            results_map[case_id] = {
                "id": case_id,
                "found_at": found_at,
                "winner": returned[0] if returned else None,
                "gold": expected,
                "winner_score": scores[0] if scores else 0.0,
                "gold_score": scores[found_at - 1] if found_at != -1 else 0.0,
                "top5": returned[:5],
                "top5_scores": scores[:5],
                "categoria": category,
                "query": query
            }

        # Restaurar función original
        self.db._calcular_score_hibrido = self.original_calcular

        return {
            "n": retrieval_count,
            "top1_hits": top1_hits,
            "top5_hits": top5_hits,
            "r1": top1_hits / retrieval_count if retrieval_count else 0.0,
            "r5": top5_hits / retrieval_count if retrieval_count else 0.0,
            "mrr": rr_sum / retrieval_count if retrieval_count else 0.0,
            "results_map": results_map,
            "telemetry": case_cands_map if capture_telemetry else None
        }

    def eval_negatives(self, neg_cases):
        fp_count = 0
        details = []
        for c in neg_cases:
            query = c["query"]
            results, total = self.db.buscar_por_frase(query, limite=5, profundidad="profundo" if c.get("deep", False) else "activos")
            _restaurar_estado_nodos(self.db, self.estado_inicial_nodos)
            is_fp = False
            top_score = 0.0
            top_concept = None
            if results and results[0][4] >= self.db.umbral_calibrado:
                is_fp = True
                fp_count += 1
                top_score = results[0][4]
                top_concept = results[0][0]
            details.append({
                "id": c["id"],
                "query": query,
                "is_fp": is_fp,
                "top_score": top_score,
                "top_concept": top_concept
            })
        return fp_count, len(neg_cases), details

def run_fase1_y_referencias():
    print("=" * 80)
    print("EJECUCIÓN DE FASE 1 Y REFERENCIAS A, B, C (PLAN TOP-1 v4.1)")
    print("=" * 80)

    # 1. Hashing criptográfico
    snap_sha = sha256_file(SNAPSHOT_PATH)
    cases_sha = sha256_file(CASES_FILE)
    print(f"[*] Snapshot SHA-256: {snap_sha}")
    print(f"[*] Dataset SHA-256:  {cases_sha}")

    # 2. Cargar casos y DB
    temp_db = setup_temp_db()
    cases = load_cases()
    harness = BioRAGExperimentHarness(temp_db, cases)

    # Separar casos
    retrieval_cases = [
        c for c in cases
        if c.get("concepto_esperado") and c["query"].strip().lower() not in harness.queries_ambiguas
    ]
    neg_cases = [c for c in cases if c.get("concepto_esperado") is None or c.get("categoria") == "negativo"]

    print(f"[*] Total casos de recuperación: {len(retrieval_cases)}")
    print(f"[*] Total controles negativos:   {len(neg_cases)}")

    # -------------------------------------------------------------------------
    # EJECUCIÓN A: BASELINE OFICIAL (875 CASOS) CON CAPTURA DE TELEMETRÍA
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[1/4] EJECUCIÓN A: BASELINE OFICIAL (875 casos)...")
    print("-" * 80)
    t0 = time.time()
    base_eval = harness.execute_eval(gate_fn=None, target_cases=retrieval_cases, capture_telemetry=True)
    t_base = time.time() - t0

    print(f"Resultados Ejecución A (Baseline):")
    print(f" - Casos Evaluados: {base_eval['n']}")
    print(f" - Top-1 Hits:      {base_eval['top1_hits']} / {base_eval['n']} ({base_eval['r1']*100:.2f}%)")
    print(f" - Top-5 Hits:      {base_eval['top5_hits']} / {base_eval['n']} ({base_eval['r5']*100:.2f}%)")
    print(f" - MRR:             {base_eval['mrr']:.4f}")
    misses_count = base_eval['n'] - base_eval['top1_hits']
    print(f" - Misses Top-1:    {misses_count}")
    print(f" - Tiempo:          {t_base:.1f} s")

    # Verificación estricta (Criterio de Abandono 1)
    if base_eval['top1_hits'] != 803 or base_eval['top5_hits'] != 875 or misses_count != 72:
        print(f"\n[FATAL] ERROR DE REPRODUCIBILIDAD EN BASELINE A:")
        print(f"Se esperaba 803/875 Top-1, 875/875 Top-5 y 72 misses.")
        print(f"Se obtuvo: {base_eval['top1_hits']}/{base_eval['n']} Top-1, {base_eval['top5_hits']}/{base_eval['n']} Top-5.")
        print("Activando parada de emergencia según Sección 6 del Plan v4.1.")
        sys.exit(1)
    print("\n✅ VERIFICACIÓN FORMAL APROBADA: Baseline A reproduce con exactitud matemática 803/875 (91.77%) y 875/875 (100.0%).")

    # Crear splits deterministas ahora que tenemos baseline verificado
    discovery_cases, validation_cases, neg_dev, neg_reserved = create_deterministic_splits(
        retrieval_cases, base_eval["results_map"], neg_cases
    )
    print(f"\n[*] Split Determinista Creado:")
    print(f" - Discovery:      {len(discovery_cases)} casos")
    print(f" - Validation:     {len(validation_cases)} casos")
    print(f" - Negativos Dev:  {len(neg_dev)} casos")
    print(f" - Negativos Res:  {len(neg_reserved)} casos")

    # Evaluar controles negativos en baseline
    fp_dev, n_dev, _ = harness.eval_negatives(neg_dev)
    fp_res, n_res, _ = harness.eval_negatives(neg_reserved)
    print(f" - FP Dev Baseline:       {fp_dev} / {n_dev}")
    print(f" - FP Reservados Baseline: {fp_res} / {n_res}")

    # -------------------------------------------------------------------------
    # FASE 1: DIAGNÓSTICO DE LOS 72 MISSES
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[2/4] FASE 1: DIAGNÓSTICO DE LOS 72 MISSES (ANÁLISIS MATRICIAL)")
    print("-" * 80)

    # Identificar los 72 misses
    miss_case_ids = [cid for cid, r in base_eval["results_map"].items() if r["found_at"] != 1]
    print(f"[*] Analizando {len(miss_case_ids)} casos misses Top-1...")

    telemetry = base_eval["telemetry"]

    # Definir los 64 parámetros continuos del grid:
    # 4 valores saturation x 4 valores min_scale_tem x 4 valores min_scale_dim = 64 configs
    saturations = [0.3, 0.4, 0.5, 0.6]
    tem_min_scales = [0.25, 0.5, 0.75, 1.0]
    dim_min_scales = [0.25, 0.5, 0.75, 1.0]

    grid_configs = []
    cfg_idx = 0
    for sat in saturations:
        for t_min in tem_min_scales:
            for d_min in dim_min_scales:
                cfg_idx += 1
                grid_configs.append({
                    "config_id": f"CFG_{cfg_idx:02d}",
                    "saturation": sat,
                    "min_scale_tem": t_min,
                    "min_scale_dim": d_min
                })

    # Extraer diagnósticos detallados para cada uno de los 72 misses
    diagnostico_72 = []
    rescatables_por_config = defaultdict(int)

    # Calcular base_weight oficial de _calcular_score_hibrido
    _base_weights = {
        "bm25": 0.25, "dim": 0.14, "concepto": 0.08, "sinonimos": 0.08,
        "peso": 0.10, "jaccard": 0.10, "grupo": 0.10, "tematico": 0.08,
        "temporal": 0.04, "asoc": 0.02, "pred": 0.20, "hub": 0.20,
    }
    _base_sum = sum(_base_weights.values())  # 1.39
    total_base = _base_sum + constants.PPMI_VECTOR_WEIGHT + constants.NCD_PESO + constants.EPISODIO_TEMPORAL_PESO + constants.ANALOGIA_PESO + constants.CAMPO_POTENCIAL_PESO
    base_weight = 1.0 / total_base if total_base > 0 else 0.0

    for cid in miss_case_ids:
        b_res = base_eval["results_map"][cid]
        gold_name = b_res["gold"]
        winner_name = b_res["winner"]
        query = b_res["query"]
        category = b_res["categoria"]
        gold_rank = b_res["found_at"]
        gold_score_A = b_res["gold_score"]
        winner_score_A = b_res["winner_score"]
        margin_orig = gold_score_A - winner_score_A

        cands = telemetry.get(cid, {})
        gold_cand = cands.get(gold_name, {})
        winner_cand = cands.get(winner_name, {})

        gold_sigs = gold_cand.get("raw_signals", {})
        winner_sigs = winner_cand.get("raw_signals", {})

        # Broad contributions
        # tematico_score solo contribuye si hay gate léxico (bm25 > 0.001 or concepto_ratio > 0.001)
        g_tem_gated = gold_sigs.get("tematico_score", 0.0) if (gold_sigs.get("bm25_norm", 0.0) > 0.001 or gold_sigs.get("concepto_ratio", 0.0) > 0.001) else 0.0
        w_tem_gated = winner_sigs.get("tematico_score", 0.0) if (winner_sigs.get("bm25_norm", 0.0) > 0.001 or winner_sigs.get("concepto_ratio", 0.0) > 0.001) else 0.0

        gold_broad_contrib = base_weight * (0.14 * gold_sigs.get("dim_score", 0.0) + 0.08 * g_tem_gated)
        winner_broad_contrib = base_weight * (0.14 * winner_sigs.get("dim_score", 0.0) + 0.08 * w_tem_gated)

        # Evaluar para las 64 configuraciones
        config_evals = {}
        for cfg in grid_configs:
            cfg_id = cfg["config_id"]
            sat = cfg["saturation"]
            min_t = cfg["min_scale_tem"]
            min_d = cfg["min_scale_dim"]

            # Formula continua
            gold_spec = max(gold_sigs.get("bm25_norm", 0.0), gold_sigs.get("sinonimos_ratio", 0.0), gold_sigs.get("concepto_ratio", 0.0))
            winner_spec = max(winner_sigs.get("bm25_norm", 0.0), winner_sigs.get("sinonimos_ratio", 0.0), winner_sigs.get("concepto_ratio", 0.0))

            g_ratio = max(0.0, min(1.0, gold_spec / sat)) if sat > 0 else 0.0
            w_ratio = max(0.0, min(1.0, winner_spec / sat)) if sat > 0 else 0.0

            g_t_scale = 1.0 - (1.0 - min_t) * g_ratio
            g_d_scale = 1.0 - (1.0 - min_d) * g_ratio

            w_t_scale = 1.0 - (1.0 - min_t) * w_ratio
            w_d_scale = 1.0 - (1.0 - min_d) * w_ratio

            # Pérdida de score absoluto L
            L_gold = base_weight * (0.14 * gold_sigs.get("dim_score", 0.0) * (1.0 - g_d_scale) + 0.08 * g_tem_gated * (1.0 - g_t_scale))
            L_winner = base_weight * (0.14 * winner_sigs.get("dim_score", 0.0) * (1.0 - w_d_scale) + 0.08 * w_tem_gated * (1.0 - w_t_scale))

            delta_nuevo = margin_orig + L_winner - L_gold
            rescatable_aritmetico = (delta_nuevo > 0)

            if rescatable_aritmetico:
                rescatables_por_config[cfg_id] += 1

            config_evals[cfg_id] = {
                "gold_spec": round(gold_spec, 4),
                "winner_spec": round(winner_spec, 4),
                "gold_tem_scale": round(g_t_scale, 4),
                "gold_dim_scale": round(g_d_scale, 4),
                "winner_tem_scale": round(w_t_scale, 4),
                "winner_dim_scale": round(w_d_scale, 4),
                "L_gold": round(L_gold, 6),
                "L_winner": round(L_winner, 6),
                "delta_nuevo": round(delta_nuevo, 6),
                "rescatable_aritmetico": bool(rescatable_aritmetico)
            }

        diagnostico_72.append({
            "case_id": cid,
            "query": query,
            "categoria": category,
            "gold": gold_name,
            "winner": winner_name,
            "gold_rank_A": gold_rank,
            "score_gold_A": round(gold_score_A, 6),
            "score_winner_A": round(winner_score_A, 6),
            "margin_original": round(margin_orig, 6),
            "gold_signals": gold_sigs,
            "winner_signals": winner_sigs,
            "gold_broad_contrib": round(gold_broad_contrib, 6),
            "winner_broad_contrib": round(winner_broad_contrib, 6),
            "configs": config_evals
        })

    # Guardar reporte de Fase 1
    fase1_data = {
        "metadata": {
            "snapshot_sha256": snap_sha,
            "dataset_sha256": cases_sha,
            "total_misses": len(diagnostico_72),
            "grid_configs_count": len(grid_configs),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "resumen_rescatabilidad_aritmetica": {
            cfg_id: count for cfg_id, count in sorted(rescatables_por_config.items())
        },
        "misses": diagnostico_72
    }
    fase1_path = os.path.join(BASE_DIR, "docs", "fase1_diagnostico_72_misses.json")
    with open(fase1_path, "w", encoding="utf-8") as f:
        json.dump(fase1_data, f, indent=2, ensure_ascii=False)
    print(f"[*] Reporte Fase 1 guardado en: {fase1_path}")

    max_rescates = max(rescatables_por_config.values()) if rescatables_por_config else 0
    min_rescates = min(rescatables_por_config.values()) if rescatables_por_config else 0
    print(f"[*] Rescatabilidad Aritmética sobre los 72 Misses:")
    print(f" - Rango de misses con delta_nuevo > 0: entre {min_rescates} y {max_rescates} casos (según config).")
    if max_rescates < 8:
        print("⚠️ ADVERTENCIA: Menos de 8 misses muestran delta_nuevo > 0 (Señal de reconsideración según Plan v4.1).")
    else:
        print(f"✅ FASE 1 SUPERA UMBRAL EXPLORATORIO: Hasta {max_rescates} misses muestran margen positivo aritmético.")

    # -------------------------------------------------------------------------
    # EJECUCIÓN B: REFERENCIA v32.7 HISTÓRICA (UMBRAL BINARIO ORIGINAL)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[3/4] EJECUCIÓN B: REPRODUCCIÓN HISTÓRICA v32.7 (UMBRAL BINARIO)")
    print("-" * 80)

    # Lógica exacta de v32.7:
    # spec = max(bm25, sin, ppmi, c_ratio)
    # if spec >= 0.2: tem *= 0.5, dim *= 0.75
    def gate_v32_7(kwargs, concepto=""):
        kw = dict(kwargs)
        bm25 = kw.get("bm25_norm", 0.0)
        sin = kw.get("sinonimos_ratio", 0.0)
        ppmi = kw.get("ppmi_score", 0.0)
        c_ratio = kw.get("concepto_ratio", 0.0)
        spec_strength = max(bm25, sin, ppmi, c_ratio)
        if spec_strength >= 0.2:
            kw["tematico_score"] = kw.get("tematico_score", 0.0) * 0.5
            kw["dim_score"] = kw.get("dim_score", 0.0) * 0.75
        return kw

    t0 = time.time()
    disc_v32_7 = harness.execute_eval(gate_fn=gate_v32_7, target_cases=discovery_cases)
    val_v32_7 = harness.execute_eval(gate_fn=gate_v32_7, target_cases=validation_cases)
    t_v32_7 = time.time() - t0

    # Contar ganancias y pérdidas en Discovery
    disc_gains = 0
    disc_losses = 0
    disc_top5_losses = 0
    for cid, item in disc_v32_7["results_map"].items():
        base_item = base_eval["results_map"][cid]
        if base_item["found_at"] != 1 and item["found_at"] == 1:
            disc_gains += 1
        elif base_item["found_at"] == 1 and item["found_at"] != 1:
            disc_losses += 1
        if base_item["found_at"] != -1 and item["found_at"] == -1:
            disc_top5_losses += 1

    # Contar ganancias y pérdidas en Validation
    val_gains = 0
    val_losses = 0
    val_top5_losses = 0
    for cid, item in val_v32_7["results_map"].items():
        base_item = base_eval["results_map"][cid]
        if base_item["found_at"] != 1 and item["found_at"] == 1:
            val_gains += 1
        elif base_item["found_at"] == 1 and item["found_at"] != 1:
            val_losses += 1
        if base_item["found_at"] != -1 and item["found_at"] == -1:
            val_top5_losses += 1

    print(f"Resultados Referencia B (v32.7 original):")
    print(f" - Discovery:  R@1 = {disc_v32_7['top1_hits']}/{disc_v32_7['n']} ({disc_v32_7['r1']*100:.2f}%) | Ganancias: +{disc_gains}, Pérdidas: -{disc_losses} | Pérdidas Top-5: {disc_top5_losses}")
    print(f" - Validation: R@1 = {val_v32_7['top1_hits']}/{val_v32_7['n']} ({val_v32_7['r1']*100:.2f}%) | Ganancias: +{val_gains}, Pérdidas: -{val_losses} | Pérdidas Top-5: {val_top5_losses}")
    print(f" - Tiempo:     {t_v32_7:.1f} s")

    ref_b_report = {
        "metadata": {
            "snapshot_sha256": snap_sha,
            "dataset_sha256": cases_sha,
            "version": "v32.7_reference_check"
        },
        "discovery": {
            "r1": disc_v32_7["r1"], "r5": disc_v32_7["r5"], "mrr": disc_v32_7["mrr"],
            "gains": disc_gains, "losses": disc_losses, "top5_losses": disc_top5_losses
        },
        "validation": {
            "r1": val_v32_7["r1"], "r5": val_v32_7["r5"], "mrr": val_v32_7["mrr"],
            "gains": val_gains, "losses": val_losses, "top5_losses": val_top5_losses
        }
    }
    ref_b_path = os.path.join(BASE_DIR, "docs", "ref_b_v32_7_results.json")
    with open(ref_b_path, "w", encoding="utf-8") as f:
        json.dump(ref_b_report, f, indent=2, ensure_ascii=False)
    print(f"[*] Reporte Referencia B guardado en: {ref_b_path}")

    # -------------------------------------------------------------------------
    # EJECUCIÓN C: CANDIDATA CONTINUA PILOTO (1 CONFIGURACIÓN SOBRE DISCOVERY)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[4/4] EJECUCIÓN C: CANDIDATA CONTINUA PILOTO (DISCOVERY 442 CASOS)")
    print("-" * 80)

    # Piloto con parámetros medios: saturation=0.5, min_scale_tem=0.5, min_scale_dim=0.75
    pilot_sat = 0.5
    pilot_min_t = 0.5
    pilot_min_d = 0.75

    def gate_pilot_continuous(kwargs, concepto=""):
        kw = dict(kwargs)
        bm25 = kw.get("bm25_norm", 0.0)
        sin = kw.get("sinonimos_ratio", 0.0)
        c_ratio = kw.get("concepto_ratio", 0.0)
        spec = max(bm25, sin, c_ratio)
        ratio = max(0.0, min(1.0, spec / pilot_sat)) if pilot_sat > 0 else 0.0
        t_scale = 1.0 - (1.0 - pilot_min_t) * ratio
        d_scale = 1.0 - (1.0 - pilot_min_d) * ratio
        kw["tematico_score"] = kw.get("tematico_score", 0.0) * t_scale
        kw["dim_score"] = kw.get("dim_score", 0.0) * d_scale
        return kw

    t0 = time.time()
    pilot_eval = harness.execute_eval(gate_fn=gate_pilot_continuous, target_cases=discovery_cases)
    t_pilot = time.time() - t0

    pilot_gains = 0
    pilot_losses = 0
    pilot_top5_losses = 0
    for cid, item in pilot_eval["results_map"].items():
        base_item = base_eval["results_map"][cid]
        if base_item["found_at"] != 1 and item["found_at"] == 1:
            pilot_gains += 1
        elif base_item["found_at"] == 1 and item["found_at"] != 1:
            pilot_losses += 1
        if base_item["found_at"] != -1 and item["found_at"] == -1:
            pilot_top5_losses += 1

    print(f"Resultados Ejecución C (Piloto Continuo sat=0.5, tem=0.5, dim=0.75):")
    print(f" - Discovery R@1:         {pilot_eval['top1_hits']}/{pilot_eval['n']} ({pilot_eval['r1']*100:.2f}%)")
    print(f" - Discovery R@5:         {pilot_eval['top5_hits']}/{pilot_eval['n']} ({pilot_eval['r5']*100:.2f}%)")
    print(f" - Ganancias Top-1:       +{pilot_gains}")
    print(f" - Pérdidas Top-1:        -{pilot_losses}")
    print(f" - Delta Neto Top-1:      +{pilot_gains - pilot_losses}")
    print(f" - Pérdidas Top-5:        {pilot_top5_losses}")
    print(f" - Tiempo:                {t_pilot:.1f} s")

    ref_c_report = {
        "metadata": {
            "snapshot_sha256": snap_sha,
            "dataset_sha256": cases_sha,
            "version": "continuous_pilot_c",
            "params": {"saturation": pilot_sat, "min_scale_tem": pilot_min_t, "min_scale_dim": pilot_min_d}
        },
        "discovery": {
            "r1": pilot_eval["r1"], "r5": pilot_eval["r5"], "mrr": pilot_eval["mrr"],
            "gains": pilot_gains, "losses": pilot_losses, "net_delta": pilot_gains - pilot_losses,
            "top5_losses": pilot_top5_losses
        }
    }
    ref_c_path = os.path.join(BASE_DIR, "docs", "ref_c_piloto_results.json")
    with open(ref_c_path, "w", encoding="utf-8") as f:
        json.dump(ref_c_report, f, indent=2, ensure_ascii=False)
    print(f"[*] Reporte Referencia C guardado en: {ref_c_path}")

    print("\n" + "=" * 80)
    print("FASE 1 Y REFERENCIAS A, B, C COMPLETADAS EXITOSAMENTE")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Ejecución de Fases 1 y 2 (Plan Top-1 v4.1)")
    parser.add_argument("--fase1_y_referencias", action="store_true", help="Ejecutar Referencias A, B, C y Fase 1 Diagnóstico")
    args = parser.parse_args()

    if args.fase1_y_referencias or len(sys.argv) == 1:
        run_fase1_y_referencias()

if __name__ == "__main__":
    main()
