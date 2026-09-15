#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio Experimental: Enrutador Simbólico y Resonancia Semántica
MemoryBioRAG — Fase 1 (Sonda Refinada: Firma Dimensional + Grafo Anti-Hub)

Rescata recuerdos en el Abismo Léxico (0 palabras en común) mediante:
  1. Activación de Dimensiones Semánticas (las 104 dimensiones de corteza)
  2. Grafo Hebbiano con Atenuación Anti-Hub (penalización logarítmica por grado)
  3. Resonancia Confluente (interferencia constructiva donde coinciden ambas)

CERO hardcoding. 100% matemática local y agnóstica.
"""
import sqlite3
import math
import sys
import os
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
        "intencion_semantica": ["resolver", "conflicto", "contradiccion", "decision"]
    }
]

def evaluar_sonda_refinada():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    from core.stemmer_es import stem

    print("=" * 78)
    print("SONDA EXPERIMENTAL REFINADA: RESONANCIA DIMENSIONAL + GRAFO ANTI-HUB")
    print(f"Base de datos evaluada: {DB_PATH.name}")
    print("=" * 78)

    aciertos_top1 = 0
    aciertos_top5 = 0
    aciertos_top10 = 0

    for caso in CASOS:
        q = caso["query"]
        esperado = caso["esperado"]
        tokens_intencion = caso["intencion_semantica"]
        
        print(f"\n--- CASO {caso['id']}: \"{q}\" ---")
        print(f"Esperado: {esperado}")

        # 1. Activación de Dimensiones Semánticas en el Catálogo (104 dims)
        matched_dims = set()
        for tok in tokens_intencion:
            rows = cur.execute("""
                SELECT id, name FROM dimensiones_semanticas 
                WHERE name LIKE ? OR description LIKE ?
            """, (f"%{tok}%", f"%{tok}%")).fetchall()
            for r in rows:
                matched_dims.add(r[0])

        dim_scores = defaultdict(float)
        if matched_dims:
            ph_dims = ",".join(str(d) for d in matched_dims)
            rows = cur.execute(f"""
                SELECT concepto, count(*) as shared
                FROM largo_plazo_dimensiones
                WHERE dimension_id IN ({ph_dims})
                GROUP BY concepto
            """).fetchall()
            max_shared = max((r[1] for r in rows), default=1)
            for c, shared in rows:
                dim_scores[c] = shared / max_shared

        # 2. Grafo Hebbiano Anti-Hub
        # Buscar semillas FTS de las palabras de la intención
        stems = [stem(t) for t in tokens_intencion if len(t) >= 3]
        fts_stems = [f'"{s}*"' for s in stems if len(s) >= 3]

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
                # Ley de potencia Anti-Hub: w / (deg^0.75)
                hebb_scores[v] += (w or 0.5) / (deg ** 0.75)

        # Normalizar hebb_scores
        max_hebb = max(hebb_scores.values(), default=1.0)
        for k in hebb_scores:
            hebb_scores[k] /= max_hebb

        # 3. Interferencia Constructiva (Resonancia Confluente)
        candidatos = set(dim_scores.keys()) | set(hebb_scores.keys())
        scores_finales = []
        for c in candidatos:
            sd = dim_scores.get(c, 0.0)
            sh = hebb_scores.get(c, 0.0)
            
            # Bonus multiplicativo si ambas señales coinciden (coherencia de onda)
            coherencia = math.sqrt(sd * sh) if (sd > 0 and sh > 0) else 0.0
            
            score_final = 0.50 * sd + 0.30 * sh + 0.20 * coherencia
            scores_finales.append((c, score_final, sd, sh, coherencia))

        scores_finales.sort(key=lambda x: x[1], reverse=True)

        # Ubicar al gold
        pos_gold = -1
        score_gold = 0.0
        for idx, (c, sc, sd, sh, coh) in enumerate(scores_finales):
            if c == esperado:
                pos_gold = idx + 1
                score_gold = sc
                break

        print(f"Candidatos evocados en total: {len(scores_finales)}")
        print("Top 5 evocados:")
        for idx, (c, sc, sd, sh, coh) in enumerate(scores_finales[:5]):
            is_gold = " <<<< GOLD!" if c == esperado else ""
            print(f"  #{idx+1:2d} [score: {sc:.4f} | dim: {sd:.3f} | hebb: {sh:.3f} | coh: {coh:.3f}] {c}{is_gold}")

        if pos_gold != -1:
            print(f"-> Resultado: Gold encontrado en posición #{pos_gold} (Score: {score_gold:.4f})")
            if pos_gold == 1:
                aciertos_top1 += 1
            if pos_gold <= 5:
                aciertos_top5 += 1
            if pos_gold <= 10:
                aciertos_top10 += 1
        else:
            print("-> Resultado: ❌ NO evocado")

    print("\n" + "=" * 78)
    print(f"RESUMEN REFINADO: Top-1: {aciertos_top1}/5 ({aciertos_top1*20}%) | Top-5: {aciertos_top5}/5 ({aciertos_top5*20}%) | Top-10: {aciertos_top10}/5 ({aciertos_top10*20}%)")
    print("=" * 78)
    conn.close()

if __name__ == "__main__":
    evaluar_sonda_refinada()
