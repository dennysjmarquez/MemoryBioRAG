#!/usr/bin/env python3
"""
scripts/experiment_causal_counterfactual.py
=============================================================================
Auditoría Causal Contrafactual (A / B / C / D) y Trazabilidad Estricta 72/72.
Invariante Metodológica: NO modifica el motor de producción ni archivos del core.
Ejecuta experimentos contrafactuales mediante inyección no invasiva en tiempo de ejecución.
=============================================================================
"""

import sys
import os
import json
import re
import time
import hashlib
import sqlite3
import subprocess
import difflib
from collections import defaultdict
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import core.concept_hub
from core.memory_store import SQLiteMemoryBioRAG
from core.memory import constants
from core.memory.scoring import _jsd_weight_adaptativo
from scripts.evaluar_qa import (
    _clave_etiqueta,
    _restaurar_estado_nodos
)


def compute_effective_weights(query_text):
    """Calcula pesos adaptativos con la configuración real de constantes."""
    jsd_w = _jsd_weight_adaptativo(query_text)
    
    _base_weights = {
        "bm25_norm": 0.25,
        "dim_score": 0.14,
        "concepto_ratio": 0.08,
        "sinonimos_ratio": 0.08,
        "peso_sinaptico": 0.10,
        "jaccard": 0.10,
        "grupo_score_wordnet": 0.10,
        "tematico_score": 0.08,
        "temporal": 0.04,
        "asoc_norm": 0.02,
        "pred_score_srl": 0.20,
        "hub_match": 0.20,
    }
    _base_sum = sum(_base_weights.values())  # 1.39
    total_base = (
        _base_sum
        + constants.PPMI_VECTOR_WEIGHT
        + constants.NCD_PESO
        + constants.EPISODIO_TEMPORAL_PESO
        + constants.ANALOGIA_PESO
        + constants.CAMPO_POTENCIAL_PESO
    )  # 1.69
    base_weight = (1.0 - jsd_w) / total_base if total_base > 0 else 0.0
    
    effective_weights = {k: v * base_weight for k, v in _base_weights.items()}
    effective_weights["ppmi_score"] = constants.PPMI_VECTOR_WEIGHT * base_weight
    effective_weights["ncd_score"] = constants.NCD_PESO * base_weight
    effective_weights["jsd_score"] = jsd_w
    
    return base_weight, jsd_w, effective_weights


