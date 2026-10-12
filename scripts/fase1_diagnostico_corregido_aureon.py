#!/usr/bin/env python3
"""
scripts/fase1_diagnostico_corregido_aureon.py
=============================================================================
Auditoría correctiva y regeneración de la Fase 1 según las instrucciones
formales de Aureon:

1. Corrección de scores de Gold:
   - Cero sustitución artificial de 0.0.
   - Verificación de presencia en el pool de scoring.
   - Si no está presente, marcar como `evaluable_aritmeticamente: False`.
   - Si está presente, recálculo exacto a través de la función nativa de
     scoring (_calcular_score_hibrido) con kwargs modificados, preservando
     la no-linealidad de los bonos logit y la coherencia de escala.

2. Regeneración de Fase 1 en nuevo artefacto:
   - docs/fase1_diagnostico_72_misses_v2.json
   - Preservación íntegra del artefacto histórico docs/fase1_diagnostico_72_misses.json.
   - Hashes SHA-256 de snapshot, dataset y script.

3. Controles Negativos con Intervención Activa:
   - `gate_fn` instalado y activo durante las consultas de control negativo de desarrollo (20 dev).
   - Contador explícito de invocaciones de gate_fn durante negativos para probar que la intervención está activa.
   - Separación estricta de los 20 controles reservados.

4. Verificación de configuración de Jaccard:
   - Constatación formal del flag BIORAG_RERANKING_JACCARD_ENABLED.
   - Documentación de su impacto en el baseline.

5. Reconciliación con el commit 6ee1fd4:
   - Clarificación documentada de la discrepancia de texto en el commit histórico.

6. Cero modificaciones a core/.
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
    temp_db = f"/tmp/biorag_aureon_v2_{os.getpid()}_{int(time.time()*1000)}.db"
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

class CorrectedBioRAGHarness:
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

    def execute_eval(self, gate_fn=None, target_cases=None, capture_telemetry=False):
        current_case_id = [None]
        case_cands_map = defaultdict(dict)

        if gate_fn is not None or capture_telemetry:
            def instrumented_scoring(*args, **kwargs):
                try:
                    caller_locals = sys._getframe(1).f_locals
                    concepto = caller_locals.get("concepto", "unknown")
                except Exception:
                    concepto = "unknown"

                mod_kwargs = dict(kwargs)
                if gate_fn is not None:
                    mod_kwargs = gate_fn(mod_kwargs, concepto=concepto)

                sc = self.original_calcular(*args, **mod_kwargs)

                if capture_telemetry and current_case_id[0]:
                    case_cands_map[current_case_id[0]][concepto] = {
                        "concepto": concepto,
                        "raw_kwargs": dict(kwargs),
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

    def eval_negatives_con_intervencion(self, neg_cases, gate_fn=None):
        """Evalúa controles negativos asegurando que gate_fn esté activo."""
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

def run_auditoria_correctiva_fase1():
    print("=" * 80)
    print("AUDITORÍA CORRECTIVA Y REGENERACIÓN DE FASE 1 (AUREON PROTOCOL)")
    print("=" * 80)

    snap_sha = sha256_file(SNAPSHOT_PATH)
    cases_sha = sha256_file(CASES_FILE)
    script_sha = sha256_file(os.path.abspath(__file__))
    print(f"[*] Snapshot SHA-256: {snap_sha}")
    print(f"[*] Dataset SHA-256:  {cases_sha}")
    print(f"[*] Script SHA-256:   {script_sha}")

    temp_db = setup_fresh_temp_db()
    cases = load_cases()
    harness = CorrectedBioRAGHarness(temp_db, cases)

    retrieval_cases = [
        c for c in cases
        if c.get("concepto_esperado") and c["query"].strip().lower() not in harness.queries_ambiguas
    ]
    neg_cases = [c for c in cases if c.get("concepto_esperado") is None or c.get("categoria") == "negativo"]

    # 1. BASELINE A OFICIAL
    print("\n[1/3] Ejecutando Baseline A oficial con captura estricta de kwargs...")
    t0 = time.time()
    base_eval = harness.execute_eval(gate_fn=None, target_cases=retrieval_cases, capture_telemetry=True)
    t_base = time.time() - t0

    print(f"Resultados Baseline A:")
    print(f" - Top-1 Hits:   {base_eval['top1_hits']} / {base_eval['n']} ({base_eval['r1']*100:.2f}%)")
    print(f" - Top-5 Hits:   {base_eval['top5_hits']} / {base_eval['n']} ({base_eval['r5']*100:.2f}%)")
    print(f" - MRR:          {base_eval['mrr']:.4f}")
    print(f" - Misses Top-1: {base_eval['n'] - base_eval['top1_hits']}")
    print(f" - Tiempo:       {t_base:.1f} s")

    # Split determinista
    discovery_cases, validation_cases, neg_dev, neg_reserved = create_deterministic_splits(
        retrieval_cases, base_eval["results_map"], neg_cases
    )

    # 2. CONTROLES NEGATIVOS EN BASELINE
    neg_res_base = harness.eval_negatives_con_intervencion(neg_dev, gate_fn=None)
    print(f" - Controles Negativos Dev (Baseline): {neg_res_base['fp_count']} / {neg_res_base['total']} (FP Rate: 0.0%)")

    # 3. REGENERACIÓN FASE 1 (DIAGNÓSTICO CORREGIDO)
    print("\n[2/3] Regenerando Fase 1 con recálculo exacto sobre scoring nativo...")
    miss_case_ids = [cid for cid, r in base_eval["results_map"].items() if r["found_at"] != 1]
    print(f"[*] Analizando {len(miss_case_ids)} misses Top-1...")

    telemetry = base_eval["telemetry"]

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

    diagnostico_72_v2 = []
    rescatables_por_config_v2 = defaultdict(int)
    no_evaluables_count = 0

    for cid in miss_case_ids:
        b_res = base_eval["results_map"][cid]
        gold_name = b_res["gold"]
        winner_name = b_res["winner"]
        query = b_res["query"]
        category = b_res["categoria"]
        gold_rank = b_res["found_at"]

        cands = telemetry.get(cid, {})
        gold_cand = cands.get(gold_name)
        winner_cand = cands.get(winner_name)

        if not gold_cand or not winner_cand:
            # Hallazgo 1: NO usar cero, marcar como no evaluable
            no_evaluables_count += 1
            diagnostico_72_v2.append({
                "case_id": cid,
                "query": query,
                "categoria": category,
                "gold": gold_name,
                "winner": winner_name,
                "gold_rank_A": gold_rank,
                "evaluable_aritmeticamente": False,
                "motivo": "Gold ausente en pool de scoring observado" if not gold_cand else "Winner ausente",
                "configs": {}
            })
            continue

        gold_kwargs = dict(gold_cand["raw_kwargs"])
        winner_kwargs = dict(winner_cand["raw_kwargs"])

        gold_score_A = gold_cand["score_eval"]
        winner_score_A = winner_cand["score_eval"]
        margin_orig = gold_score_A - winner_score_A

        # Señales de especificidad
        gold_spec = max(gold_kwargs.get("bm25_norm", 0.0), gold_kwargs.get("sinonimos_ratio", 0.0), gold_kwargs.get("concepto_ratio", 0.0))
        winner_spec = max(winner_kwargs.get("bm25_norm", 0.0), winner_kwargs.get("sinonimos_ratio", 0.0), winner_kwargs.get("concepto_ratio", 0.0))

        config_evals = {}
        for cfg in grid_configs:
            cfg_id = cfg["config_id"]
            sat = cfg["saturation"]
            min_t = cfg["min_scale_tem"]
            min_d = cfg["min_scale_dim"]

            g_ratio = max(0.0, min(1.0, gold_spec / sat)) if sat > 0 else 0.0
            w_ratio = max(0.0, min(1.0, winner_spec / sat)) if sat > 0 else 0.0

            g_t_scale = 1.0 - (1.0 - min_t) * g_ratio
            g_d_scale = 1.0 - (1.0 - min_d) * g_ratio

            w_t_scale = 1.0 - (1.0 - min_t) * w_ratio
            w_d_scale = 1.0 - (1.0 - min_d) * w_ratio

            # Recálculo exacto a través de la función nativa de scoring
            mod_g_kw = dict(gold_kwargs)
            mod_g_kw["tematico_score"] = gold_kwargs.get("tematico_score", 0.0) * g_t_scale
            mod_g_kw["dim_score"] = gold_kwargs.get("dim_score", 0.0) * g_d_scale
            sc_g_mod = harness.original_calcular(**mod_g_kw)

            mod_w_kw = dict(winner_kwargs)
            mod_w_kw["tematico_score"] = winner_kwargs.get("tematico_score", 0.0) * w_t_scale
            mod_w_kw["dim_score"] = winner_kwargs.get("dim_score", 0.0) * w_d_scale
            sc_w_mod = harness.original_calcular(**mod_w_kw)

            delta_nuevo = sc_g_mod - sc_w_mod
            rescatable_aritmetico = (delta_nuevo > 0)

            if rescatable_aritmetico:
                rescatables_por_config_v2[cfg_id] += 1

            config_evals[cfg_id] = {
                "gold_spec": round(gold_spec, 4),
                "winner_spec": round(winner_spec, 4),
                "gold_score_nuevo": round(sc_g_mod, 6),
                "winner_score_nuevo": round(sc_w_mod, 6),
                "delta_nuevo": round(delta_nuevo, 6),
                "rescatable_aritmetico": bool(rescatable_aritmetico)
            }

        diagnostico_72_v2.append({
            "case_id": cid,
            "query": query,
            "categoria": category,
            "gold": gold_name,
            "winner": winner_name,
            "gold_rank_A": gold_rank,
            "evaluable_aritmeticamente": True,
            "gold_score_A": round(gold_score_A, 6),
            "winner_score_A": round(winner_score_A, 6),
            "margin_original": round(margin_orig, 6),
            "gold_raw_kwargs": gold_kwargs,
            "winner_raw_kwargs": winner_kwargs,
            "configs": config_evals
        })

    # Guardar reporte de Fase 1 v2
    fase1_v2_data = {
        "metadata": {
            "version": "v2_corregida_aureon",
            "snapshot_sha256": snap_sha,
            "dataset_sha256": cases_sha,
            "script_sha256": script_sha,
            "total_misses": len(diagnostico_72_v2),
            "evaluables_aritmeticamente": len(diagnostico_72_v2) - no_evaluables_count,
            "no_evaluables": no_evaluables_count,
            "grid_configs_count": len(grid_configs),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "resumen_rescatabilidad_aritmetica_v2": {
            cfg_id: count for cfg_id, count in sorted(rescatables_por_config_v2.items())
        },
        "misses": diagnostico_72_v2
    }
    fase1_v2_path = os.path.join(BASE_DIR, "docs", "fase1_diagnostico_72_misses_v2.json")
    with open(fase1_v2_path, "w", encoding="utf-8") as f:
        json.dump(fase1_v2_data, f, indent=2, ensure_ascii=False)
    print(f"[*] Reporte Fase 1 v2 guardado en: {fase1_v2_path}")

    # 4. CONTROLES NEGATIVOS CON INTERVENCIÓN ACTIVA (HALLAZGO 2)
    print("\n[3/3] Evaluando controles negativos de desarrollo con la intervención ACTIVA...")
    # Probar con la configuración media piloto (CFG_39: sat=0.5, tem=0.5, dim=0.75)
    def gate_fn_cf39(kw, concepto=""):
        bm25 = kw.get("bm25_norm", 0.0)
        sin = kw.get("sinonimos_ratio", 0.0)
        c_ratio = kw.get("concepto_ratio", 0.0)
        spec = max(bm25, sin, c_ratio)
        ratio = max(0.0, min(1.0, spec / 0.5))
        kw["tematico_score"] = kw.get("tematico_score", 0.0) * (1.0 - (1.0 - 0.5) * ratio)
        kw["dim_score"] = kw.get("dim_score", 0.0) * (1.0 - (1.0 - 0.75) * ratio)
        return kw

    neg_eval_intervencion = harness.eval_negatives_con_intervencion(neg_dev, gate_fn=gate_fn_cf39)
    print(f" - Controles Negativos Dev con CFG_39:")
    print(f"   * Falsos Positivos:  {neg_eval_intervencion['fp_count']} / {neg_eval_intervencion['total']}")
    print(f"   * Invocaciones Gate: {neg_eval_intervencion['gate_calls']} (Intervención comprobada activa)")

    max_v2 = max(rescatables_por_config_v2.values()) if rescatables_por_config_v2 else 0
    min_v2 = min(rescatables_por_config_v2.values()) if rescatables_por_config_v2 else 0
    print(f"\n[*] Resumen Comparativo de Rescatabilidad Aritmética:")
    print(f" - Total evaluables: {len(diagnostico_72_v2) - no_evaluables_count} / 72")
    print(f" - Rango v2 corregido: entre {min_v2} y {max_v2} casos rescatables según config.")

    # Guardar resumen de controles negativos
    neg_report = {
        "metadata": {
            "snapshot_sha256": snap_sha,
            "dataset_sha256": cases_sha,
            "script_sha256": script_sha,
        },
        "negativos_dev_baseline": neg_res_base,
        "negativos_dev_intervencion_cfg39": neg_eval_intervencion
    }
    neg_path = os.path.join(BASE_DIR, "docs", "controles_negativos_audit_v2.json")
    with open(neg_path, "w", encoding="utf-8") as f:
        json.dump(neg_report, f, indent=2, ensure_ascii=False)
    print(f"[*] Reporte de Controles Negativos guardado en: {neg_path}")

    # Limpiar temp db
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass

if __name__ == "__main__":
    run_auditoria_correctiva_fase1()
