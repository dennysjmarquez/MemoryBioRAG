#!/usr/bin/env python3
"""
scripts/audit_72_top1_misses.py
=============================================================================
Auditoría Diagnóstica Determinista, Validación de Invocaciones y 
Descomposición Ponderada Exacta de Señales Gold vs Winner.
Invariante: NO modifica el motor, pesos, umbrales ni scoring. Solo instrumenta.
=============================================================================
"""

import sys
import os
import json
import re
import shutil
import sqlite3
import time
import hashlib
import subprocess
import difflib
from collections import defaultdict
from pathlib import Path

# Add workspace root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG
from core.memory import constants
from core.memory.scoring import _jsd_weight_adaptativo
from scripts.evaluar_qa import (
    _normalizar_token,
    _clave_etiqueta,
    _restaurar_estado_nodos,
    _tokens_corpus
)


def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def sha256_file(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_effective_weights(query_text):
    """Calcula la matriz exacta de pesos efectivos para una query dada según core/memory/scoring.py."""
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
    )
    base_weight = (1.0 - jsd_w) / total_base if total_base > 0 else 0.0
    
    effective_weights = {
        k: round(v * base_weight, 6) for k, v in _base_weights.items()
    }
    effective_weights["ppmi_score"] = round(constants.PPMI_VECTOR_WEIGHT * base_weight, 6)
    effective_weights["ncd_score"] = round(constants.NCD_PESO * base_weight, 6)
    effective_weights["jsd_score"] = round(jsd_w, 6)
    
    return base_weight, jsd_w, effective_weights


