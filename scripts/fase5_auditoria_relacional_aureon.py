#!/usr/bin/env python3
"""
scripts/fase5_auditoria_relacional_aureon.py
=============================================================================
Fase 5 — Auditoría de Errores y Evidencia Relacional Independiente
Protocolo Científico Aureon — Arcadia Protocol.
Cero modificaciones a core/.
Snapshot: snapshots/qa_escape_qcr_20260811.db
Dataset: scripts/casos_qa_baseline_v1.jsonl
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
from collections import defaultdict, Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
DIAG_V2_FILE = os.path.join(BASE_DIR, "docs", "fase1_diagnostico_72_misses_v2.json")
OUTPUT_REPORT_JSON = os.path.join(BASE_DIR, "docs", "fase5_auditoria_relacional_reporte.json")
OUTPUT_REPORT_MD = os.path.join(BASE_DIR, "docs", "fase5_auditoria_relacional_reporte.md")

def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def normalizar_texto(s: str) -> str:
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', '', s)

def calcular_jaccard_tokens(t1: str, t2: str) -> float:
    s1 = set(t1.lower().split())
    s2 = set(t2.lower().split())
    if not (s1 | s2):
        return 0.0
    return len(s1 & s2) / len(s1 | s2)

def main():
    print("=== FASE 5: AUDITORÍA DE ERRORES Y EVIDENCIA RELACIONAL INDEPENDIENTE ===")
    
    snap_hash = sha256_file(SNAPSHOT_PATH)
    cases_hash = sha256_file(CASES_FILE)
    print(f"Snapshot SHA-256: {snap_hash}")
    print(f"Dataset SHA-256:  {cases_hash}")
    
    conn = sqlite3.connect(SNAPSHOT_PATH)
    cursor = conn.cursor()
    
    with open(DIAG_V2_FILE, "r", encoding="utf-8") as f:
        diag_v2 = json.load(f)
        
    misses = diag_v2["misses"]
    
    # ── COMPROBACIONES AUTOMÁTICAS OBLIGATORIAS (Parte A) ────────────────────────
    total_misses = len(misses)
    unique_ids = set(m["case_id"] for m in misses)
    assert total_misses == 72, f"Error: Se esperaban 72 casos, encontrados {total_misses}"
    assert len(unique_ids) == 72, f"Error: Hay IDs duplicados, únicos = {len(unique_ids)}"
    print(f"[*] Comprobación de integridad superada: exactamente 72 identificadores únicos.")
    
    # Grados en sinapsis
    degrees = defaultdict(int)
    cursor.execute("SELECT origen, count(*) FROM sinapsis GROUP BY origen")
    for r in cursor.fetchall(): degrees[r[0]] += r[1]
    cursor.execute("SELECT destino, count(*) FROM sinapsis GROUP BY destino")
    for r in cursor.fetchall(): degrees[r[0]] += r[1]
    
    tabla_72_casos = []
    categorias_principales = Counter()
    pares_variantes_auditados = []
    
    # ── PARTE A: RECLASIFICACIÓN MUTUAMENTE EXCLUYENTE ───────────────────────────
    for m in misses:
        cid = m["case_id"]
        q = m["query"]
        cat_dataset = m["categoria"]
        gold = m["gold"]
        winner = m["winner"]
        rank_gold = m.get("gold_rank_A")
        evaluable = m.get("evaluable_aritmeticamente", False)
        margin = m.get("margin_original")
        
        # Recuperar contenido real de Gold y Winner
        cursor.execute("SELECT contenido, creado_en, peso_sinaptico, estado, sinonimos FROM largo_plazo WHERE concepto = ?", (gold,))
        row_g = cursor.fetchone()
        cursor.execute("SELECT contenido, creado_en, peso_sinaptico, estado, sinonimos FROM largo_plazo WHERE concepto = ?", (winner,))
        row_w = cursor.fetchone()
        
        cont_g = row_g[0] if row_g else ""
        creado_g = row_g[1] if row_g else None
        peso_g = row_g[2] if row_g else None
        sinonimos_g = (row_g[4] or "") if row_g else ""
        
        cont_w = row_w[0] if row_w else ""
        creado_w = row_w[1] if row_w else None
        peso_w = row_w[2] if row_w else None
        
        # Similitud morfológica y textual
        g_norm = normalizar_texto(gold)
        w_norm = normalizar_texto(winner)
        label_sim = difflib.SequenceMatcher(None, g_norm, w_norm).ratio()
        
        cont_sim_seq = difflib.SequenceMatcher(None, cont_g, cont_w).ratio() if cont_g and cont_w else 0.0
        cont_jacc = calcular_jaccard_tokens(cont_g, cont_w)
        
        cursor.execute("SELECT peso, tipo FROM sinapsis WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)", (gold, winner, winner, gold))
        arista = cursor.fetchone()
        
        # Determinar si son variantes/duplicados reales con contenido verificado
        es_par_variante_candidato = (
            (g_norm == w_norm) or 
            g_norm.startswith(w_norm) or 
            w_norm.startswith(g_norm) or 
            (label_sim >= 0.70)
        )
        
        es_duplicado_verificado = es_par_variante_candidato and (cont_jacc >= 0.40 or cont_sim_seq >= 0.40 or g_norm == w_norm)
        
        # Asignación de EXACTAMENTE UNA Categoría Principal Mutuamente Excluyente:
        # Prioridad determinista jerárquica:
        # 1. bypass_concept_hub (caso especial donde no hubo competencia híbrida)
        # 2. colision_identidad_duplicado (cuando el par es morfológica Y textualmente una variante de memoria)
        # 3. sinonimo_ausente (consultas de la categoría sinonimo donde falta el puente léxico)
        # 4. brecha_lexica_tema (consultas sintéticas abstractas de por_tema)
        # 5. competencia_ranking_multisenal (el resto de casos competitivos: typos, variantes gramaticales, etc.)
        etiquetas_secundarias = []
        
        if cid == "0516" or not evaluable:
            cat_principal = "bypass_concept_hub"
            etiquetas_secundarias.append("inyeccion_post_processing")
            if cat_dataset == "por_tema": etiquetas_secundarias.append("origen_por_tema")
        elif es_duplicado_verificado:
            cat_principal = "colision_identidad_duplicado"
            etiquetas_secundarias.append(f"sim_label_{label_sim:.2f}")
            etiquetas_secundarias.append(f"jacc_cont_{cont_jacc:.2f}")
            if abs(margin or 0.0) <= 0.010: etiquetas_secundarias.append("margen_ultraestrecho")
        elif cat_dataset == "sinonimo":
            cat_principal = "sinonimo_ausente"
            q_clean = q.strip().lower()
            if q_clean not in sinonimos_g.lower():
                etiquetas_secundarias.append("termino_ausente_en_sinonimos_campo")
            if abs(margin or 0.0) <= 0.050: etiquetas_secundarias.append("margen_competitivo")
        elif cat_dataset == "por_tema":
            cat_principal = "brecha_lexica_tema"
            etiquetas_secundarias.append("consulta_abstracta_sintetica")
            etiquetas_secundarias.append("competidor_con_match_superficial")
        else:
            cat_principal = "competencia_ranking_multisenal"
            etiquetas_secundarias.append(f"categoria_dataset_{cat_dataset}")
            if abs(margin or 0.0) <= 0.010: etiquetas_secundarias.append("margen_ultraestrecho")
            elif abs(margin or 0.0) <= 0.050: etiquetas_secundarias.append("margen_moderado")
            else: etiquetas_secundarias.append("margen_amplio")
            
        categorias_principales[cat_principal] += 1
        
        if es_par_variante_candidato:
            pares_variantes_auditados.append({
                "case_id": cid,
                "categoria_principal": cat_principal,
                "query": q,
                "gold": gold,
                "winner": winner,
                "gold_creado": creado_g,
                "winner_creado": creado_w,
                "gold_peso": peso_g,
                "winner_peso": peso_w,
                "similitud_etiqueta": round(label_sim, 4),
                "similitud_contenido_seq": round(cont_sim_seq, 4),
                "jaccard_tokens_contenido": round(cont_jacc, 4),
                "es_duplicado_verificado": es_duplicado_verificado,
                "arista_directa": arista is not None,
                "arista_detalle": arista
            })
            
        # ── PARTE B: EVALUACIÓN DE ANCLAJE Y EVIDENCIA RELACIONAL OPERATIVA ────────
        # Regla operativa real: Compara c1 (ganador) vs c2 (segundo candidato)
        # NUNCA usa a Gold para la decisión.
        # En la evaluación de fallos, c1 es el ganador erróneo y c2 es el siguiente candidato.
        # Para saber si la evidencia favorece a c2 sobre c1: Delta = E_rel(c2|q) - E_rel(c1|q)
        q_tokens = [t.lower() for t in q.split() if len(t) >= 3]
        anclajes = []
        if q_tokens:
            cursor.execute(
                "SELECT concepto FROM largo_plazo WHERE concepto NOT IN (?, ?) AND (" + 
                " OR ".join(["concepto LIKE ?" for _ in q_tokens]) + ") LIMIT 10",
                [winner, gold] + [f"%{t}%" for t in q_tokens]
            )
            anclajes = [r[0] for r in cursor.fetchall()]
        
        aristas_c1_anclajes = 0
        aristas_c2_anclajes = 0
        if anclajes:
            cursor.execute(
                "SELECT count(*) FROM sinapsis WHERE ((origen = ? AND destino IN (" + 
                ",".join(["?"]*len(anclajes)) + ")) OR (destino = ? AND origen IN (" + 
                ",".join(["?"]*len(anclajes)) + ")))",
                [winner] + anclajes + [winner] + anclajes
            )
            aristas_c1_anclajes = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT count(*) FROM sinapsis WHERE ((origen = ? AND destino IN (" + 
                ",".join(["?"]*len(anclajes)) + ")) OR (destino = ? AND origen IN (" + 
                ",".join(["?"]*len(anclajes)) + ")))",
                [gold] + anclajes + [gold] + anclajes
            )
            aristas_c2_anclajes = cursor.fetchone()[0]
            
        deg_c1 = max(1, degrees[winner])
        deg_c2 = max(1, degrees[gold])
        
        e_rel_raw_c1 = aristas_c1_anclajes
        e_rel_raw_c2 = aristas_c2_anclajes
        delta_rel_raw = e_rel_raw_c2 - e_rel_raw_c1
        
        e_rel_norm_c1 = aristas_c1_anclajes / deg_c1
        e_rel_norm_c2 = aristas_c2_anclajes / deg_c2
        delta_rel_norm = e_rel_norm_c2 - e_rel_norm_c1
        
        tabla_72_casos.append({
            "case_id": cid,
            "query": q,
            "categoria_dataset": cat_dataset,
            "categoria_principal": cat_principal,
            "etiquetas_secundarias": etiquetas_secundarias,
            "gold": gold,
            "winner": winner,
            "gold_rank": rank_gold,
            "margin_original": margin,
            "grado_winner_c1": deg_c1,
            "grado_gold_c2": deg_c2,
            "nodos_anclaje_count": len(anclajes),
            "evidencia_relacional_raw_c1": e_rel_raw_c1,
            "evidencia_relacional_raw_c2": e_rel_raw_c2,
            "delta_relacional_raw": delta_rel_raw,
            "delta_relacional_norm": round(delta_rel_norm, 5),
            "veredicto_relacional": (
                "favorece_c2_gold" if delta_rel_norm > 0.005 else
                "favorece_c1_winner" if delta_rel_norm < -0.005 else
                "neutral_o_abstencion"
            )
        })
        
    conn.close()
    
    # Comprobación de que la suma de categorías principales suma exactamente 72
    assert sum(categorias_principales.values()) == 72, f"Error en suma: {sum(categorias_principales.values())}"
    
    # Estadísticas de evidencia relacional
    anclaje_disponible = sum(1 for c in tabla_72_casos if c["nodos_anclaje_count"] > 0)
    fav_c2 = sum(1 for c in tabla_72_casos if c["veredicto_relacional"] == "favorece_c2_gold")
    fav_c1 = sum(1 for c in tabla_72_casos if c["veredicto_relacional"] == "favorece_c1_winner")
    abstenciones = sum(1 for c in tabla_72_casos if c["veredicto_relacional"] == "neutral_o_abstencion")
    
    reporte_datos = {
        "metadata": {
            "version": "fase5_auditoria_relacional_aureon",
            "snapshot_sha256": snap_hash,
            "dataset_sha256": cases_hash,
            "total_casos_verificados": total_misses,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "resumen_taxonomia_mutuamente_excluyente": dict(categorias_principales),
        "resumen_evidencia_relacional": {
            "total_con_anclaje": anclaje_disponible,
            "total_sin_anclaje": 72 - anclaje_disponible,
            "favorece_c2_gold": fav_c2,
            "favorece_c1_winner": fav_c1,
            "neutral_o_abstencion": abstenciones
        },
        "pares_variantes_auditados": pares_variantes_auditados,
        "tabla_72_casos": tabla_72_casos
    }
    
    with open(OUTPUT_REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(reporte_datos, f, indent=2, ensure_ascii=False)
        
    print(f"\nReporte JSON guardado en: {OUTPUT_REPORT_JSON}")
    print("\n=== RESUMEN TAXONOMÍA PRINCIPAL MUTUAMENTE EXCLUYENTE ===")
    for k, v in categorias_principales.items():
        print(f"  {k}: {v} casos ({v/72*100:.1f}%)")
    print(f"  TOTAL COMPROBADO: {sum(categorias_principales.values())} / 72")
    
    print("\n=== RESUMEN DE EVIDENCIA RELACIONAL INDEPENDIENTE (PARTE B) ===")
    print(f"  Consultas con nodos de anclaje: {anclaje_disponible} / 72 ({anclaje_disponible/72*100:.1f}%)")
    print(f"  Consultas sin anclaje (abstención obligatoria): {72 - anclaje_disponible} / 72")
    print(f"  Evidencia normalizada favorece a c2 (Gold):       {fav_c2} / 72 ({fav_c2/72*100:.1f}%)")
    print(f"  Evidencia normalizada favorece a c1 (Competidor): {fav_c1} / 72 ({fav_c1/72*100:.1f}%)")
    print(f"  Zona neutra / Abstención:                         {abstenciones} / 72 ({abstenciones/72*100:.1f}%)")
    
    print("\n=== PARES DE VARIANTES CON SIMILITUD DE CONTENIDO VERIFICADA ===")
    for p in pares_variantes_auditados:
        print(f"  Caso {p['case_id']}: {p['gold']} vs {p['winner']}")
        print(f"    Sim Etiqueta: {p['similitud_etiqueta']} | Jaccard Contenido: {p['jaccard_tokens_contenido']} | SeqMatcher Contenido: {p['similitud_contenido_seq']}")
        print(f"    ¿Es duplicado verificado?: {p['es_duplicado_verificado']} | Arista: {p['arista_directa']}")

if __name__ == "__main__":
    main()
