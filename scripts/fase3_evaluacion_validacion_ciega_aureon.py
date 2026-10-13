#!/usr/bin/env python3
"""
scripts/fase3_evaluacion_validacion_ciega_aureon.py
=============================================================================
Fase 3: Evaluación Ciega Confirmatoria en Validación (Plan Top-1 v4.1).

Aprobado formalmente por Aureon:
1. Configuración candidata congelada y autorizada:
   CFG_12 = {"saturation": 0.30, "min_scale_tem": 0.75, "min_scale_dim": 1.00}
2. Alcance: EXCLUSIVAMENTE sobre la partición de Validación (433 casos) y los
   20 controles negativos reservados deterministas.
3. Criterios de aceptación fijados PRE-ejecución:
   - Cero pérdidas en Top-5 frente al baseline en Validación (R@5 = 100%).
   - Mejora neta Top-1 positiva como objetivo de confirmación (net_delta > 0).
   - Cero falsos positivos en los 20 controles negativos reservados (0/20 FP).
4. Controles reservados: evaluados una sola vez con CFG_12 activa, registrando
   total_candidates, gate_calls y resultado individual por consulta.
5. Cero modificaciones a core/.
6. Evaluación única: sin segundas pasadas, sin ajuste de umbrales ni tuning
   sobre los resultados de Validación.
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
FASE1_V2_FILE = os.path.join(BASE_DIR, "docs", "fase1_diagnostico_72_misses_v2.json")
SEED = "biorag_split_seed_20261008_deterministic"

# Parámetros congelados de CFG_12
CFG_12_PARAMS = {
    "saturation": 0.30,
    "min_scale_tem": 0.75,
    "min_scale_dim": 1.00
}

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

def get_deterministic_validation_and_reserved_splits(retrieval_cases, neg_cases):
    # Cargar los 72 misses verificados del Baseline A para reconstruir exactamente los estratos
    with open(FASE1_V2_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    miss_ids = set(m["case_id"] for m in d["misses"])

    strata = defaultdict(list)
    for c in retrieval_cases:
        cid = c["id"]
        cat = c["categoria"]
        is_hit = cid not in miss_ids
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

    return validation, neg_reserved

def setup_fresh_temp_db():
    temp_db = f"/tmp/biorag_validation_blind_{os.getpid()}_{int(time.time()*1000)}.db"
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

class ValidationBlindHarness:
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

def make_cfg12_gate_fn():
    sat = CFG_12_PARAMS["saturation"]
    min_t = CFG_12_PARAMS["min_scale_tem"]
    min_d = CFG_12_PARAMS["min_scale_dim"]

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

def run_fase3_validacion_ciega():
    print("=" * 80)
    print("FASE 3: EVALUACIÓN CIEGA CONFIRMATORIA EN VALIDACIÓN (PLAN v4.1)")
    print("=" * 80)

    snap_sha = sha256_file(SNAPSHOT_PATH)
    cases_sha = sha256_file(CASES_FILE)
    script_sha = sha256_file(os.path.abspath(__file__))
    print(f"[*] Snapshot SHA-256: {snap_sha}")
    print(f"[*] Dataset SHA-256:  {cases_sha}")
    print(f"[*] Script SHA-256:   {script_sha}")

    temp_db = setup_fresh_temp_db()
    cases = load_cases()
    harness = ValidationBlindHarness(temp_db, cases)

    retrieval_cases = [
        c for c in cases
        if c.get("concepto_esperado") and c["query"].strip().lower() not in harness.queries_ambiguas
    ]
    neg_cases = [c for c in cases if c.get("concepto_esperado") is None or c.get("categoria") == "negativo"]

    validation_cases, neg_reserved = get_deterministic_validation_and_reserved_splits(retrieval_cases, neg_cases)

    print(f"\n[*] Partición de Validación Cargada:")
    print(f" - Casos de Validación:         {len(validation_cases)} casos")
    print(f" - Controles Negativos Reservados: {len(neg_reserved)} casos")
    print(f" - Configuración Evaluada:      CFG_12 {CFG_12_PARAMS}")

    # 1. EVALUAR BASELINE EN VALIDACIÓN (433 casos)
    print("\n" + "-" * 80)
    print("[1/3] Ejecutando Baseline Oficial en Validación (433 casos)...")
    print("-" * 80)
    t0_base = time.time()
    base_val = harness.execute_eval(gate_fn=None, target_cases=validation_cases)
    t_base = time.time() - t0_base

    print(f"Resultados Baseline en Validación:")
    print(f" - Top-1 Hits: {base_val['top1_hits']} / {base_val['n']} ({base_val['r1']*100:.2f}%)")
    print(f" - Top-5 Hits: {base_val['top5_hits']} / {base_val['n']} ({base_val['r5']*100:.2f}%)")
    print(f" - MRR:        {base_val['mrr']:.4f}")
    print(f" - Tiempo:     {t_base:.1f} s")

    # Baseline en controles reservados (referencia)
    neg_base_res = harness.eval_negatives_con_intervencion(neg_reserved, gate_fn=None)
    print(f" - FP Controles Reservados (Baseline): {neg_base_res['fp_count']} / {neg_base_res['total']}")

    # 2. EVALUAR CFG_12 EN VALIDACIÓN (433 casos)
    print("\n" + "-" * 80)
    print("[2/3] Ejecutando CFG_12 en Validación (433 casos) — Evaluación Única Ciega...")
    print("-" * 80)
    gate_cfg12 = make_cfg12_gate_fn()
    t0_val = time.time()
    cfg12_val = harness.execute_eval(gate_fn=gate_cfg12, target_cases=validation_cases)
    t_val = time.time() - t0_val

    # Calcular transiciones por caso
    val_gains = []
    val_losses = []
    val_top5_losses = []

    for cid, item in cfg12_val["results_map"].items():
        base_item = base_val["results_map"][cid]
        # Top-1 transitions
        if base_item["found_at"] != 1 and item["found_at"] == 1:
            val_gains.append({
                "id": cid,
                "gold": item["gold"],
                "old_winner": base_item["winner"],
                "new_winner": item["winner"],
                "old_rank": base_item["found_at"],
                "new_rank": item["found_at"],
                "query": item["query"]
            })
        elif base_item["found_at"] == 1 and item["found_at"] != 1:
            val_losses.append({
                "id": cid,
                "gold": item["gold"],
                "old_winner": base_item["winner"],
                "new_winner": item["winner"],
                "old_rank": base_item["found_at"],
                "new_rank": item["found_at"],
                "query": item["query"]
            })
        # Top-5 transitions
        if base_item["found_at"] != -1 and item["found_at"] == -1:
            val_top5_losses.append({
                "id": cid,
                "gold": item["gold"],
                "old_rank": base_item["found_at"],
                "new_rank": item["found_at"],
                "query": item["query"]
            })

    net_delta_val = len(val_gains) - len(val_losses)

    print(f"Resultados CFG_12 en Validación:")
    print(f" - Top-1 Hits:   {cfg12_val['top1_hits']} / {cfg12_val['n']} ({cfg12_val['r1']*100:.2f}%) vs Base {base_val['r1']*100:.2f}%")
    print(f" - Top-5 Hits:   {cfg12_val['top5_hits']} / {cfg12_val['n']} ({cfg12_val['r5']*100:.2f}%) vs Base {base_val['r5']*100:.2f}%")
    print(f" - MRR:          {cfg12_val['mrr']:.4f} vs Base {base_val['mrr']:.4f}")
    print(f" - Ganancias:    +{len(val_gains)}")
    print(f" - Pérdidas:     -{len(val_losses)}")
    print(f" - Delta Neto:   {net_delta_val:+d}")
    print(f" - Pérdidas T5:  {len(val_top5_losses)}")
    print(f" - Tiempo:       {t_val:.1f} s")

    # 3. EVALUAR CONTROLES NEGATIVOS RESERVADOS CON CFG_12
    print("\n" + "-" * 80)
    print("[3/3] Evaluando los 20 Controles Negativos Reservados con CFG_12...")
    print("-" * 80)
    neg_cfg12_res = harness.eval_negatives_con_intervencion(neg_reserved, gate_fn=gate_cfg12)
    print(f"Resultados Controles Negativos Reservados con CFG_12:")
    print(f" - Falsos Positivos:  {neg_cfg12_res['fp_count']} / {neg_cfg12_res['total']}")
    print(f" - Invocaciones Gate: {neg_cfg12_res['gate_calls']}")

    # Contar controles con y sin candidatos
    con_candidatos = [d for d in neg_cfg12_res["details"] if d["total_candidates"] > 0]
    sin_candidatos = [d for d in neg_cfg12_res["details"] if d["total_candidates"] == 0]
    print(f" - Controles sin candidatos (OOV): {len(sin_candidatos)} / 20")
    print(f" - Controles con candidatos:       {len(con_candidatos)} / 20")

    # 4. VEREDICTO FORMAL CONTRA CRITERIOS PRE-FIJADOS
    print("\n" + "=" * 80)
    print("VEREDICTO DE LA EVALUACIÓN CIEGA EN VALIDACIÓN")
    print("=" * 80)

    pasa_top5 = (len(val_top5_losses) == 0 and cfg12_val["r5"] >= base_val["r5"])
    pasa_fp = (neg_cfg12_res["fp_count"] == 0)
    pasa_top1 = (net_delta_val > 0)

    print(f"1. Cero pérdidas Top-5 (R@5 = 100%): {'✅ CUMPLIDO' if pasa_top5 else '❌ FALLIDO'} ({len(val_top5_losses)} pérdidas)")
    print(f"2. Mejora neta Top-1 (net_delta > 0): {'✅ CUMPLIDO' if pasa_top1 else '❌ NO ALCANZADO'} (Net: {net_delta_val:+d})")
    print(f"3. Cero Falsos Positivos (0/20 FP):   {'✅ CUMPLIDO' if pasa_fp else '❌ FALLIDO'} ({neg_cfg12_res['fp_count']} FP)")

    decision_final = "CONFIRMADA" if (pasa_top5 and pasa_fp and pasa_top1) else "NO_CONFIRMADA"
    print(f"\nResultado Global de Validación: {decision_final}")

    # Guardar reporte JSON
    reporte_validacion = {
        "metadata": {
            "version": "fase3_validacion_ciega_confirmatoria",
            "decision": decision_final,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "snapshot_sha256": snap_sha,
            "dataset_sha256": cases_sha,
            "script_sha256": script_sha,
            "config_evaluada": {
                "id": "CFG_12",
                "params": CFG_12_PARAMS
            }
        },
        "criterios_aceptacion_prefijados": {
            "cero_perdidas_top5": {"cumplido": pasa_top5, "perdidas_top5": len(val_top5_losses)},
            "mejora_neta_top1": {"cumplido": pasa_top1, "net_delta": net_delta_val},
            "cero_falsos_positivos_reservados": {"cumplido": pasa_fp, "fp_count": neg_cfg12_res["fp_count"]}
        },
        "baseline_validacion": {
            "n": base_val["n"],
            "top1_hits": base_val["top1_hits"],
            "top5_hits": base_val["top5_hits"],
            "r1": base_val["r1"],
            "r5": base_val["r5"],
            "mrr": base_val["mrr"],
            "elapsed_seconds": round(t_base, 1)
        },
        "cfg12_validacion": {
            "n": cfg12_val["n"],
            "top1_hits": cfg12_val["top1_hits"],
            "top5_hits": cfg12_val["top5_hits"],
            "r1": cfg12_val["r1"],
            "r5": cfg12_val["r5"],
            "mrr": cfg12_val["mrr"],
            "gains_count": len(val_gains),
            "losses_count": len(val_losses),
            "net_delta": net_delta_val,
            "losses_top5_count": len(val_top5_losses),
            "elapsed_seconds": round(t_val, 1),
            "gains": val_gains,
            "losses": val_losses,
            "top5_losses": val_top5_losses
        },
        "controles_negativos_reservados": {
            "total": neg_cfg12_res["total"],
            "fp_count": neg_cfg12_res["fp_count"],
            "gate_calls": neg_cfg12_res["gate_calls"],
            "sin_candidatos_oov_count": len(sin_candidatos),
            "con_candidatos_count": len(con_candidatos),
            "details": neg_cfg12_res["details"]
        }
    }

    report_path = os.path.join(BASE_DIR, "docs", "fase3_validacion_ciega_reporte.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(reporte_validacion, f, indent=2, ensure_ascii=False)
    print(f"\n[*] Reporte completo guardado en: {report_path}")

    # Limpiar temp db
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass

if __name__ == "__main__":
    run_fase3_validacion_ciega()
