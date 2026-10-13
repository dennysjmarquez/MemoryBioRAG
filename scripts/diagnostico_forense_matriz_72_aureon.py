#!/usr/bin/env python3
"""
scripts/diagnostico_forense_matriz_72_aureon.py
=============================================================================
Investigación Forense Estructural de los 72 Fallos de Baseline de MemoryBioRAG.
Protocolo Aureon — Arcadia Protocol.
Cero modificaciones a core/.
Snapshot: snapshots/qa_escape_qcr_20260811.db
Dataset: scripts/casos_qa_baseline_v1.jsonl
=============================================================================
"""

import os
import sys
import json
import sqlite3
import unicodedata
import re
import difflib
from collections import defaultdict, Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.sdm import generar_vector_sdm, similitud_sdm, distancia_hamming

SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
DIAG_V2_FILE = os.path.join(BASE_DIR, "docs", "fase1_diagnostico_72_misses_v2.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "docs", "forense_matriz_72_misses.json")

def normalizar_cadena(s: str) -> str:
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', '', s)

def es_colision_version_o_alias(gold: str, winner: str) -> tuple[bool, str]:
    g_norm = normalizar_cadena(gold)
    w_norm = normalizar_cadena(winner)
    
    # 1. Idénticos tras remover guiones y puntuación
    if g_norm == w_norm:
        return True, "nombre_normalizado_identico"
        
    # 2. Uno contiene al otro o difieren solo en versión/sufijo numérico
    if g_norm.startswith(w_norm) or w_norm.startswith(g_norm):
        return True, "prefijo_comun_version_o_variante"
        
    # 3. Similitud de secuencia muy alta (typo o variación ortográfica en concepto)
    seq_ratio = difflib.SequenceMatcher(None, g_norm, w_norm).ratio()
    if seq_ratio >= 0.75:
        return True, f"alta_similitud_lexica_concepto_{seq_ratio:.2f}"
        
    return False, "conceptos_distintos"

def main():
    print("Iniciando auditoría forense sobre los 72 fallos de baseline...")
    
    with open(DIAG_V2_FILE, "r", encoding="utf-8") as f:
        diag_v2 = json.load(f)
        
    misses = diag_v2["misses"]
    print(f"Cargados {len(misses)} casos de fallo del diagnóstico v2.")
    
    conn = sqlite3.connect(SNAPSHOT_PATH)
    cursor = conn.cursor()
    
    # Cargar todos los nodos SDM en memoria para análisis rápido
    cursor.execute("SELECT concepto, vector FROM nodos_sdm")
    sdm_map = {row[0]: row[1] for row in cursor.fetchall()}
    print(f"Cargados {len(sdm_map)} vectores SDM desde nodos_sdm.")
    
    matriz_forense = []
    
    # Estadísticas para el resumen
    cat_counts = Counter()
    tipo_fallo_counts = Counter()
    sdm_favors_counts = Counter()
    pred_availability_counts = Counter()
    
    for m in misses:
        cid = m["case_id"]
        query = m["query"]
        cat = m["categoria"]
        gold = m["gold"]
        winner = m["winner"]
        gold_rank = m.get("gold_rank_A")
        evaluable = m.get("evaluable_aritmeticamente", False)
        margin = m.get("margin_original")
        
        cat_counts[cat] += 1
        
        # kwargs de scoring
        g_kw = m.get("gold_raw_kwargs") or {}
        w_kw = m.get("winner_raw_kwargs") or {}
        
        # 1. SDM Vector Analysis
        q_vec = generar_vector_sdm(concepto=query, contenido=query)
        g_vec = sdm_map.get(gold)
        w_vec = sdm_map.get(winner)
        
        sdm_info = {
            "gold_sdm_present": g_vec is not None,
            "winner_sdm_present": w_vec is not None,
            "sim_sdm_gold": None,
            "sim_sdm_winner": None,
            "sdm_delta": None,
            "hamming_gold": None,
            "hamming_winner": None,
            "sdm_veredicto": "no_disponible"
        }
        
        if g_vec and w_vec:
            sim_g = similitud_sdm(q_vec, g_vec)
            sim_w = similitud_sdm(q_vec, w_vec)
            ham_g = distancia_hamming(q_vec, g_vec)
            ham_w = distancia_hamming(q_vec, w_vec)
            delta = round(sim_g - sim_w, 4)
            
            sdm_info["sim_sdm_gold"] = sim_g
            sdm_info["sim_sdm_winner"] = sim_w
            sdm_info["sdm_delta"] = delta
            sdm_info["hamming_gold"] = ham_g
            sdm_info["hamming_winner"] = ham_w
            
            if delta > 0.001:
                sdm_info["sdm_veredicto"] = "favorece_gold"
                sdm_favors_counts["favorece_gold"] += 1
            elif delta < -0.001:
                sdm_info["sdm_veredicto"] = "favorece_winner"
                sdm_favors_counts["favorece_winner"] += 1
            else:
                sdm_info["sdm_veredicto"] = "empate"
                sdm_favors_counts["empate"] += 1
        else:
            sdm_favors_counts["sin_vector"] += 1
            
        # 2. Sinapsis / Grafo Analysis
        cursor.execute("SELECT count(*) FROM sinapsis WHERE origen = ? OR destino = ?", (gold, gold))
        g_degree = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM sinapsis WHERE origen = ? OR destino = ?", (winner, winner))
        w_degree = cursor.fetchone()[0]
        
        # Vecinos compartidos entre Gold y Winner
        cursor.execute("""
            SELECT count(distinct vecino) FROM (
                SELECT CASE WHEN origen = ? THEN destino ELSE origen END as vecino FROM sinapsis WHERE origen = ? OR destino = ?
                INTERSECT
                SELECT CASE WHEN origen = ? THEN destino ELSE origen END as vecino FROM sinapsis WHERE origen = ? OR destino = ?
            )
        """, (gold, gold, gold, winner, winner, winner))
        vecinos_compartidos = cursor.fetchone()[0]
        
        # Arista directa entre Gold y Winner
        cursor.execute("""
            SELECT peso, tipo FROM sinapsis 
            WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)
        """, (gold, winner, winner, gold))
        arista_directa = cursor.fetchone()
        
        grafo_info = {
            "grado_gold": g_degree,
            "grado_winner": w_degree,
            "vecinos_compartidos": vecinos_compartidos,
            "arista_directa_existe": arista_directa is not None,
            "arista_directa_peso": arista_directa[0] if arista_directa else None,
            "arista_directa_tipo": arista_directa[1] if arista_directa else None
        }
        
        # 3. Predicados SRL Analysis
        cursor.execute("SELECT sujeto, accion, objeto, contexto FROM predicados WHERE concepto = ?", (gold,))
        g_preds = [{"sujeto": r[0], "accion": r[1], "objeto": r[2], "contexto": r[3]} for r in cursor.fetchall()]
        cursor.execute("SELECT sujeto, accion, objeto, contexto FROM predicados WHERE concepto = ?", (winner,))
        w_preds = [{"sujeto": r[0], "accion": r[1], "objeto": r[2], "contexto": r[3]} for r in cursor.fetchall()]
        
        pred_status = "ninguno"
        if g_preds and w_preds:
            pred_status = "ambos"
        elif g_preds:
            pred_status = "solo_gold"
        elif w_preds:
            pred_status = "solo_winner"
        pred_availability_counts[pred_status] += 1
        
        predicados_info = {
            "gold_preds_count": len(g_preds),
            "winner_preds_count": len(w_preds),
            "status": pred_status,
            "gold_preds_samples": g_preds[:2],
            "winner_preds_samples": w_preds[:2]
        }
        
        # 4. Clasificación del Tipo de Fallo
        es_colision, detalle_colision = es_colision_version_o_alias(gold, winner)
        
        if not evaluable:
            tipo_fallo = "fallo_recuperacion_pool_ausente"
            evidencia_favorece_winner = "Winner inyectado por Concept Hub post-processing o rescate especial."
            evidencia_favorece_gold = "Gold presente en candidates pero superado por inyección no ponderada."
            info_faltante = "Mecanismo de competición justa antes de la inyección forzada del hub."
        elif es_colision:
            tipo_fallo = "fallo_desambiguacion_version_o_alias"
            evidencia_favorece_winner = f"Ligeramente superior en BM25 o sinónimos debido a grafía ({detalle_colision})."
            evidencia_favorece_gold = f"Es el concepto canónico exacto solicitado por la query ({gold})."
            info_faltante = "Resolución de sinonimia/canonicidad o unificación de grafías (guión vs guión bajo, sufijos de versión)."
        elif cat == "por_tema":
            tipo_fallo = "fallo_evidencia_relacional_por_tema"
            evidencia_favorece_winner = f"Mayor score temático/JSD/PPMI por co-ocurrencia superficial de tokens ({w_kw.get('tematico_score', 0):.2f})."
            evidencia_favorece_gold = f"Relevancia conceptual ontológica real para el tema de la consulta."
            info_faltante = "Señal relacional o puente topológico que conecte la consulta con el nodo Gold sin depender de coincidencia superficial de palabras."
        elif cat == "sinonimo":
            tipo_fallo = "fallo_semantico_sinonimo_lejano"
            evidencia_favorece_winner = f"Mayor coincidencia léxica directa o PPMI ({w_kw.get('bm25_norm', 0):.2f})."
            evidencia_favorece_gold = f"Es el sinónimo semántico verdadero aunque tenga menor BM25."
            info_faltante = "Conexión en tabla sinonimos o puente semántico latente calibrado."
        else:
            tipo_fallo = "fallo_ranking_competitivo_multisenal"
            evidencia_favorece_winner = f"Ganó por suma multi-señal (BM25: {w_kw.get('bm25_norm', 0):.2f}, PPMI: {w_kw.get('ppmi_score', 0):.2f})."
            evidencia_favorece_gold = f"Presencia en top candidatos (rank {gold_rank}) con señales cercanas."
            info_faltante = "Señal discriminativa ortogonal para desempatar candidates con scores cercanos."
            
        tipo_fallo_counts[tipo_fallo] += 1
        
        matriz_forense.append({
            "case_id": cid,
            "query": query,
            "categoria": cat,
            "gold": gold,
            "winner": winner,
            "gold_rank": gold_rank,
            "winner_rank": 1,
            "evaluable_aritmeticamente": evaluable,
            "margin_original": margin,
            "tipo_fallo": tipo_fallo,
            "es_colision_alias_version": es_colision,
            "detalle_colision": detalle_colision,
            "signals_gold": {
                "bm25_norm": g_kw.get("bm25_norm", 0.0),
                "concepto_ratio": g_kw.get("concepto_ratio", 0.0),
                "sinonimos_ratio": g_kw.get("sinonimos_ratio", 0.0),
                "dim_score": g_kw.get("dim_score", 0.0),
                "tematico_score": g_kw.get("tematico_score", 0.0),
                "ppmi_score": g_kw.get("ppmi_score", 0.0),
                "pred_score": g_kw.get("pred_score", 0.0),
                "hub_match": g_kw.get("hub_match", 0.0),
                "jsd_score": g_kw.get("jsd_score", 0.0),
                "peso_sinaptico": g_kw.get("peso_sinaptico", 0.0),
                "asoc_count": g_kw.get("asoc_count", 0),
            },
            "signals_winner": {
                "bm25_norm": w_kw.get("bm25_norm", 0.0),
                "concepto_ratio": w_kw.get("concepto_ratio", 0.0),
                "sinonimos_ratio": w_kw.get("sinonimos_ratio", 0.0),
                "dim_score": w_kw.get("dim_score", 0.0),
                "tematico_score": w_kw.get("tematico_score", 0.0),
                "ppmi_score": w_kw.get("ppmi_score", 0.0),
                "pred_score": w_kw.get("pred_score", 0.0),
                "hub_match": w_kw.get("hub_match", 0.0),
                "jsd_score": w_kw.get("jsd_score", 0.0),
                "peso_sinaptico": w_kw.get("peso_sinaptico", 0.0),
                "asoc_count": w_kw.get("asoc_count", 0),
            },
            "sdm_analysis": sdm_info,
            "grafo_analysis": grafo_info,
            "predicados_analysis": predicados_info,
            "forense_diagnostico": {
                "evidencia_favorece_winner": evidencia_favorece_winner,
                "evidencia_favorece_gold": evidencia_favorece_gold,
                "info_faltante_para_distinguir": info_faltante
            }
        })
        
    conn.close()
    
    reporte_final = {
        "metadata": {
            "version": "forense_72_misses_v1_aureon",
            "total_misses": len(matriz_forense),
            "snapshot_path": SNAPSHOT_PATH,
            "dataset_path": CASES_FILE
        },
        "resumen_estadistico": {
            "distribucion_por_categoria": dict(cat_counts),
            "distribucion_tipo_fallo": dict(tipo_fallo_counts),
            "sdm_discriminacion": dict(sdm_favors_counts),
            "predicados_disponibilidad": dict(pred_availability_counts)
        },
        "matriz_forense": matriz_forense
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(reporte_final, f, indent=2, ensure_ascii=False)
        
    print(f"Reporte forense guardado exitosamente en {OUTPUT_JSON}")
    print("\n=== RESUMEN EJECUTIVO ===")
    print("Categorías:", dict(cat_counts))
    print("Tipos de Fallo:", dict(tipo_fallo_counts))
    print("SDM Discriminación:", dict(sdm_favors_counts))
    print("Predicados Disponibilidad:", dict(pred_availability_counts))

if __name__ == "__main__":
    main()
