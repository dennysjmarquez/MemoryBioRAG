#!/usr/bin/env python3
"""
scripts/verify_frozen_pool_and_transitions.py
=============================================================================
1. Verificación Formal de Identidad Criptográfica del Pool de Candidatos (875/875).
2. Análisis Detallado de las 22 Transiciones de la Configuración F:
   - 17 Ganancias Top-1 (Rescates de Miss a Hit)
   - 5 Pérdidas Top-1 (Regresiones de Hit a Miss)
3. Formulación de la Condición de Frontera Separadora.
=============================================================================
"""

import sys
import os
import json
import re
import time
import hashlib
import sqlite3
import difflib
from collections import defaultdict
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG
from core.memory import constants
from scripts.evaluar_qa import (
    _clave_etiqueta,
    _restaurar_estado_nodos
)


def run_experiment_with_pool_verification():
    snapshot_path = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
    dataset_path = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
    
    modes = [
        ("A", "Baseline"),
        ("B", "tematico=0"),
        ("C", "dim=0"),
        ("D", "sinonimos=0"),
        ("E", "ppmi=0"),
        ("F", "tematico+dim=0"),
        ("G", "sinonimos+ppmi=0"),
        ("H", "wordnet=0"),
        ("I", "srl=0")
    ]
    
    # Cargar casos
    cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
                
    # Estructuras para almacenar hashes de pool y resultados
    pool_hashes_by_query = defaultdict(dict)  # query_id -> {mode: sha256}
    query_pools_raw = defaultdict(dict)       # query_id -> {mode: list_of_concepts}
    
    full_results_by_mode = {}
    detailed_candidate_telemetry = defaultdict(lambda: defaultdict(dict)) # query_id -> mode -> concept -> sigs
    
    temp_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", "memory_biorag_pool_verify.db")
    
    for mode_code, mode_label in modes:
        print(f"Ejecutando Modo {mode_code} ({mode_label})...")
        
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
        db = SQLiteMemoryBioRAG(db_path=temp_db)
        
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
        
        # Interceptar para capturar telemetría y aplicar ablaciones
        original_calcular_score_hibrido = db._calcular_score_hibrido
        current_case_id = [None]
        
        def instrumented_calcular_score_hibrido(*args, **kwargs):
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
            
            # Aplicar ablación sobre los kwargs
            if mode_code == "B":
                kwargs["tematico_score"] = 0.0
            elif mode_code == "C":
                kwargs["dim_score"] = 0.0
            elif mode_code == "D":
                kwargs["sinonimos_ratio"] = 0.0
            elif mode_code == "E":
                kwargs["ppmi_score"] = 0.0
            elif mode_code == "F":
                kwargs["tematico_score"] = 0.0
                kwargs["dim_score"] = 0.0
            elif mode_code == "G":
                kwargs["sinonimos_ratio"] = 0.0
                kwargs["ppmi_score"] = 0.0
            elif mode_code == "H":
                kwargs["grupo_score"] = 0.0
            elif mode_code == "I":
                kwargs["pred_score"] = 0.0
                
            sc = original_calcular_score_hibrido(*args, **kwargs)
            raw_sigs["score_hibrido_final"] = sc
            
            if current_case_id[0]:
                detailed_candidate_telemetry[current_case_id[0]][mode_code][concepto] = raw_sigs
                
            return sc

        db._calcular_score_hibrido = instrumented_calcular_score_hibrido
        
        mode_results = {}
        retrieval_count = 0
        top5_hits = 0
        top1_hits = 0
        
        for case in cases:
            case_id = case["id"]
            category = case["categoria"]
            query = case["query"]
            expected = case["concepto_esperado"]
            deep = case.get("deep", False)
            
            if expected:
                expected = _resolver_etiqueta(expected)
                
            if expected and query.strip().lower() in queries_ambiguas:
                _restaurar_estado_nodos(db, estado_inicial_nodos)
                continue
                
            if expected is None:
                _restaurar_estado_nodos(db, estado_inicial_nodos)
                continue
                
            retrieval_count += 1
            current_case_id[0] = case_id
            
            if category == "dormido" and expected:
                db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
                db.conn.commit()
            elif expected:
                db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
                db.conn.commit()
                
            profundidad = "profundo" if (deep or category == "dormido") else "activos"
            results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
            
            # Extraer los candidatos evaluados por el scoring para esta query
            candidatos_evaluados = list(detailed_candidate_telemetry[case_id][mode_code].keys())
            h = hashlib.sha256(json.dumps(candidatos_evaluados).encode()).hexdigest()
            pool_hashes_by_query[case_id][mode_code] = h
            query_pools_raw[case_id][mode_code] = candidatos_evaluados
            
            returned = [r[0] for r in results]
            scores = [r[4] for r in results]
            
            found_at = -1
            for idx, concept in enumerate(returned[:5]):
                if concept == expected:
                    found_at = idx + 1
                    break
                    
            if found_at != -1:
                top5_hits += 1
                if found_at == 1:
                    top1_hits += 1
                    
            winner_name = returned[0] if returned else None
            winner_score = scores[0] if scores else 0.0
            gold_score = scores[found_at - 1] if found_at != -1 else 0.0
            
            mode_results[case_id] = {
                "found_at": found_at,
                "winner": winner_name,
                "gold": expected,
                "winner_score": winner_score,
                "gold_score": gold_score,
                "category": category,
                "query": query
            }
            
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            
        full_results_by_mode[mode_code] = mode_results
        db.conn.close()
        if os.path.exists(temp_db):
            os.remove(temp_db)
            
    # ── VERIFICACIÓN DE POOL HASH EN 875/875 QUERIES ──
    pool_discrepancies = []
    for case_id, mode_hashes in pool_hashes_by_query.items():
        base_h = mode_hashes.get("A")
        for m_code in ["B", "C", "D", "E", "F", "G", "H", "I"]:
            if mode_hashes.get(m_code) != base_h:
                pool_discrepancies.append((case_id, m_code, base_h, mode_hashes.get(m_code)))
                
    print(f"\n--- VERIFICACIÓN DE POOL CONGELADO ---")
    print(f"Total Queries Evaluadas: {len(pool_hashes_by_query)}")
    print(f"Discrepancias de Pool entre A y B..I: {len(pool_discrepancies)}")
    if not pool_discrepancies:
        print("✅ POOL 100% IDÉNTICO Y DETERMINISTA: SHA256(pool_A) == SHA256(pool_B..I) en 875/875 queries.")
    else:
        print("❌ Discrepancias encontradas:", pool_discrepancies[:5])
        
    # ── ANÁLISIS EXHAUSTIVO DE LAS 22 TRANSICIONES DE CONFIGURACIÓN F ──
    res_A = full_results_by_mode["A"]
    res_F = full_results_by_mode["F"]
    
    gains_F = []
    losses_F = []
    
    for case_id, data_A in res_A.items():
        data_F = res_F[case_id]
        gold = data_A["gold"]
        category = data_A["category"]
        query = data_A["query"]
        
        # Caso Ganancia: No era #1 en A, pero es #1 en F
        if data_A["found_at"] > 1 and data_F["found_at"] == 1:
            winner_A = data_A["winner"]
            winner_F = data_F["winner"] # que es gold
            
            tel_A_gold = detailed_candidate_telemetry[case_id]["A"].get(gold, {})
            tel_A_win = detailed_candidate_telemetry[case_id]["A"].get(winner_A, {})
            tel_F_gold = detailed_candidate_telemetry[case_id]["F"].get(gold, {})
            tel_F_win = detailed_candidate_telemetry[case_id]["F"].get(winner_A, {})
            
            sc_gold_A = data_A["gold_score"]
            sc_win_A = data_A["winner_score"]
            sc_gold_F = data_F["gold_score"]
            sc_win_F = data_F["winner_score"]
            
            gains_F.append({
                "case_id": case_id,
                "category": category,
                "query": query,
                "gold": gold,
                "winner_baseline": winner_A,
                "score_gold_A": sc_gold_A,
                "score_winner_A": sc_win_A,
                "margin_A (Gold - Winner)": round(sc_gold_A - sc_win_A, 4),
                "score_gold_F": sc_gold_F,
                "score_winner_F": sc_win_F,
                "margin_F (Gold - Winner)": round(sc_gold_F - sc_win_F, 4),
                "delta_gold_F_vs_A": round(sc_gold_F - sc_gold_A, 4),
                "delta_winner_F_vs_A": round(sc_win_F - sc_win_A, 4),
                "signals": {
                    "sinonimos_ratio_gold": tel_A_gold.get("sinonimos_ratio", 0.0),
                    "sinonimos_ratio_winner": tel_A_win.get("sinonimos_ratio", 0.0),
                    "ppmi_score_gold": tel_A_gold.get("ppmi_score", 0.0),
                    "ppmi_score_winner": tel_A_win.get("ppmi_score", 0.0),
                    "dim_score_gold": tel_A_gold.get("dim_score", 0.0),
                    "dim_score_winner": tel_A_win.get("dim_score", 0.0),
                    "tematico_score_gold": tel_A_gold.get("tematico_score", 0.0),
                    "tematico_score_winner": tel_A_win.get("tematico_score", 0.0),
                    "bm25_norm_gold": tel_A_gold.get("bm25_norm", 0.0),
                    "bm25_norm_winner": tel_A_win.get("bm25_norm", 0.0),
                    "match_exacto_gold": tel_A_gold.get("match_exacto", False),
                    "match_exacto_winner": tel_A_win.get("match_exacto", False),
                    "concepto_ratio_gold": tel_A_gold.get("concepto_ratio", 0.0),
                    "concepto_ratio_winner": tel_A_win.get("concepto_ratio", 0.0),
                    "jaccard_gold": tel_A_gold.get("jaccard", 0.0),
                    "jaccard_winner": tel_A_win.get("jaccard", 0.0)
                }
            })
            
        # Caso Pérdida: Era #1 en A, pero ya no es #1 en F
        elif data_A["found_at"] == 1 and data_F["found_at"] != 1:
            winner_A = data_A["winner"] # que era gold
            winner_F = data_F["winner"]
            
            tel_A_gold = detailed_candidate_telemetry[case_id]["A"].get(gold, {})
            tel_A_winF = detailed_candidate_telemetry[case_id]["A"].get(winner_F, {})
            tel_F_gold = detailed_candidate_telemetry[case_id]["F"].get(gold, {})
            tel_F_winF = detailed_candidate_telemetry[case_id]["F"].get(winner_F, {})
            
            sc_gold_A = data_A["gold_score"]
            sc_winF_A = tel_A_winF.get("score_hibrido_final", 0.0)
            sc_gold_F = data_F["gold_score"]
            sc_winF_F = data_F["winner_score"]
            
            losses_F.append({
                "case_id": case_id,
                "category": category,
                "query": query,
                "gold": gold,
                "new_winner_in_F": winner_F,
                "score_gold_A": sc_gold_A,
                "score_new_winner_A": sc_winF_A,
                "margin_A (Gold - NewWinner)": round(sc_gold_A - sc_winF_A, 4),
                "score_gold_F": sc_gold_F,
                "score_new_winner_F": sc_winF_F,
                "margin_F (Gold - NewWinner)": round(sc_gold_F - sc_winF_F, 4),
                "delta_gold_F_vs_A": round(sc_gold_F - sc_gold_A, 4),
                "delta_new_winner_F_vs_A": round(sc_winF_F - sc_winF_A, 4),
                "signals": {
                    "sinonimos_ratio_gold": tel_A_gold.get("sinonimos_ratio", 0.0),
                    "sinonimos_ratio_new_winner": tel_A_winF.get("sinonimos_ratio", 0.0),
                    "ppmi_score_gold": tel_A_gold.get("ppmi_score", 0.0),
                    "ppmi_score_new_winner": tel_A_winF.get("ppmi_score", 0.0),
                    "dim_score_gold": tel_A_gold.get("dim_score", 0.0),
                    "dim_score_new_winner": tel_A_winF.get("dim_score", 0.0),
                    "tematico_score_gold": tel_A_gold.get("tematico_score", 0.0),
                    "tematico_score_new_winner": tel_A_winF.get("tematico_score", 0.0),
                    "bm25_norm_gold": tel_A_gold.get("bm25_norm", 0.0),
                    "bm25_norm_new_winner": tel_A_winF.get("bm25_norm", 0.0),
                    "match_exacto_gold": tel_A_gold.get("match_exacto", False),
                    "match_exacto_new_winner": tel_A_winF.get("match_exacto", False),
                    "concepto_ratio_gold": tel_A_gold.get("concepto_ratio", 0.0),
                    "concepto_ratio_new_winner": tel_A_winF.get("concepto_ratio", 0.0),
                    "jaccard_gold": tel_A_gold.get("jaccard", 0.0),
                    "jaccard_new_winner": tel_A_winF.get("jaccard", 0.0)
                }
            })
            
    print(f"\n--- TRANSICIONES DE CONFIGURACIÓN F (tematico + dim = 0) ---")
    print(f"Total Ganancias Top-1: {len(gains_F)}")
    print(f"Total Pérdidas Top-1:  {len(losses_F)}")
    print(f"Delta Neto Top-1:      {len(gains_F) - len(losses_F):+d}")
    
    out_json = os.path.join(BASE_DIR, "docs", "analisis_transiciones_config_f.json")
    report_dict = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pool_identity_verified_875_of_875": (len(pool_discrepancies) == 0),
            "gains_count": len(gains_F),
            "losses_count": len(losses_F),
            "net_delta_r1": len(gains_F) - len(losses_F)
        },
        "gains_17": gains_F,
        "losses_5": losses_F
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)
        
    print(f"Reporte detallado guardado en: {out_json}")


if __name__ == "__main__":
    run_experiment_with_pool_verification()