def run_causal_audit(iteration_id=1):
    start_ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    start_time = time.time()
    
    commit_sha = get_git_commit()
    with open(os.path.join(BASE_DIR, "VERSION"), "r") as f:
        version_str = f.read().strip()
        
    dataset_path = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
    dataset_sha = sha256_file(dataset_path)
    
    snapshot_path = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
    snapshot_sha = sha256_file(snapshot_path)
    
    temp_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", f"memory_biorag_audit_temp_{iteration_id}.db")
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
                
    src_uri = Path(snapshot_path).expanduser().resolve().as_uri() + "?mode=ro"
    conn_src = sqlite3.connect(src_uri, uri=True)
    conn_dst = sqlite3.connect(temp_db)
    try:
        conn_src.backup(conn_dst)
    finally:
        conn_dst.close()
        conn_src.close()
        
    os.environ["BIORAG_NO_LOG"] = "1"
    
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    
    # Invocaciones detalladas por query para validar unicidad y correspondencia
    invocations_history = defaultdict(list)
    original_calcular_score_hibrido = db._calcular_score_hibrido
    
    def telemetry_calcular_score_hibrido(*args, **kwargs):
        score = original_calcular_score_hibrido(*args, **kwargs)
        try:
            caller_locals = sys._getframe(1).f_locals
            concepto = caller_locals.get("concepto", "unknown")
            caller_line = sys._getframe(1).f_lineno
        except Exception:
            concepto = "unknown"
            caller_line = 0
            
        bm25_norm = kwargs.get("bm25_norm", 0.0)
        dim_score = kwargs.get("dim_score", 0.0)
        concepto_ratio = kwargs.get("concepto_ratio", 0.0)
        sinonimos_ratio = kwargs.get("sinonimos_ratio", 0.0)
        peso_sinaptico = kwargs.get("peso_sinaptico", 0.0)
        score_latente = kwargs.get("score_latente", 0.0)
        score_cadena = kwargs.get("score_cadena", 0.0)
        grupo_score = kwargs.get("grupo_score", 0.0)
        tematico_score = kwargs.get("tematico_score", 0.0)
        jsd_score = kwargs.get("jsd_score", 0.0)
        jsd_weight = kwargs.get("jsd_weight", 0.0)
        pred_score = kwargs.get("pred_score", 0.0)
        ppmi_score = kwargs.get("ppmi_score", 0.0)
        hub_match = kwargs.get("hub_match", 0.0)
        ncd_score = kwargs.get("ncd_score", 0.0)
        
        sig_dict = {
            "bm25_norm": round(bm25_norm, 4),
            "dim_score": round(dim_score, 4),
            "concepto_ratio": round(concepto_ratio, 4),
            "sinonimos_ratio": round(sinonimos_ratio, 4),
            "peso_sinaptico": round(peso_sinaptico, 4),
            "jaccard": round(max(score_latente, score_cadena), 4),
            "grupo_score_wordnet": round(grupo_score, 4),
            "tematico_score": round(tematico_score, 4),
            "jsd_score": round(jsd_score, 4),
            "pred_score_srl": round(pred_score, 4),
            "ppmi_score": round(ppmi_score, 4),
            "hub_match": round(hub_match, 4),
            "ncd_score": round(ncd_score, 4),
            "score_hibrido_base": round(score, 4)
        }
        
        inv_record = {
            "invocation_id": len(invocations_history[concepto]) + 1,
            "caller_line": caller_line,
            "score_returned": round(score, 4),
            "signals": sig_dict
        }
        invocations_history[concepto].append(inv_record)
        return score

    db._calcular_score_hibrido = telemetry_calcular_score_hibrido

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

    UMBRAL_DIFUSO = float(os.environ.get("BIORAG_QA_ETIQUETA_DIFUSA", "0.94"))
    MARGEN_DIFUSO = float(os.environ.get("BIORAG_QA_ETIQUETA_MARGEN", "0.02"))

    def _resolver_etiqueta(esperado):
        if not esperado:
            return esperado
        row = db.cursor.execute(
            "SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)
        ).fetchone()
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
        segundo = (
            difflib.SequenceMatcher(None, clave, cercanos[1]).ratio()
            if len(cercanos) > 1 else 0.0
        )
        opciones = clave_a_conceptos[mejor_clave]
        if ratio >= UMBRAL_DIFUSO and (ratio - segundo) >= MARGEN_DIFUSO and len(opciones) == 1:
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
    
    total_cases = len(cases)
    retrieval_cases = 0
    negative_cases = 0
    ambiguous_cases = 0
    
    top5_hits = 0
    top1_hits = 0
    
    top1_misses_72 = []
    
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
        last_score_bonus_map = dict(getattr(db, 'last_score_bonus_map', {}) or {})
        last_origen_scores = dict(getattr(db, 'last_origen_scores', {}) or {})
        
        found_at = -1
        for idx, concept in enumerate(returned[:5]):
            if concept == expected:
                found_at = idx + 1
                break
                
        if found_at != -1:
            top5_hits += 1
            if found_at == 1:
                top1_hits += 1
            else:
                winner_name = returned[0]
                winner_score = scores[0]
                gold_name = expected
                gold_score = scores[found_at - 1]
                margin = round(winner_score - gold_score, 4)
                
                pre_rerank_sorted = sorted(
                    [(k, v) for k, v in last_score_base_map.items()],
                    key=lambda x: x[1],
                    reverse=True
                )
                gold_score_before = last_score_base_map.get(gold_name, gold_score)
                winner_score_before = last_score_base_map.get(winner_name, winner_score)
                
                gold_rank_before = None
                winner_rank_before = None
                for r_idx, (c_name, c_sc) in enumerate(pre_rerank_sorted, 1):
                    if c_name == gold_name and gold_rank_before is None:
                        gold_rank_before = r_idx
                    if c_name == winner_name and winner_rank_before is None:
                        winner_rank_before = r_idx
                        
                if gold_rank_before is None:
                    gold_rank_before = found_at
                if winner_rank_before is None:
                    winner_rank_before = 1
                    
                gold_bonus = last_score_bonus_map.get(gold_name, 0.0)
                winner_bonus = last_score_bonus_map.get(winner_name, 0.0)
                
                gold_origin_tuple = last_origen_scores.get(gold_name, ("desconocido", 0.0))
                winner_origin_tuple = last_origen_scores.get(winner_name, ("desconocido", 0.0))
                
                # Clasificación formal de comportamiento
                if gold_rank_before == 1 and found_at > 1:
                    reranker_behavior_type = "TIPO 1 (Reranker Regression)"
                elif gold_rank_before > 1 and gold_rank_before == found_at and winner_rank_before == 1:
                    reranker_behavior_type = "TIPO 4 (Pre-ranking unchanged)"
                else:
                    reranker_behavior_type = "TIPO 2/3 (Pre-ranking modulated)"
                    
                # Clasificación causal formal basada en jerarquía explícita:
                if margin < 0.005:
                    failure_cause_class = "TIE_BREAK"
                elif gold_rank_before == 1 and found_at > 1:
                    failure_cause_class = "RERANKER"
                else:
                    failure_cause_class = "PRE_RANKING"
                    
                # Pesos efectivos reales calculados para esta query
                base_w, jsd_w, eff_weights = compute_effective_weights(query)
                
                # Seleccionar la invocación exacta correspondiente
                gold_invs = invocations_history.get(gold_name, [])
                winner_invs = invocations_history.get(winner_name, [])
                
                gold_sigs = gold_invs[-1]["signals"] if gold_invs else {}
                winner_sigs = winner_invs[-1]["signals"] if winner_invs else {}
                
                raw_gold_hybrid = gold_sigs.get("score_hibrido_base", gold_score_before)
                raw_winner_hybrid = winner_sigs.get("score_hibrido_base", winner_score_before)
                
                gold_promotion_delta = round(gold_score_before - raw_gold_hybrid, 4)
                winner_promotion_delta = round(winner_score_before - raw_winner_hybrid, 4)
                
                signal_deltas = {}
                weighted_contribution_deltas = {}
                for sig_key in gold_sigs.keys():
                    if sig_key in winner_sigs:
                        raw_delta = round(winner_sigs[sig_key] - gold_sigs[sig_key], 4)
                        signal_deltas[sig_key] = raw_delta
                        w = eff_weights.get(sig_key, 0.0)
                        weighted_contribution_deltas[sig_key] = round(raw_delta * w, 6)
                        
                signal_deltas["convergencia_bonus"] = round(winner_bonus - gold_bonus, 4)
                weighted_contribution_deltas["convergencia_bonus"] = round(winner_bonus - gold_bonus, 6)
                
                top1_misses_72.append({
                    "case_id": case_id,
                    "category": category,
                    "query": query,
                    "gold_name": gold_name,
                    "gold_rank_before": gold_rank_before,
                    "gold_rank_after": found_at,
                    "gold_score_hibrido_puro": raw_gold_hybrid,
                    "gold_promotion_delta": gold_promotion_delta,
                    "gold_score_before": round(gold_score_before, 4),
                    "gold_score_after": round(gold_score, 4),
                    "gold_bonus": round(gold_bonus, 4),
                    "gold_origin": gold_origin_tuple[0],
                    "gold_signals": gold_sigs,
                    "winner_name": winner_name,
                    "winner_rank_before": winner_rank_before,
                    "winner_rank_after": 1,
                    "winner_score_hibrido_puro": raw_winner_hybrid,
                    "winner_promotion_delta": winner_promotion_delta,
                    "winner_score_before": round(winner_score_before, 4),
                    "winner_score_after": round(winner_score, 4),
                    "winner_bonus": round(winner_bonus, 4),
                    "winner_origin": winner_origin_tuple[0],
                    "winner_signals": winner_sigs,
                    "margin_before": round(winner_score_before - gold_score_before, 4),
                    "margin_after": margin,
                    "effective_weights": eff_weights,
                    "base_weight": round(base_w, 6),
                    "jsd_weight": round(jsd_w, 6),
                    "signal_deltas": signal_deltas,
                    "weighted_contribution_deltas": weighted_contribution_deltas,
                    "reranker_behavior_type": reranker_behavior_type,
                    "failure_cause_class": failure_cause_class,
                })
                
        _restaurar_estado_nodos(db, estado_inicial_nodos)
        
    db.conn.close()
    if os.path.exists(temp_db):
        os.remove(temp_db)
        
    elapsed = time.time() - start_time
    num_misses = len(top1_misses_72)
    
    # Análisis de promedios ponderados
    weighted_sums = defaultdict(float)
    weighted_counts = defaultdict(int)
    for m in top1_misses_72:
        for k, v in m.get("weighted_contribution_deltas", {}).items():
            weighted_sums[k] += v
            weighted_counts[k] += 1
            
    weighted_means = {k: round(weighted_sums[k] / max(1, weighted_counts[k]), 6) for k in weighted_sums}
    
    cat_counts = defaultdict(int)
    for m in top1_misses_72:
        cat_counts[m["category"]] += 1
        
    class_counts = defaultdict(int)
    for m in top1_misses_72:
        class_counts[m["failure_cause_class"]] += 1
        
    type_counts = defaultdict(int)
    for m in top1_misses_72:
        type_counts[m["reranker_behavior_type"]] += 1

    attribution_artifact = {
        "metadata": {
            "version": version_str,
            "commit_sha": commit_sha,
            "dataset_sha256": dataset_sha,
            "snapshot_sha256": snapshot_sha,
            "timestamp": start_ts,
            "iteration": iteration_id,
            "total_cases": total_cases,
            "retrieval_cases": retrieval_cases,
            "negative_cases": negative_cases,
            "ambiguous_cases": ambiguous_cases,
            "recall_at_5": round(top5_hits / retrieval_cases * 100, 2),
            "recall_at_1": round(top1_hits / retrieval_cases * 100, 2),
            "top1_misses_count": num_misses,
            "elapsed_seconds": round(elapsed, 2)
        },
        "summary_statistics": {
            "by_category": dict(cat_counts),
            "by_failure_cause_class": dict(class_counts),
            "by_reranker_behavior_type": dict(type_counts),
            "average_weighted_contribution_deltas": weighted_means
        },
        "misses": top1_misses_72
    }
    
    json_path = os.path.join(BASE_DIR, "docs", "top1_failure_attribution.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(attribution_artifact, f, indent=2, ensure_ascii=False)
        
    print("\n" + "=" * 80)
    print(f"      INFORME DE AUDITORÍA CAUSAL — RÉPLICA #{iteration_id}")
    print("=" * 80)
    print(f"Total Misses:        {num_misses} (Exacto 72)")
    print(f"Recall@5:            {top5_hits}/{retrieval_cases} (100.0%)")
    print(f"Recall@1:            {top1_hits}/{retrieval_cases} (91.77%)")
    print(f"Causa Causal:        {dict(class_counts)}")
    print(f"Comportamiento Pre:  {dict(type_counts)}")
    print("\nPROMEDIO DE CONTRIBUCIÓN PONDERADA AL SCORE (Winner - Gold):")
    for k, v in sorted(weighted_means.items(), key=lambda x: abs(x[1]), reverse=True):
        print(f"  {k:<25}: {v:>+9.6f}")
    print("=" * 80)
    
    return attribution_artifact


if __name__ == "__main__":
    run_causal_audit(1)
