#!/usr/bin/env python3
"""
scripts/fase4_desempate_sdm_discovery_aureon.py
=============================================================================
Estudio Contrafactual Exploratorio sobre Discovery: Desempate SDM Condicionado.
Protocolo Aureon — Arcadia Protocol.
Cero modificaciones a core/.
Snapshot: snapshots/qa_escape_qcr_20260811.db
Dataset: scripts/casos_qa_baseline_v1.jsonl
Split: Discovery (442 casos) + Controles Negativos Dev (20 casos)
Seed: biorag_split_seed_20261008_deterministic
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
from core.sdm import generar_vector_sdm, similitud_sdm
from scripts.fase1_diagnostico_corregido_aureon import (
    CorrectedBioRAGHarness,
    create_deterministic_splits,
    setup_fresh_temp_db,
    load_cases,
    sha256_file,
    _restaurar_estado_nodos
)

SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
OUTPUT_REPORT = os.path.join(BASE_DIR, "docs", "fase4_desempate_sdm_discovery_reporte.json")
SEED = "biorag_split_seed_20261008_deterministic"

def _normalizar_token(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)).lower()

def _clave_etiqueta(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', _normalizar_token(texto))

def es_colision_alias_o_version(c1: str, c2: str) -> bool:
    s1 = _clave_etiqueta(c1)
    s2 = _clave_etiqueta(c2)
    if s1 == s2:
        return True
    if s1.startswith(s2) or s2.startswith(s1):
        return True
    if difflib.SequenceMatcher(None, s1, s2).ratio() >= 0.75:
        return True
    return False

def aplicar_desempate_sdm(results, query, sdm_map, umbral_margen=0.010, umbral_delta_sdm=0.003):
    """
    results: lista de tuplas [(concepto, contenido, peso, estado, score, asoc), ...]
    Retorna (results_modificados, se_activo, detalle)
    """
    if not results or len(results) < 2:
        return list(results), False, "menos_de_2_candidatos"
        
    c1, cont1, p1, e1, s1, a1 = results[0]
    c2, cont2, p2, e2, s2, a2 = results[1]
    
    # Condición 1: Margen entre los dos primeros <= umbral_margen
    diff_score = float(s1) - float(s2)
    if diff_score > umbral_margen:
        return list(results), False, f"margen_superior_a_umbral_{diff_score:.4f}"
        
    # Condición 2: Colisión de alias o versión
    if not es_colision_alias_o_version(c1, c2):
        return list(results), False, "conceptos_no_son_alias_ni_version"
        
    # Condición 3: Existencia de vectores SDM
    vec1 = sdm_map.get(c1)
    vec2 = sdm_map.get(c2)
    if not vec1 or not vec2:
        return list(results), False, "falta_vector_sdm"
        
    # Cálculo de similitud SDM completa (ponderada)
    q_vec = generar_vector_sdm(concepto=query, contenido=query)
    sim1 = similitud_sdm(q_vec, vec1)
    sim2 = similitud_sdm(q_vec, vec2)
    delta_sdm = sim2 - sim1
    
    # Desempate activo si c2 supera a c1 por más de umbral_delta_sdm
    if delta_sdm > umbral_delta_sdm:
        nuevo_s2 = round(min(1.0, max(float(s2), float(s1) + 0.0001)), 4)
        candidatos_mod = list(results)
        candidatos_mod[0] = (c2, cont2, p2, e2, nuevo_s2, a2)
        candidatos_mod[1] = (c1, cont1, p1, e1, s1, a1)
        return candidatos_mod, True, f"desempate_ejecutado_delta_sdm_{delta_sdm:.4f}"
        
    return list(results), False, f"sdm_no_favorece_c2_delta_{delta_sdm:.4f}"

def main():
    print("=== FASE 4: EVALUACIÓN CONTRAFACTUAL DESEMPATE SDM EN DISCOVERY ===")
    
    snap_hash = sha256_file(SNAPSHOT_PATH)
    cases_hash = sha256_file(CASES_FILE)
    print(f"Snapshot SHA-256: {snap_hash}")
    print(f"Dataset SHA-256:  {cases_hash}")
    
    temp_db = setup_fresh_temp_db()
    
    # Cargar casos
    all_cases = load_cases()
    harness = CorrectedBioRAGHarness(temp_db, all_cases)
    
    # Cargar mapa de vectores SDM
    cur = harness.db.cursor.execute("SELECT concepto, vector FROM nodos_sdm")
    sdm_map = {r[0]: r[1] for r in cur.fetchall()}
    print(f"Vectores SDM en memoria: {len(sdm_map)}")
    
    retrieval_cases = [
        c for c in all_cases
        if c.get("concepto_esperado") and c["query"].strip().lower() not in harness.queries_ambiguas
    ]
    neg_cases = [c for c in all_cases if c.get("concepto_esperado") is None or c.get("categoria") == "negativo"]
    
    print("Obteniendo resultados baseline para split determinista...")
    base_eval = harness.execute_eval(gate_fn=None, target_cases=retrieval_cases)
    baseline_results = base_eval["results_map"]
    
    discovery_cases, validation_cases, neg_dev, neg_reserved = create_deterministic_splits(
        retrieval_cases, baseline_results, neg_cases
    )
    print(f"Casos Discovery: {len(discovery_cases)}")
    print(f"Casos Negativos Dev: {len(neg_dev)}")
    
    # Evaluar Baseline vs Contrafactual SDM sobre Discovery
    top1_base = 0
    top5_base = 0
    rr_base = 0.0
    
    top1_sdm = 0
    top5_sdm = 0
    rr_sdm = 0.0
    
    activaciones = 0
    transiciones = []
    
    gains_top1 = []
    losses_top1 = []
    
    for case in discovery_cases:
        cid = case["id"]
        cat = case["categoria"]
        query = case["query"]
        expected = case.get("concepto_esperado")
        deep = case.get("deep", False)
        
        esperado_resuelto, motivo = harness.resolver_etiqueta(expected)
        if motivo.startswith("obsoleta_resuelta"):
            expected = esperado_resuelto
            
        if cat == "dormido":
            harness.db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            harness.db.conn.commit()
        else:
            harness.db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            harness.db.conn.commit()
            
        profundidad = "profundo" if (deep or cat == "dormido") else "activos"
        results, _ = harness.db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        _restaurar_estado_nodos(harness.db, harness.estado_inicial_nodos)
        
        base_top5 = [r[0] for r in results[:5]]
        
        # Rank base
        rank_base = -1
        for idx, conc in enumerate(base_top5):
            if conc == expected:
                rank_base = idx + 1
                break
                
        if rank_base != -1:
            top5_base += 1
            if rank_base == 1:
                top1_base += 1
            rr_base += 1.0 / rank_base
            
        # Aplicar desempate contrafactual SDM
        sdm_results, activo, detalle = aplicar_desempate_sdm(results, query, sdm_map, umbral_margen=0.010, umbral_delta_sdm=0.003)
        sdm_top5 = [r[0] for r in sdm_results[:5]]
        
        rank_sdm = -1
        for idx, conc in enumerate(sdm_top5):
            if conc == expected:
                rank_sdm = idx + 1
                break
                
        if rank_sdm != -1:
            top5_sdm += 1
            if rank_sdm == 1:
                top1_sdm += 1
            rr_sdm += 1.0 / rank_sdm
            
        if activo:
            activaciones += 1
            trans = {
                "case_id": cid,
                "categoria": cat,
                "query": query,
                "gold": expected,
                "winner_base": base_top5[0] if base_top5 else None,
                "winner_sdm": sdm_top5[0] if sdm_top5 else None,
                "rank_base": rank_base,
                "rank_sdm": rank_sdm,
                "detalle": detalle
            }
            transiciones.append(trans)
            if rank_base != 1 and rank_sdm == 1:
                gains_top1.append(trans)
            elif rank_base == 1 and rank_sdm != 1:
                losses_top1.append(trans)
                
    mrr_base = rr_base / len(discovery_cases)
    mrr_sdm = rr_sdm / len(discovery_cases)
    
    # Evaluar Controles Negativos Dev (20 casos)
    fps_base = 0
    fps_sdm = 0
    for case in neg_dev:
        query = case["query"]
        results, _ = harness.db.buscar_por_frase(query, limite=5, ignore_peso_sinaptico=True)
        if results:
            fps_base += 1
        sdm_results, _, _ = aplicar_desempate_sdm(results, query, sdm_map, umbral_margen=0.010, umbral_delta_sdm=0.003)
        if sdm_results:
            fps_sdm += 1
            
    harness.db.conn.close()
    if os.path.exists(temp_db):
        try: os.remove(temp_db)
        except OSError: pass
        
    resultado_discovery = {
        "metadata": {
            "version": "fase4_desempate_sdm_discovery_aureon",
            "snapshot_sha256": snap_hash,
            "dataset_sha256": cases_hash,
            "casos_discovery": len(discovery_cases),
            "casos_negativos_dev": len(neg_dev),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "resumen_metricas": {
            "top1_base": top1_base,
            "top1_sdm": top1_sdm,
            "delta_top1": top1_sdm - top1_base,
            "recall1_base_pct": round(top1_base / len(discovery_cases) * 100, 2),
            "recall1_sdm_pct": round(top1_sdm / len(discovery_cases) * 100, 2),
            "top5_base": top5_base,
            "top5_sdm": top5_sdm,
            "delta_top5": top5_sdm - top5_base,
            "mrr_base": round(mrr_base, 4),
            "mrr_sdm": round(mrr_sdm, 4),
            "desempates_activados": activaciones,
            "ganancias_top1": len(gains_top1),
            "perdidas_top1": len(losses_top1),
            "falsos_positivos_base": fps_base,
            "falsos_positivos_sdm": fps_sdm
        },
        "transiciones": transiciones,
        "ganancias": gains_top1,
        "perdidas": losses_top1
    }
    
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(resultado_discovery, f, indent=2, ensure_ascii=False)
        
    print(f"\nResultados guardados en {OUTPUT_REPORT}")
    print(f"Top-1 Base: {top1_base}/{len(discovery_cases)} ({top1_base/len(discovery_cases)*100:.2f}%)")
    print(f"Top-1 SDM:  {top1_sdm}/{len(discovery_cases)} ({top1_sdm/len(discovery_cases)*100:.2f}%) -> Delta: {top1_sdm - top1_base:+d}")
    print(f"Top-5 Base: {top5_base}/{len(discovery_cases)} | Top-5 SDM: {top5_sdm}/{len(discovery_cases)} -> Delta: {top5_sdm - top5_base:+d}")
    print(f"MRR Base:   {mrr_base:.4f} | MRR SDM: {mrr_sdm:.4f}")
    print(f"Desempates activados: {activaciones}")
    print(f"Ganancias Top-1: {len(gains_top1)}")
    print(f"Pérdidas Top-1:  {len(losses_top1)}")
    print(f"Falsos Positivos Neg Dev: Base {fps_base}/20, SDM {fps_sdm}/20")
    
    if transiciones:
        print("\nTransiciones observadas:")
        for t in transiciones:
            print(f"  Caso {t['case_id']} [{t['categoria']}] Q: \"{t['query']}\"")
            print(f"    Gold: {t['gold']} | Base Winner: {t['winner_base']} -> SDM Winner: {t['winner_sdm']}")
            print(f"    Rank Base: {t['rank_base']} -> Rank SDM: {t['rank_sdm']} | Detalle: {t['detalle']}")

if __name__ == "__main__":
    main()
