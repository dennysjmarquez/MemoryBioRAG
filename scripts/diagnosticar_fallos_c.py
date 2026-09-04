#!/usr/bin/env python3
"""
scripts/diagnosticar_fallos_c.py

Diagnóstico causal quirúrgico de los 39 fallos de la Corrida C
(BIORAG_HUB_ENABLED=1, BIORAG_WORDNET_ENABLED=0).
"""

import os
import sys
import json
import re
import sqlite3
import shutil

# Configurar entorno para Corrida C
os.environ["BIORAG_HUB_ENABLED"] = "1"
os.environ["BIORAG_WORDNET_ENABLED"] = "0"
os.environ["BIORAG_NO_LOG"] = "1"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG

SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
CASOS_PATH = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
TEMP_DB = "/tmp/biorag_diag_c.db"


def main():
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"Error: Snapshot no encontrado en {SNAPSHOT_PATH}")
        sys.exit(1)

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)
    shutil.copyfile(SNAPSHOT_PATH, TEMP_DB)

    print(f"Iniciando diagnóstico sobre copia de snapshot: {TEMP_DB}")
    cerebro = SQLiteMemoryBioRAG(db_path=TEMP_DB)

    # Cargar casos QA
    casos = []
    with open(CASOS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                casos.append(json.loads(line))

    def resolver_gold(gold_label):
        mapeo = {
            "lección:_guardar_todo_lo_importante_inmediatamente,_no_esperar": "lección:_guardar_todo_lo_importante_inmediatamente_y_no_esperar",
            "plugin_biorag-remember_v8.4_-_solo_session.idle,_sin_conteo_de_edits": "plugin_biorag-remember_v8.4_-_solo_session.idle_y_sin_conteo_de_edits",
            "plugin_v7.1_fix:_session.idle_es_un_event,_no_un_hook": "plugin_v7.1_fix:_session.idle_es_un_event_y_no_un_hook",
        }
        return mapeo.get(gold_label, gold_label)

    # Detectar queries ambiguas
    queries_por_texto = {}
    for c in casos:
        q = c["query"].strip().lower()
        exp = c.get("expected")
        if exp and c.get("categoria") not in ["negativo", "dormido"]:
            queries_por_texto.setdefault(q, set()).add(resolver_gold(exp))
    
    queries_ambiguas = {q for q, exps in queries_por_texto.items() if len(exps) > 1}

    fallos_diag = []
    categorias_fallos = {
        "AMBIGUEDAD_1_TOKEN": [],
        "RANKING_DROP_TOP50": [],
        "NO_RECUPERADO_TOP50": []
    }

    print("Evaluando casos...")
    for idx, caso in enumerate(casos):
        cat = caso.get("categoria", "")
        if cat in ["negativo", "dormido"]:
            continue

        query = caso["query"]
        if query.strip().lower() in queries_ambiguas:
            # Reclasificada como ambigua, no cuenta como fallo de retrieval regular
            continue

        expected = caso.get("expected") or caso.get("concepto_esperado")
        if not expected:
            continue

        if isinstance(expected, list):
            expected_list = [resolver_gold(e) for e in expected]
        else:
            expected_list = [resolver_gold(expected)]

        # Buscar top 5
        res_top5, _ = cerebro.buscar_por_frase(query, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
        conceptos_top5 = [r[0] for r in res_top5]

        match_top5 = any(exp in conceptos_top5 for exp in expected_list)

        if not match_top5:
            # 1. Búsqueda extendida a 50
            res_top50, _ = cerebro.buscar_por_frase(query, profundidad="activos", limite=50, ignore_peso_sinaptico=True)
            conceptos_top50 = [r[0] for r in res_top50]

            rank_en_top50 = None
            gold_match = None
            gold_score = 0.0
            for r_idx, r in enumerate(res_top50):
                if r[0] in expected_list:
                    rank_en_top50 = r_idx + 1
                    gold_match = r[0]
                    gold_score = r[4]
                    break

            # 2. Verificar existencia en BD
            cursor = cerebro.cursor
            cursor.execute("SELECT id, concepto, estado FROM largo_plazo WHERE concepto = ?", (expected_list[0],))
            nodo_info = cursor.fetchone()

            # 3. Diagnóstico de categoría
            palabras_query = query.strip().split()
            es_1_palabra = len(palabras_query) == 1

            if es_1_palabra and rank_en_top50 is not None:
                tipo_fallo = "AMBIGUEDAD_1_TOKEN"
            elif rank_en_top50 is not None:
                tipo_fallo = "RANKING_DROP_TOP50"
            else:
                tipo_fallo = "NO_RECUPERADO_TOP50"

            diag_item = {
                "id": caso.get("id", idx + 1),
                "categoria": cat,
                "query": query,
                "expected": expected_list[0] if len(expected_list) == 1 else expected_list,
                "tipo_fallo": tipo_fallo,
                "nodo_existe_db": bool(nodo_info),
                "nodo_estado_db": nodo_info[2] if nodo_info else "INEXISTENTE",
                "rank_en_top50": rank_en_top50,
                "gold_score": round(gold_score, 4) if gold_score else 0.0,
                "top1_concepto": conceptos_top5[0] if conceptos_top5 else None,
                "top1_score": round(res_top5[0][4], 4) if res_top5 else 0.0,
                "top5_retornados": [r[0] for r in res_top5]
            }

            fallos_diag.append(diag_item)
            categorias_fallos[tipo_fallo].append(diag_item)

    print("\n" + "="*80)
    print(f"DIAGNÓSTICO CAUSAL COMPLETO: {len(fallos_diag)} FALLOS ENCONTRADOS")
    print("="*80)

    print(f"\n1. RANKING_DROP_TOP50 ({len(categorias_fallos['RANKING_DROP_TOP50'])} casos):")
    print("   -> El nodo Gold SÍ fue generado en el pool (Top 50), pero quedó desplazado al puesto 6..50.")
    print("   -> Solución: Ajuste fino de discriminación / reranking.")
    for item in categorias_fallos["RANKING_DROP_TOP50"]:
        id_str = str(item['id'])
        print(f"   [{id_str:>4s}] [{item['categoria']:18s}] '{item['query']}'")
        print(f"          Expected: {item['expected']} (Rank #{item['rank_en_top50']}, Score: {item['gold_score']})")
        print(f"          Top #1:   {item['top1_concepto']} (Score: {item['top1_score']})")

    print(f"\n2. AMBIGUEDAD_1_TOKEN ({len(categorias_fallos['AMBIGUEDAD_1_TOKEN'])} casos):")
    print("   -> Queries de 1 sola palabra genérica donde múltiples nodos compiten por el mismo término.")
    for item in categorias_fallos["AMBIGUEDAD_1_TOKEN"]:
        id_str = str(item['id'])
        print(f"   [{id_str:>4s}] [{item['categoria']:18s}] '{item['query']}'")
        print(f"          Expected: {item['expected']} (Rank #{item['rank_en_top50']}, Score: {item['gold_score']})")
        print(f"          Top #1:   {item['top1_concepto']} (Score: {item['top1_score']})")

    print(f"\n3. NO_RECUPERADO_TOP50 ({len(categorias_fallos['NO_RECUPERADO_TOP50'])} casos):")
    print("   -> El nodo Gold NO apareció en los primeros 50 candidatos (Fallo de Candidate Generation).")
    for item in categorias_fallos["NO_RECUPERADO_TOP50"]:
        id_str = str(item['id'])
        print(f"   [{id_str:>4s}] [{item['categoria']:18s}] '{item['query']}'")
        print(f"          Expected: {item['expected']} | Estado BD: {item['nodo_estado_db']}")
        print(f"          Top #1:   {item['top1_concepto']} (Score: {item['top1_score']})")

    cat_summary = {}
    for item in fallos_diag:
        c = item["categoria"]
        cat_summary[c] = cat_summary.get(c, 0) + 1

    print("\n" + "-"*80)
    print("DESGLOSE POR CATEGORÍA DEL QA:")
    for c, count in sorted(cat_summary.items(), key=lambda x: -x[1]):
        print(f"   - {c:22s}: {count} fallos")

    print(f"\nTOTAL FALLOS ANALIZADOS: {len(fallos_diag)}")
    print("="*80)

    out_file = os.path.join(BASE_DIR, "scripts", "diagnostico_fallos_c.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_fallos": len(fallos_diag),
            "desglose_tipos": {k: len(v) for k, v in categorias_fallos.items()},
            "desglose_categorias": cat_summary,
            "detalles": fallos_diag
        }, f, indent=2, ensure_ascii=False)
    print(f"Reporte detallado guardado en: {out_file}")

    cerebro.conn.close()
    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