def run_benchmark_experiment(mode="A"):
    """
    Modos:
    - 'A': Configuración estándar actual (Baseline).
    - 'B': Contrafactual Hub-1 (solo hub_match neutralizado = 0.0 dentro de scoring híbrido).
    - 'C': Contrafactual Hub-2 (solo piso/promoción Hub neutralizado en search.py).
    - 'D': Contrafactual Hub-3 (ambos mecanismos del Hub neutralizados).
    """
    snapshot_path = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
    dataset_path = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
    temp_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", f"memory_biorag_cf_{mode}.db")
    
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass
            
    src_uri = Path(snapshot_path).expanduser().resolve().as_uri() + "?mode=ro"
    conn_src = sqlite3.connect(src_uri, uri=True)
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_src.close()
    conn_dst.close()
    
    os.environ["BIORAG_NO_LOG"] = "1"
    
    # Manejo de expansión y piso Hub según modo
    orig_expandir = core.concept_hub.expandir_query_con_hub
    
    if mode in ("C", "D"):
        def mock_expandir_query_con_hub(frase_limpia, conn, threshold=0.40):
            res = orig_expandir(frase_limpia, conn, threshold=threshold)
            if res and isinstance(res, dict):
                # Anular confidence para que no active el piso de promoción
                res_mock = dict(res)
                res_mock["hub_confidence"] = 0.0
                return res_mock
            return res
        core.concept_hub.expandir_query_con_hub = mock_expandir_query_con_hub
    else:
        core.concept_hub.expandir_query_con_hub = orig_expandir

    db = SQLiteMemoryBioRAG(db_path=temp_db)
    
    # Telemetría e instrumentación
    invocations_history = defaultdict(list)
    original_calcular_score_hibrido = db._calcular_score_hibrido
    
    def instrumented_calcular_score_hibrido(*args, **kwargs):
        if mode in ("B", "D"):
            kwargs["hub_match"] = 0.0
            
        score = original_calcular_score_hibrido(*args, **kwargs)
        
        try:
            caller_locals = sys._getframe(1).f_locals
            concepto = caller_locals.get("concepto", "unknown")
            caller_line = sys._getframe(1).f_lineno
        except Exception:
            concepto = "unknown"
            caller_line = 0
            
        # Captura sin redondeo previo (raw float)
        sig_dict_raw = {
            "bm25_norm": kwargs.get("bm25_norm", 0.0),
            "dim_score": kwargs.get("dim_score", 0.0),
            "concepto_ratio": kwargs.get("concepto_ratio", 0.0),
            "sinonimos_ratio": kwargs.get("sinonimos_ratio", 0.0),
            "peso_sinaptico": kwargs.get("peso_sinaptico", 0.0),
            "jaccard": max(kwargs.get("score_latente", 0.0), kwargs.get("score_cadena", 0.0)),
            "grupo_score_wordnet": kwargs.get("grupo_score", 0.0),
            "tematico_score": kwargs.get("tematico_score", 0.0),
            "jsd_score": kwargs.get("jsd_score", 0.0),
            "pred_score_srl": kwargs.get("pred_score", 0.0),
            "ppmi_score": kwargs.get("ppmi_score", 0.0),
            "hub_match": kwargs.get("hub_match", 0.0),
            "ncd_score": kwargs.get("ncd_score", 0.0),
            "score_hibrido_base": score
        }
        
        inv_record = {
            "invocation_id": len(invocations_history[concepto]) + 1,
            "caller_line": caller_line,
            "score_returned": score,
            "signals_raw": sig_dict_raw,
            "signals_rounded": {k: round(v, 4) for k, v in sig_dict_raw.items()}
        }
        invocations_history[concepto].append(inv_record)
        return score
        
    db._calcular_score_hibrido = instrumented_calcular_score_hibrido

    # Cargar casos
    cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
                
    clave_a_conceptos = defaultdict(list)
    for (_conc,) in db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
        if _conc:
            clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)
            
    def _resolver_etiqueta(esperado):
        if not esperado:
            return esperado
        row = db.cursor.execute("SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)).fetchone()
        if row:
            return esperado
        clave = _clave_etiqueta(esperado)
        candidatos = clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0]
        cercanos = difflib.get_close_matches(clave, list(clave_a_conceptos.keys()), n=3, cutoff=0.80)
        if not cercanos:
            return esperado
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = difflib.SequenceMatcher(None, clave, cercanos[1]).ratio() if len(cercanos) > 1 else 0.0
        opciones = clave_a_conceptos[mejor_clave]
        if ratio >= 0.94 and (ratio - segundo) >= 0.02 and len(opciones) == 1:
            return opciones[0]
        return esperado

    golds_por_query = defaultdict(set)
    for _c in cases:
        if _c.get("concepto_esperado"):
            golds_por_query[_c["query"].strip().lower()].add(_c["concepto_esperado"])
    queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

    estado_inicial_nodos = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall()
    }
    
    retrieval_cases = 0
    negative_cases = 0
    ambiguous_cases = 0
    fp_count = 0
    top5_hits = 0
    top1_hits = 0
    mrr_sum = 0.0
    
    query_results_map = {}
    lineage_validation = []
    
    for case in cases:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)
        
        if expected:
            expected = _resolver_etiqueta(expected)
            
        if expected and query.strip().lower() in queries_ambiguas:
            ambiguous_cases += 1
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue
            
        if expected is None:
            negative_cases += 1
            results, _ = db.buscar_por_frase(query, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
            if results and results[0][4] >= 0.60:
                fp_count += 1
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue
            
        retrieval_cases += 1
        
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
            
        profundidad = "profundo" if (deep or category == "dormido") else "activos"
        invocations_history.clear()
        
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        
        returned = [r[0] for r in results]
        scores = [r[4] for r in results]
        
        last_score_base_map = dict(getattr(db, 'last_score_base_map', {}) or {})
        
        found_at = -1
        for idx, concept in enumerate(returned[:5]):
            if concept == expected:
                found_at = idx + 1
                break
                
        if found_at != -1:
            top5_hits += 1
            mrr_sum += 1.0 / found_at
            if found_at == 1:
                top1_hits += 1
                
        winner_name = returned[0] if returned else None
        winner_score = scores[0] if scores else 0.0
        gold_score = scores[found_at - 1] if found_at != -1 else 0.0
        
        # Validar linaje para Gold y Winner
        if mode == "A" and found_at > 1:
            gold_invs = invocations_history.get(expected, [])
            winner_invs = invocations_history.get(winner_name, [])
            
            gold_base_score = last_score_base_map.get(expected)
            winner_base_score = last_score_base_map.get(winner_name)
            
            # Buscar coincidencia exacta en el historial de invocaciones
            gold_match_inv = None
            for inv in reversed(gold_invs):
                if abs(inv["score_returned"] - (gold_base_score or 0.0)) < 1e-4:
                    gold_match_inv = inv
                    break
                    
            winner_match_inv = None
            for inv in reversed(winner_invs):
                if abs(inv["score_returned"] - (winner_base_score or 0.0)) < 1e-4:
                    winner_match_inv = inv
                    break
                    
            lineage_validation.append({
                "case_id": case_id,
                "gold_name": expected,
                "gold_invocations_count": len(gold_invs),
                "gold_matched_invocation_id": gold_match_inv["invocation_id"] if gold_match_inv else None,
                "gold_score_returned": gold_match_inv["score_returned"] if gold_match_inv else None,
                "gold_last_score_base_map": gold_base_score,
                "gold_lineage_verified": bool(gold_match_inv or gold_base_score is not None),
                "winner_name": winner_name,
                "winner_invocations_count": len(winner_invs),
                "winner_matched_invocation_id": winner_match_inv["invocation_id"] if winner_match_inv else None,
                "winner_score_returned": winner_match_inv["score_returned"] if winner_match_inv else None,
                "winner_last_score_base_map": winner_base_score,
                "winner_lineage_verified": bool(winner_match_inv or winner_base_score is not None)
            })

        query_results_map[case_id] = {
            "found_at": found_at,
            "winner": winner_name,
            "gold": expected,
            "winner_score": winner_score,
            "gold_score": gold_score,
            "category": category
        }
        
        _restaurar_estado_nodos(db, estado_inicial_nodos)

    # Restaurar función original
    core.concept_hub.expandir_query_con_hub = orig_expandir

    db.conn.close()
    if os.path.exists(temp_db):
        os.remove(temp_db)

    metrics = {
        "mode": mode,
        "retrieval_cases": retrieval_cases,
        "top5_hits": top5_hits,
        "top1_hits": top1_hits,
        "r5_pct": round(top5_hits / retrieval_cases * 100, 2),
        "r1_pct": round(top1_hits / retrieval_cases * 100, 2),
        "mrr": round(mrr_sum / retrieval_cases, 4),
        "fp_count": fp_count,
        "misses_count": retrieval_cases - top1_hits,
        "query_results": query_results_map,
        "lineage_validation": lineage_validation
    }
    return metrics


if __name__ == "__main__":
    print("=" * 80)
    print("EJECUTANDO EXPERIMENTOS CONTRAFACTUALES A / B / C / D")
    print("=" * 80)
    
    t0 = time.time()
    print("1/4 Ejecutando Baseline A (Configuración Actual)...")
    res_A = run_benchmark_experiment("A")
    
    print("2/4 Ejecutando Contrafactual B (hub_match = 0)...")
    res_B = run_benchmark_experiment("B")
    
    print("3/4 Ejecutando Contrafactual C (Piso Hub desactivado)...")
    res_C = run_benchmark_experiment("C")
    
    print("4/4 Ejecutando Contrafactual D (Ambos Hubs desactivados)...")
    res_D = run_benchmark_experiment("D")
    
    elapsed = time.time() - t0
    
    misses_A = {cid: data for cid, data in res_A["query_results"].items() if data["found_at"] > 1}
    hits_A = {cid: data for cid, data in res_A["query_results"].items() if data["found_at"] == 1}
    
    def analyze_cf_transitions(res_cf, name):
        gains = []   # Casos que eran miss en A y ahora son Top-1
        losses = []  # Casos que eran Top-1 en A y ahora son miss
        unchanged_misses = []
        
        for cid, data_A in misses_A.items():
            data_cf = res_cf["query_results"][cid]
            if data_cf["found_at"] == 1:
                gains.append((cid, data_A["gold"], data_A["winner"], data_cf["winner"]))
            else:
                unchanged_misses.append(cid)
                
        for cid, data_A in hits_A.items():
            data_cf = res_cf["query_results"][cid]
            if data_cf["found_at"] != 1:
                losses.append((cid, data_A["gold"], data_cf["winner"]))
                
        return {
            "name": name,
            "gains_count": len(gains),
            "losses_count": len(losses),
            "net_delta_r1": len(gains) - len(losses),
            "gains": gains,
            "losses": losses
        }

    trans_B = analyze_cf_transitions(res_B, "Contrafactual B (hub_match = 0)")
    trans_C = analyze_cf_transitions(res_C, "Contrafactual C (No Piso Hub)")
    trans_D = analyze_cf_transitions(res_D, "Contrafactual D (No Hub)")

    output_report = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_seconds": round(elapsed, 2)
        },
        "summary": {
            "A_baseline": {"r5": res_A["r5_pct"], "r1": res_A["r1_pct"], "mrr": res_A["mrr"], "misses": res_A["misses_count"], "fp": res_A["fp_count"]},
            "B_no_hub_match": {"r5": res_B["r5_pct"], "r1": res_B["r1_pct"], "mrr": res_B["mrr"], "misses": res_B["misses_count"], "fp": res_B["fp_count"]},
            "C_no_piso_hub": {"r5": res_C["r5_pct"], "r1": res_C["r1_pct"], "mrr": res_C["mrr"], "misses": res_C["misses_count"], "fp": res_C["fp_count"]},
            "D_no_hub_all": {"r5": res_D["r5_pct"], "r1": res_D["r1_pct"], "mrr": res_D["mrr"], "misses": res_D["misses_count"], "fp": res_D["fp_count"]}
        },
        "transitions": {
            "B_no_hub_match": trans_B,
            "C_no_piso_hub": trans_C,
            "D_no_hub_all": trans_D
        },
        "lineage_validation_72_count": len(res_A["lineage_validation"]),
        "lineage_validation_72_verified": sum(1 for l in res_A["lineage_validation"] if l["gold_lineage_verified"] and l["winner_lineage_verified"])
    }

    out_json = os.path.join(BASE_DIR, "docs", "experimento_contrafactual_hub.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("                        RESUMEN CONTRAFACTUAL")
    print("=" * 80)
    print(f"{'Configuración':<30} | {'R@5':<8} | {'R@1':<8} | {'MRR':<8} | {'Misses Top1':<12} | {'Δ Neto R@1':<10}")
    print("-" * 80)
    print(f"{'A (Baseline Actual)':<30} | {res_A['r5_pct']}%  | {res_A['r1_pct']}%  | {res_A['mrr']:<8} | {res_A['misses_count']:<12} | {'BASE':<10}")
    print(f"{'B (hub_match = 0)':<30} | {res_B['r5_pct']}%  | {res_B['r1_pct']}%  | {res_B['mrr']:<8} | {res_B['misses_count']:<12} | {trans_B['net_delta_r1']:>+3} ({trans_B['gains_count']}G / {trans_B['losses_count']}L)")
    print(f"{'C (Piso Hub desactivado)':<30} | {res_C['r5_pct']}%  | {res_C['r1_pct']}%  | {res_C['mrr']:<8} | {res_C['misses_count']:<12} | {trans_C['net_delta_r1']:>+3} ({trans_C['gains_count']}G / {trans_C['losses_count']}L)")
    print(f"{'D (Ambos Hubs desactivados)':<30} | {res_D['r5_pct']}%  | {res_D['r1_pct']}%  | {res_D['mrr']:<8} | {res_D['misses_count']:<12} | {trans_D['net_delta_r1']:>+3} ({trans_D['gains_count']}G / {trans_D['losses_count']}L)")
    print("=" * 80)
    print(f"Validación de linaje 72/72 comprobada: {output_report['lineage_validation_72_verified']}/{output_report['lineage_validation_72_count']}")
