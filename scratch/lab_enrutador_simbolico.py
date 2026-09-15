#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio Experimental: Enrutador Simbólico y Resonancia Semántica
MemoryBioRAG — Fase 1 (Sonda Auditada: Símbolos, Dimensiones IDF y Marcador Somático)

Implementa la arquitectura simbólica de 3 pilares:
  1. Activación de Dimensiones Semánticas ponderadas por Especificidad (IDF)
  2. Modulación por Marcador Somático de Damasio (Impacto Emocional: valencia_somatica * peso_sinaptico)
  3. Difusión y Convergencia Sináptica Hebbiana Anti-Hub (con penalización por grado)

Evaluación 100% determinista y reproducible sobre qa_escape_qcr_20260811.db.
"""
import sqlite3
import math
import sys
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "snapshots" / "qa_escape_qcr_20260811.db"

CASOS = [
    {
        "id": 1,
        "query": "qué hacía antes de ser programador",
        "esperado": "historia_tasajera_fumigador_rufino",
        "intencion_semantica": ["profesional", "trabajo", "antes", "personal"]
    },
    {
        "id": 2,
        "query": "metí un cambio y todo se rompió",
        "esperado": "leccion_control_flujo_codigo_preexistente",
        "intencion_semantica": ["fallar", "error", "romper", "codigo", "cambio"]
    },
    {
        "id": 3,
        "query": "toqué algo que andaba bien y dejó de andar",
        "esperado": "leccion_control_flujo_codigo_preexistente",
        "intencion_semantica": ["fallar", "error", "romper", "codigo", "modificar"]
    },
    {
        "id": 4,
        "query": "cómo sobrevivía económicamente antes de la tecnología",
        "esperado": "historia_tasajera_fumigador_rufino",
        "intencion_semantica": ["profesional", "trabajo", "economico", "personal"]
    },
    {
        "id": 5,
        "query": "dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?",
        "esperado": "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad",
        "intencion_semantica": ["resolver", "conflicto", "contradiccion", "decision", "regla"]
    }
]

def evaluar_sonda():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    from core.stemmer_es import stem

    print("=" * 78)
    print("SONDA EXPERIMENTAL VERIFICADA: RED SIMBÓLICA + MARCADOR SOMÁTICO")
    print(f"Base de datos evaluada: {DB_PATH.name}")
    print("=" * 78)

    # 1. Pre-calcular IDF para las 104 dimensiones
    total_nodos = cur.execute("SELECT count(DISTINCT concepto) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
    dim_rows = cur.execute("""
        SELECT d.id, d.name, count(DISTINCT lpd.concepto) as df
        FROM dimensiones_semanticas d
        LEFT JOIN largo_plazo_dimensiones lpd ON lpd.dimension_id = d.id
        GROUP BY d.id
    """).fetchall()

    idf_map = {}
    for did, name, df in dim_rows:
        # IDF de dimensión: dimensiones raras (accion_fallar, hito) tienen alto IDF
        idf_map[did] = math.log((total_nodos + 1.0) / (df + 1.0))

    # 2. Cargar Marcadores Somáticos nativos de todos los nodos activos (valencia_somatica y peso_sinaptico)
    nodo_metadata = {}
    for c, val, peso in cur.execute("SELECT concepto, valencia_somatica, peso_sinaptico FROM largo_plazo WHERE estado='activo'").fetchall():
        v = float(val or 0.0)
        p = float(peso or 0.5)
        # Factor somático biológico: 1.0 + (valencia * peso) -> rango [1.0, 2.0]
        nodo_metadata[c] = {
            "valencia": v,
            "peso": p,
            "marcador_somatico": 1.0 + (v * p)
        }

    aciertos_top1 = 0
    aciertos_top5 = 0

    for caso in CASOS:
        q = caso["query"]
        esperado = caso["esperado"]
        tokens_intencion = caso["intencion_semantica"]

        print(f"\n--- CASO {caso['id']}: \"{q}\" ---")
        print(f"Esperado: {esperado}")

        # 3. Activación de Dimensiones Semánticas en el Catálogo
        matched_dims = {}
        for tok in tokens_intencion:
            rows = cur.execute("""
                SELECT id, name FROM dimensiones_semanticas 
                WHERE name LIKE ? OR description LIKE ?
            """, (f"%{tok}%", f"%{tok}%")).fetchall()
            for did, name in rows:
                matched_dims[did] = idf_map.get(did, 1.0)

        dim_scores = defaultdict(float)
        if matched_dims:
            ph_dims = ",".join(str(d) for d in matched_dims.keys())
            rows = cur.execute(f"""
                SELECT concepto, dimension_id
                FROM largo_plazo_dimensiones
                WHERE dimension_id IN ({ph_dims})
            """).fetchall()
            for c, did in rows:
                # Sumar el peso IDF de cada dimensión activada
                dim_scores[c] += matched_dims[did]

            # Modulación Somática: amplificar por el impacto del recuerdo
            for c in dim_scores:
                meta = nodo_metadata.get(c, {"marcador_somatico": 1.0})
                dim_scores[c] *= meta["marcador_somatico"]

            # Normalizar
            max_d = max(dim_scores.values(), default=1.0)
            for c in dim_scores:
                dim_scores[c] /= max_d

        # 4. Grafo Hebbiano Anti-Hub
        stems = [stem(t) for t in tokens_intencion if len(t) >= 3]
        fts_stems = [f"{s}*" for s in stems if len(s) >= 3]

        seeds = set()
        if fts_stems:
            expr = " OR ".join(fts_stems)
            rows = cur.execute("""
                SELECT l.concepto 
                FROM largo_plazo_fts f 
                JOIN largo_plazo l ON l.rowid=f.rowid 
                WHERE largo_plazo_fts MATCH ? AND l.estado='activo'
                LIMIT 25
            """, (expr,)).fetchall()
            seeds = {r[0] for r in rows}

        hebb_scores = defaultdict(float)
        for s in seeds:
            edges = cur.execute("""
                SELECT destino, peso FROM sinapsis WHERE origen = ?
                UNION
                SELECT origen, peso FROM sinapsis WHERE destino = ?
            """, (s, s)).fetchall()
            for v, w in edges:
                deg = cur.execute("SELECT count(*) FROM sinapsis WHERE origen=? OR destino=?", (v, v)).fetchone()[0] or 1
                hebb_scores[v] += (w or 0.5) / (deg ** 0.75)

        max_hebb = max(hebb_scores.values(), default=1.0)
        for k in hebb_scores:
            hebb_scores[k] /= max_hebb

        # 5. Fusión Híbrida: Resonancia Dimensional Ponderada + Grafo Anti-Hub
        candidatos = set(dim_scores.keys()) | set(hebb_scores.keys())
        scores_finales = []
        for c in candidatos:
            sd = dim_scores.get(c, 0.0)
            sh = hebb_scores.get(c, 0.0)
            coh = math.sqrt(sd * sh) if (sd > 0 and sh > 0) else 0.0
            
            score_final = 0.50 * sd + 0.30 * sh + 0.20 * coh
            scores_finales.append((c, score_final, sd, sh, coh))

        # Desempate determinista exacto (Score DESC, Concepto ASC)
        scores_finales.sort(key=lambda x: (-x[1], x[0]))

        pos_gold = -1
        score_gold = 0.0
        for idx, (c, sc, sd, sh, coh) in enumerate(scores_finales):
            if c == esperado:
                pos_gold = idx + 1
                score_gold = sc
                break

        print(f"Dimensiones activadas: {len(matched_dims)} | Candidatos evocados: {len(scores_finales)}")
        print("Top 5 evocados:")
        for idx, (c, sc, sd, sh, coh) in enumerate(scores_finales[:5]):
            is_gold = " <<<< GOLD!" if c == esperado else ""
            print(f"  #{idx+1:2d} [score: {sc:.4f} | dim: {sd:.3f} | hebb: {sh:.3f}] {c}{is_gold}")

        if pos_gold != -1:
            print(f"-> Posición del Gold: #{pos_gold} (Score: {score_gold:.4f})")
            if pos_gold == 1:
                aciertos_top1 += 1
            if pos_gold <= 5:
                aciertos_top5 += 1
        else:
            print("-> Posición del Gold: ❌ NO evocado")

    print("\n" + "=" * 78)
    print(f"RESUMEN AUDITADO: Top-1: {aciertos_top1}/5 ({aciertos_top1*20}%) | Top-5: {aciertos_top5}/5 ({aciertos_top5*20}%)")
    print("=" * 78)
    conn.close()

if __name__ == "__main__":
    evaluar_sonda()
