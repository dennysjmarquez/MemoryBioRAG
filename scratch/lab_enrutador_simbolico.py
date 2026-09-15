#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio Experimental: Enrutador Simbólico y Resonancia Semántica
MemoryBioRAG — Fase 1 (Sonda Aislada)

Mide la capacidad de recuperar recuerdos en el Abismo Léxico (0 palabras en común)
mediante la intersección de 3 fuentes biológicas:
  1. Dimensiones Semánticas (los 13 ejes de corteza / 104 dimensiones)
  2. Grupos Semánticos Universales (WordNet lexnames en nodo_grupos_semanticos)
  3. Difusión por Grafo Sináptico Hebbiano (sinapsis directas)

CERO hardcoding. 100% matemática local y universal.
"""
import sqlite3
import math
import sys
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "snapshots" / "qa_escape_qcr_20260811.db"

CASOS = [
    {
        "id": 1,
        "query": "qué hacía antes de ser programador",
        "esperado": "historia_tasajera_fumigador_rufino",
        "tokens_clave": ["hacia", "antes", "programador"]
    },
    {
        "id": 2,
        "query": "metí un cambio y todo se rompió",
        "esperado": "leccion_control_flujo_codigo_preexistente",
        "tokens_clave": ["meti", "cambio", "rompio"]
    },
    {
        "id": 3,
        "query": "toqué algo que andaba bien y dejó de andar",
        "esperado": "leccion_control_flujo_codigo_preexistente",
        "tokens_clave": ["toque", "andaba", "bien", "dejo", "andar"]
    },
    {
        "id": 4,
        "query": "cómo sobrevivía económicamente antes de la tecnología",
        "esperado": "historia_tasajera_fumigador_rufino",
        "tokens_clave": ["sobrevivia", "economicamente", "antes", "tecnologia"]
    },
    {
        "id": 5,
        "query": "dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?",
        "esperado": "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad",
        "tokens_clave": ["dos", "modelos", "acuerdo", "resuelvo"]
    }
]

def evaluar_sonda():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    from core.clasificador_wordnet import clasificar_texto
    from core.stemmer_es import stem

    print("=" * 75)
    print("SONDA EXPERIMENTAL: ENRUTAMIENTO SIMBÓLICO MULTI-SEÑAL")
    print(f"Base de datos evaluada: {DB_PATH}")
    print("=" * 75)

    aciertos_top1 = 0
    aciertos_top5 = 0

    for caso in CASOS:
        q = caso["query"]
        esperado = caso["esperado"]
        print(f"\n--- CASO {caso['id']}: '{q}' ---")
        print(f"Esperado: {esperado}")

        # 1. Señal A: Grupos Semánticos (WordNet Lexnames) de la query
        wn_info = clasificar_texto(q)
        query_lexnames = set()
        for tok, lex_set in wn_info.items():
            query_lexnames.update(lex_set)

        grupo_scores = defaultdict(float)
        if query_lexnames:
            ph_ln = ",".join("?" * len(query_lexnames))
            gids = [r[0] for r in cur.execute(f"SELECT id FROM grupos_semanticos WHERE nombre IN ({ph_ln})", tuple(query_lexnames)).fetchall()]
            if gids:
                ph_gids = ",".join(str(g) for g in gids)
                rows = cur.execute(f"""
                    SELECT concepto, count(DISTINCT grupo_id) as match_cnt, count(DISTINCT palabra) as words_cnt
                    FROM nodo_grupos_semanticos
                    WHERE grupo_id IN ({ph_gids})
                    GROUP BY concepto
                """).fetchall()
                # Normalizar por tamaño del concepto
                for conc, match_cnt, words_cnt in rows:
                    grupo_scores[conc] = match_cnt / math.sqrt(len(gids) * (words_cnt + 1))

        # 2. Señal B: Stem FTS y salto Hebbiano a vecinos de 1er orden
        # Extraer stems de tokens relevantes (longitud >= 3)
        tokens_raw = [t for t in q.lower().split() if len(t) >= 3 and t not in {"que", "los", "las", "con", "por", "para", "una", "uno", "del"}]
        stems = [stem(t) for t in tokens_raw]
        fts_stems = [f'"{s}*"' for s in stems if len(s) >= 3]

        stem_hits = set()
        if fts_stems:
            fts_expr = " OR ".join(fts_stems)
            rows = cur.execute(f"""
                SELECT l.concepto 
                FROM largo_plazo_fts f 
                JOIN largo_plazo l ON l.rowid=f.rowid 
                WHERE largo_plazo_fts MATCH ? AND l.estado='activo'
                LIMIT 30
            """, (fts_expr,)).fetchall()
            stem_hits = {r[0] for r in rows}

        # Propagación Hebbiana de 1 salto desde stem_hits con penalización por grado (Anti-Hub)
        hebbian_scores = defaultdict(float)
        for seed in stem_hits:
            hebbian_scores[seed] += 0.5
            edges = cur.execute("""
                SELECT destino, peso FROM sinapsis WHERE origen = ?
                UNION
                SELECT origen, peso FROM sinapsis WHERE destino = ?
            """, (seed, seed)).fetchall()
            deg_seed = len(edges) or 1
            for vecino, peso in edges:
                # Penalización por grado del vecino (evita que los super-hubs capturen todo)
                deg_vecino = cur.execute("SELECT count(*) FROM sinapsis WHERE origen=? OR destino=?", (vecino, vecino)).fetchone()[0] or 1
                hebbian_scores[vecino] += (peso or 0.5) / (math.log2(deg_vecino + 2))

        # 3. Integración de Señales Simbólicas
        # Candidatos que aparecen en al menos una de las fuentes
        candidatos = set(grupo_scores.keys()) | set(hebbian_scores.keys())
        
        scores_finales = []
        for c in candidatos:
            sg = grupo_scores.get(c, 0.0)
            sh = hebbian_scores.get(c, 0.0)
            
            # Puntuación combinada
            score = 0.5 * sg + 0.5 * (sh / 10.0)
            scores_finales.append((c, score, sg, sh))

        scores_finales.sort(key=lambda x: x[1], reverse=True)

        # Ver posición del gold
        pos_gold = -1
        score_gold = 0.0
        for idx, (c, score, sg, sh) in enumerate(scores_finales):
            if c == esperado:
                pos_gold = idx + 1
                score_gold = score
                break

        print(f"Total candidatos evocados: {len(scores_finales)}")
        print(f"Top 5 evocados:")
        for idx, (c, score, sg, sh) in enumerate(scores_finales[:5]):
            is_gold = " <<<< GOLD!" if c == esperado else ""
            print(f"  #{idx+1:2d} [score: {score:.4f} | WN: {sg:.4f} | Hebb: {sh:.4f}] {c}{is_gold}")

        if pos_gold != -1:
            print(f"Resultado: Encontrado en posición #{pos_gold} (Score: {score_gold:.4f})")
            if pos_gold == 1:
                aciertos_top1 += 1
            if pos_gold <= 5:
                aciertos_top5 += 1
        else:
            print(f"Resultado: ❌ NO evocado entre {len(scores_finales)} candidatos")

    print("\n" + "=" * 75)
    print(f"RESUMEN SONDA: Top-1: {aciertos_top1}/5 ({aciertos_top1*20}%) | Top-5: {aciertos_top5}/5 ({aciertos_top5*20}%)")
    print("=" * 75)
    conn.close()

if __name__ == "__main__":
    evaluar_sonda()
