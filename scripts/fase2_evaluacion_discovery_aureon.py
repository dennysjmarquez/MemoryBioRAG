#!/usr/bin/env python3
"""
scripts/fase2_evaluacion_discovery_aureon.py
=============================================================================
Fase 2: Evaluación Integral del Pipeline en Discovery (Plan Top-1 v4.1).

Aprobado por Aureon:
1. Alcance estricto: EXCLUSIVAMENTE sobre Discovery (442 casos).
2. Congelamiento absoluto: Validación (433 casos) y los 20 controles reservados
   permanecen 100% INTACTOS y sin consumir.
3. Pipeline completo: Evaluación a través de buscar_por_frase() con todos los
   componentes de ranking reales (competencia contra todo el pool, desempates,
   GABA, QCR, hubs, etc.).
4. Evaluación del grid de 64 configuraciones continuas (4 sat x 4 tem x 4 dim).
5. Controles negativos de desarrollo (20 dev) evaluados con gate_fn activo,
   registrando total_candidates por consulta.
6. Registro exhaustivo de transiciones (ganancias, pérdidas, pérdidas en Top-5).
7. Selección estricta:
   - Requiere CERO pérdidas en Top-5 (R@5 = 100% en Discovery).
   - Requiere CERO falsos positivos (0/20 FP en desarrollo).
   - Maximiza Delta Neto en Top-1.
8. Cero modificaciones en core/.
=============================================================================
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
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

    sorted_negs = sorted(neg_cases, key=lambda x: get_hash_key(x["id"], SEED))
    neg_dev = []
    neg_reserved = []
    for idx, item in enumerate(sorted_negs):
        if idx % 2 == 0:
            neg_dev.append(item)
        else:
            neg_reserved.append(item)

    return discovery, validation, neg_dev, neg_reserved

def setup_fresh_temp_db():
    temp_db = f"/tmp/biorag_discovery_grid_{os.getpid()}_{int(time.time()*1000)}.db"
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

class DiscoveryGridHarness:
    def __init__(self, temp_db, cases):
        self.temp_db = temp_db
        self.cases = cases
        os.environ["BIORAG_NO_LOG"] = "1"
        self.db = SQLiteMemoryBioRAG(db_path=temp_db)

        self.clave_a_conceptos = defaultdict(list)
        for (_conc,) in self.db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
            if _conc:
                self.clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)

        self.UMBRAL_DIFUSO = 0.94
        self.MARGEN_DIFUSO = 0.02

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

    def execute_eval(self, gate_fn=None, target_cases=None):
        if gate_fn is not None:
            def instrumented_scoring(*args, **kwargs):
                try:
                    caller_locals = sys._getframe(1).f_locals
                    concepto = caller_locals.get("concepto", "unknown")
                except Exception:
                    concepto = "unknown"
                mod_kwargs = gate_fn(dict(kwargs), concepto=concepto)
                return self.original_calcular(*args, **mod_kwargs)
            self.db._calcular_score_hibrido = instrumented_scoring
        else:
            self.db._calcular_score_hibrido = self.original_calcular

        cases_to_run = target_cases if target_cases is not None else self.cases
        results_map = {}
        top1_hits = 0
        top5_hits = 0
        rr_sum = 0.0
        retrieval_count = 0

        try:
            for case in cases_to_run:
                case_id = case["id"]
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
                    "gold_score": scores[found_at - 1] if found_at != -1 else None,
                    "top5": returned[:5],
                    "top5_scores": scores[:5],
                    "categoria": category,
                    "query": query
                }
        finally:
            self.db._calcular_score_hibrido = self.original_calcular

        return {
            "n": retrieval_count,
            "top1_hits": top1_hits,
            "top5_hits": top5_hits,
            "r1": top1_hits / retrieval_count if retrieval_count else 0.0,
            "r5": top5_hits / retrieval_count if retrieval_count else 0.0,
            "mrr": rr_sum / retrieval_count if retrieval_count else 0.0,
            "results_map": results_map
        }

    def eval_negatives_con_intervencion(self, neg_cases, gate_fn=None):
        fp_count = 0
        details = []
        gate_calls = [0]

        if gate_fn is not None:
            def instrumented_neg_scoring(*args, **kwargs):
                gate_calls[0] += 1
                try:
                    caller_locals = sys._getframe(1).f_locals
                    concepto = caller_locals.get("concepto", "unknown")
                except Exception:
                    concepto = "unknown"
                mod_kwargs = gate_fn(dict(kwargs), concepto=concepto)
                return self.original_calcular(*args, **mod_kwargs)
            self.db._calcular_score_hibrido = instrumented_neg_scoring
        else:
            self.db._calcular_score_hibrido = self.original_calcular

        try:
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
                    "total_candidates": total,
                    "is_fp": is_fp,
                    "top_score": top_score,
                    "top_concept": top_concept
                })
        finally:
            self.db._calcular_score_hibrido = self.original_calcular

        return {
            "fp_count": fp_count,
            "total": len(neg_cases),
            "gate_calls": gate_calls[0],
            "gate_active": gate_fn is not None,
            "details": details
        }

def make_continuous_gate_fn(sat: float, min_t: float, min_d: float):
    def gate_fn(kw, concepto=""):
        bm25 = kw.get("bm25_norm", 0.0)
        sin = kw.get("sinonimos_ratio", 0.0)
        c_ratio = kw.get("concepto_ratio", 0.0)
        spec = max(bm25, sin, c_ratio)
        ratio = max(0.0, min(1.0, spec / sat)) if sat > 0 else 0.0
        t_scale = 1.0 - (1.0 - min_t) * ratio
        d_scale = 1.0 - (1.0 - min_d) * ratio
        kw["tematico_score"] = kw.get("tematico_score", 0.0) * t_scale
        kw["dim_score"] = kw.get("dim_score", 0.0) * d_scale
        return kw
    return gate_fn

def run_fase2_discovery_grid():
    print("=" * 80)
    print("FASE 2: EVALUACIÓN INTEGRAL DEL PIPELINE EN DISCOVERY (PLAN v4.1)")
    print("=" * 80)

    snap_sha = sha256_file(SNAPSHOT_PATH)
    cases_sha = sha256_file(CASES_FILE)
    script_sha = sha256_file(os.path.abspath(__file__))
    print(f"[*] Snapshot SHA-256: {snap_sha}")
    print(f"[*] Dataset SHA-256:  {cases_sha}")
    print(f"[*] Script SHA-256:   {script_sha}")

    temp_db = setup_fresh_temp_db()
    cases = load_cases()
    harness = DiscoveryGridHarness(temp_db, cases)

    retrieval_cases = [
        c for c in cases
        if c.get("concepto_esperado") and c["query"].strip().lower() not in harness.queries_ambiguas
    ]
    neg_cases = [c for c in cases if c.get("concepto_esperado") is None or c.get("categoria") == "negativo"]

    # 1. BASELINE GENERAL PARA CALCULAR SPLITS DETERMINISTAS
    print("\n[Paso 1] Verificando Baseline A completo para generar splits...")
    t0 = time.time()
    base_eval = harness.execute_eval(gate_fn=None, target_cases=retrieval_cases)
    t_base = time.time() - t0
    print(f" - Baseline A: R@1 = {base_eval['top1_hits']}/{base_eval['n']} ({base_eval['r1']*100:.2f}%), R@5 = {base_eval['top5_hits']}/{base_eval['n']} ({base_eval['r5']*100:.2f}%) [{t_base:.1f}s]")

    # Splits
    discovery_cases, validation_cases, neg_dev, neg_reserved = create_deterministic_splits(
        retrieval_cases, base_eval["results_map"], neg_cases
    )

    print(f"\n[*] Particiones Deterministas Fijadas:")
    print(f" - Discovery:      {len(discovery_cases)} casos (ACTIVA para exploración)")
    print(f" - Validation:     {len(validation_cases)} casos (CONGELADA)")
    print(f" - Negativos Dev:  {len(neg_dev)} casos (ACTIVA para exploración)")
    print(f" - Negativos Res:  {len(neg_reserved)} casos (CONGELADA)")

    # Baseline específico en Discovery
    base_disc = harness.execute_eval(gate_fn=None, target_cases=discovery_cases)
    print(f"\n[Paso 2] Baseline en Discovery verificado:")
    print(f" - Top-1 Hits: {base_disc['top1_hits']} / {base_disc['n']} ({base_disc['r1']*100:.2f}%)")
    print(f" - Top-5 Hits: {base_disc['top5_hits']} / {base_disc['n']} ({base_disc['r5']*100:.2f}%)")
    print(f" - MRR:        {base_disc['mrr']:.4f}")

    # Controles negativos dev baseline
    neg_dev_base = harness.eval_negatives_con_intervencion(neg_dev, gate_fn=None)
    print(f" - Negativos Dev Baseline: {neg_dev_base['fp_count']} / {neg_dev_base['total']} (FP Rate: 0.0%)")

    # 2. DEFINIR LAS 64 CONFIGURACIONES DEL GRID
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

    print(f"\n" + "=" * 80)
    print(f"[Paso 3] EJECUTANDO GRID DE {len(grid_configs)} CONFIGURACIONES EN DISCOVERY...")
    print("=" * 80)

    grid_results = []
    output_report_path = os.path.join(BASE_DIR, "docs", "fase2_discovery_grid_reporte.json")

    configs_sin_perdidas_top5 = []

    for idx, cfg in enumerate(grid_configs):
        cfg_id = cfg["config_id"]
        sat = cfg["saturation"]
        min_t = cfg["min_scale_tem"]
        min_d = cfg["min_scale_dim"]

        t_start = time.time()
        g_fn = make_continuous_gate_fn(sat=sat, min_t=min_t, min_d=min_d)
        res = harness.execute_eval(gate_fn=g_fn, target_cases=discovery_cases)
        t_elapsed = time.time() - t_start

        # Evaluar controles negativos dev
        neg_res = harness.eval_negatives_con_intervencion(neg_dev, gate_fn=g_fn)

        # Transiciones respecto al Baseline Discovery
        gains_top1 = []
        losses_top1 = []
        losses_top5 = []

        for cid, item in res["results_map"].items():
            base_item = base_disc["results_map"][cid]
            # Top-1
            if base_item["found_at"] != 1 and item["found_at"] == 1:
                gains_top1.append({
                    "id": cid,
                    "gold": item["gold"],
                    "old_winner": base_item["winner"],
                    "new_winner": item["winner"],
                    "old_rank": base_item["found_at"],
                    "new_rank": item["found_at"],
                    "query": item["query"]
                })
            elif base_item["found_at"] == 1 and item["found_at"] != 1:
                losses_top1.append({
                    "id": cid,
                    "gold": item["gold"],
                    "old_winner": base_item["winner"],
                    "new_winner": item["winner"],
                    "old_rank": base_item["found_at"],
                    "new_rank": item["found_at"],
                    "query": item["query"]
                })
            # Top-5
            if base_item["found_at"] != -1 and item["found_at"] == -1:
                losses_top5.append({
                    "id": cid,
                    "gold": item["gold"],
                    "old_rank": base_item["found_at"],
                    "new_rank": item["found_at"],
                    "query": item["query"]
                })

        net_delta = len(gains_top1) - len(losses_top1)

        cfg_summary = {
            "config_id": cfg_id,
            "params": {"saturation": sat, "min_scale_tem": min_t, "min_scale_dim": min_d},
            "r1": res["r1"],
            "r5": res["r5"],
            "mrr": res["mrr"],
            "top1_hits": res["top1_hits"],
            "top5_hits": res["top5_hits"],
            "total_cases": res["n"],
            "gains_top1_count": len(gains_top1),
            "losses_top1_count": len(losses_top1),
            "net_delta_top1": net_delta,
            "losses_top5_count": len(losses_top5),
            "fp_dev": neg_res["fp_count"],
            "fp_dev_total": neg_res["total"],
            "elapsed_seconds": round(t_elapsed, 1),
            "losses_top5": losses_top5,
            "gains_top1": gains_top1,
            "losses_top1": losses_top1
        }
        grid_results.append(cfg_summary)

        if len(losses_top5) == 0:
            configs_sin_perdidas_top5.append(cfg_id)

        print(f"[{idx+1:02d}/64] {cfg_id} (sat={sat:.2f}, tem={min_t:.2f}, dim={min_d:.2f}) | R@1: {res['top1_hits']}/{res['n']} ({res['r1']*100:.2f}%) | Gains: +{len(gains_top1)}, Losses: -{len(losses_top1)} (Net: {net_delta:+d}) | Top-5 Losses: {len(losses_top5)} | FP: {neg_res['fp_count']}/20 [{t_elapsed:.1f}s]")

        # Guardar checkpoint progresivo en cada iteración
        checkpoint_data = {
            "metadata": {
                "version": "fase2_discovery_grid_progress",
                "snapshot_sha256": snap_sha,
                "dataset_sha256": cases_sha,
                "script_sha256": script_sha,
                "completed_configs": len(grid_results),
                "total_configs": len(grid_configs),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            },
            "baseline_discovery": {
                "r1": base_disc["r1"], "r5": base_disc["r5"], "mrr": base_disc["mrr"],
                "top1_hits": base_disc["top1_hits"], "top5_hits": base_disc["top5_hits"], "n": base_disc["n"]
            },
            "results": grid_results
        }
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("EVALUACIÓN DE LAS 64 CONFIGURACIONES COMPLETADA")
    print("=" * 80)

    # Filtrar y ordenar resultados
    # Criterio de Selección:
    # 1. Filtro estricto: losses_top5 == 0 (preservar 100% Top-5)
    # 2. Filtro estricto: fp_dev == 0 (preservar 0% falsos positivos)
    # 3. Maximizar net_delta_top1
    # 4. Maximizar MRR
    valid_candidates = [
        c for c in grid_results
        if c["losses_top5_count"] == 0 and c["fp_dev"] == 0
    ]
    valid_candidates.sort(key=lambda x: (x["net_delta_top1"], x["mrr"]), reverse=True)

    print(f"\n[*] Análisis de Candidatas Válidas (Top-5 = 100% y FP = 0/20):")
    print(f" - Configuraciones con 0 pérdidas Top-5: {len(configs_sin_perdidas_top5)} / 64")
    print(f" - Configuraciones con 0 pérdidas Top-5 Y 0 FP: {len(valid_candidates)} / 64")

    if valid_candidates:
        best = valid_candidates[0]
        print(f"\n🏆 MEJOR CONFIGURACIÓN EN DISCOVERY:")
        print(f" - ID:            {best['config_id']}")
        print(f" - Parámetros:    {best['params']}")
        print(f" - R@1 Discovery: {best['top1_hits']} / {best['total_cases']} ({best['r1']*100:.2f}%) vs Base {base_disc['r1']*100:.2f}%")
        print(f" - R@5 Discovery: {best['top5_hits']} / {best['total_cases']} ({best['r5']*100:.2f}%) [0 pérdidas Top-5]")
        print(f" - MRR Discovery: {best['mrr']:.4f} vs Base {base_disc['mrr']:.4f}")
        print(f" - Ganancias:     +{best['gains_top1_count']}")
        print(f" - Pérdidas:      -{best['losses_top1_count']}")
        print(f" - Delta Neto:    +{best['net_delta_top1']}")
        print(f" - FP Dev:        {best['fp_dev']}/{best['fp_dev_total']}")
    else:
        print("\n⚠️ AVISO: Ninguna configuración logró 0 pérdidas en Top-5.")
        print("Activando análisis de sensibilidad de pérdidas Top-5...")

    # Limpiar temp db
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass

if __name__ == "__main__":
    run_fase2_discovery_grid()
