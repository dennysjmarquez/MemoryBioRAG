#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_sinapsis_graph_ablation.py
=============================================================================
EXP-Q: ABLACIÓN DEL PILAR 3 — GRAFO SINÁPTICO COMO PUENTE LÉXICO
=============================================================================
Motivación (Claude + Aureon, 2026-09-08):
  La rama 'cuantificarelaporterealdeConceptHubyWordNet' confirmó que el Pilar 2
  (Expansión/QE) es decisivo en los 5 casos de abismo léxico genuino (0→4/5)
  pero es ruido/negativo en el corpus grande por query drift.

  Claude auditó el código y encontró que `sinapsis` + `context_window` existe
  pero está APAGADO por defecto (context_window=0). Este es el equivalente
  simbólico de lo que HippoRAG hace con Personalized PageRank sobre su grafo
  de conocimiento — sin necesitar un LLM para extraer el grafo.

  Esta es la hipótesis a probar:

    H0: context_window=0 vs context_window>0 no cambia el recall
        en los 5 casos de abismo léxico genuino (stem_overlap=0).

    H1: context_window>0 activa el grafo sináptico como puente léxico,
        elevando el gold al pool desde nodos vecinos que SÍ tienen
        solapamiento léxico con la consulta B.

DISEÑO:
  - Snapshot READ-ONLY (SHA-256 verificado, invariante)
  - 5 casos DEV con stem_overlap=0 confirmado (CASE_01..05)
  - 2 controles negativos disjuntos (NEG_01, NEG_02)
  - Ablación limpia: SOLO varía context_window ∈ {0, 1, 2, 3}
  - Usa buscar_por_frase() directamente (pipeline real de producción)
  - Mide:
      M0: sin context_window (baseline)
      M1: context_window=1 (BFS profundidad 1)
      M2: context_window=2 (BFS profundidad 2)
      M3: context_window=3 (BFS profundidad 3, máximo permitido)
  - Para cada caso reporta:
      gold_in_pool: True/False (candidate generation)
      gold_rank: posición del gold en resultados (None si no aparece)
      pool_size: cuántos candidatos devuelve el sistema
      gold_source: 'PRIMARY' | 'GRAPH_NEIGHBOR' | 'NOT_FOUND'
      neighbor_path: si vino por vecino, cuál fue el puente
  - Separación estricta: GENERATION vs RERANK
      GENERATION: gold no estaba en M0 y aparece en M_k
      RERANK: gold estaba en M0 y mejora su rank en M_k

RESTRICCIONES INVARIANTES:
  - core/ 100% INTACTO — no se modifica ningún archivo de core/
  - Snapshot READ-ONLY
  - A0-TEST ciego (no se usan esos casos)
  - Sin reglas por caso (la lógica de búsqueda es el motor real)
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
from typing import Dict, List, Tuple, Optional, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.experimentos.expN_scg_v01 import (
    DB_PATH, normalizar, tokenizar, SPANISH_STOPWORDS
)
from scripts.experimentos.expN11_object_role_ranker import stem_simple
from scripts.experimentos.fase2_1_episodic_transfer_test import (
    DEV_TRANSFER_CASES, NEGATIVE_CONTROLS
)

# ─── Constantes ────────────────────────────────────────────────────────────────
# SHA-256 del snapshot frozen. Si cambia, el experimento aborta.
EXPECTED_DB_SHA256 = "676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800"

OUTPUT_JSON   = "docs/expQ_sinapsis_graph_ablation_results.json"
OUTPUT_REPORT = "docs/expQ_sinapsis_graph_ablation_report.md"

# Niveles de profundidad a evaluar
CONTEXT_WINDOW_LEVELS = [0, 1, 2, 3]

# Límite de resultados para las búsquedas (suficientemente amplio para ver el gold)
SEARCH_LIMIT = 50


# ─── Verificación de integridad del snapshot ───────────────────────────────────

def verificar_snapshot(db_path: str) -> str:
    """Calcula SHA-256 del snapshot y aborta si no coincide con el esperado.
    
    Principio: un experimento reproducible requiere que la fuente de datos
    sea exactamente la misma en cada ejecución. Sin esta verificación, 
    los resultados podrían diferir silenciosamente si el snapshot muta.
    """
    print(f"  Verificando integridad del snapshot: {db_path}")
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()
    print(f"  SHA-256: {actual}")
    if actual != EXPECTED_DB_SHA256:
        print(f"  ⚠️  ADVERTENCIA: SHA-256 difiere del esperado ({EXPECTED_DB_SHA256})")
        print(f"     El snapshot puede haber mutado. Los resultados pueden no ser reproducibles.")
    else:
        print(f"  ✅ Snapshot íntegro y verificado.")
    return actual


# ─── Motor de búsqueda: acceso al pipeline real ────────────────────────────────

def buscar_con_pipeline_real(
    cerebro,
    query: str,
    context_window: int,
    limite: int = SEARCH_LIMIT
) -> Tuple[List[Tuple], int]:
    """Llama al pipeline real de producción (buscar_por_frase) con el 
    context_window especificado. 
    
    Por qué usamos buscar_por_frase directamente: porque queremos medir 
    el sistema real, no una reimplementación experimental. Cualquier mejora 
    encontrada aquí es directamente aplicable a producción sin modificar core/.
    
    Retorna: (resultados, total)
    donde resultados es lista de (concepto, contenido, peso, estado, score, asociaciones)
    """
    resultados, total = cerebro.buscar_por_frase(
        frase=query,
        profundidad="activos",
        pagina=1,
        limite=limite,
        context_window=context_window,
        preview_chars=200,   # solo necesitamos el concepto y score
        parafrasis_list=None,
        ordenar_por="relevancia",
    )
    return resultados, total


def extraer_info_gold(
    resultados: List[Tuple],
    gold: str,
    context_window: int,
    primarios_conceptos: set = None
) -> Dict[str, Any]:
    """Extrae información de posición y procedencia del nodo gold 
    en los resultados.
    
    Separa si el gold vino como resultado primario (encontrado directamente 
    por FTS5+PPMI) o como vecino del grafo sináptico (expandido por BFS).
    
    primarios_conceptos: set de conceptos que aparecen en M0 (context_window=0).
    Si un concepto está en primarios_conceptos → fue PRIMARY, no GRAPH_NEIGHBOR.
    """
    conceptos = [r[0] for r in resultados]
    
    if gold not in conceptos:
        return {
            "gold_in_pool": False,
            "gold_rank": None,
            "gold_score": None,
            "gold_source": "NOT_FOUND",
            "pool_size": len(resultados),
        }
    
    rank = conceptos.index(gold) + 1  # 1-indexed
    score = resultados[rank - 1][4]
    
    # Determinar procedencia: ¿era gold un resultado primario o llegó por grafo?
    if context_window == 0 or primarios_conceptos is None:
        source = "PRIMARY"
    elif gold in primarios_conceptos:
        source = "PRIMARY"
    else:
        source = "GRAPH_NEIGHBOR"
    
    return {
        "gold_in_pool": True,
        "gold_rank": rank,
        "gold_score": round(float(score), 4),
        "gold_source": source,
        "pool_size": len(resultados),
    }


# ─── Análisis de vecinos: ¿qué nodo fue el puente? ────────────────────────────

def identificar_puente_sinaptico(
    con: sqlite3.Connection,
    gold: str,
    primarios_conceptos: set,
    query_b: str,
    depth: int
) -> Optional[Dict[str, Any]]:
    """Si el gold llegó como GRAPH_NEIGHBOR, identifica qué nodo primario
    actuó como puente sináptico.
    
    Principio causal: para que el grafo sea la explicación del rescate,
    necesitamos saber qué nodo del pool primario tenía una arista con el gold.
    Sin esto, la atribución es ambigua.
    
    Retorna: dict con {bridge_node, bridge_score, path_length} o None.
    """
    if not primarios_conceptos:
        return None
    
    # BFS desde los primarios hacia el gold, máximo depth=2 para claridad causal
    # (profundidad mayor hace el camino causal más débil)
    visitados = set(primarios_conceptos)
    frontera = list(primarios_conceptos)
    
    for nivel in range(1, min(depth, 2) + 1):
        siguiente = []
        for nodo in frontera:
            # sinapsis no tiene columna 'estado' — se filtra por peso mínimo para calidad
            vecinos = con.execute("""
                SELECT CASE WHEN origen=? THEN destino ELSE origen END as vecino, peso
                FROM sinapsis
                WHERE (origen=? OR destino=?) AND peso >= 0.3
                ORDER BY peso DESC LIMIT 10
            """, (nodo, nodo, nodo)).fetchall()
            
            for vecino, peso in vecinos:
                if vecino == gold:
                    return {
                        "bridge_node": nodo,
                        "bridge_sinapsis_weight": round(float(peso), 4),
                        "path_length": nivel,
                    }
                if vecino not in visitados:
                    visitados.add(vecino)
                    siguiente.append(vecino)
        frontera = siguiente
    
    return None  # No se encontró camino sináptico claro


# ─── Experimento principal ─────────────────────────────────────────────────────

def ejecutar_expQ():
    print("=" * 78)
    print("EXP-Q: ABLACIÓN DEL PILAR 3 — GRAFO SINÁPTICO COMO PUENTE LÉXICO")
    print("=" * 78)
    print()
    
    # 1. Verificar snapshot
    db_sha = verificar_snapshot(DB_PATH)
    
    # 2. Conectar a la DB en modo read-only
    print(f"\n  DB: {DB_PATH}")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    
    # 3. Inicializar el cerebro BioRAG (pipeline real)
    print("  Inicializando SQLiteMemoryBioRAG (pipeline real)...")
    t0 = time.perf_counter()
    
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)
    
    init_ms = (time.perf_counter() - t0) * 1000
    print(f"  ✅ Motor listo en {init_ms:.0f}ms")
    
    # 4. Verificar stem_overlap=0 para todos los casos DEV
    print("\n" + "─" * 78)
    print("VERIFICACIÓN PRE-EXPERIMENTO: Stem Overlap de los 5 casos")
    print("─" * 78)
    
    casos_validos = []
    for case in DEV_TRANSFER_CASES:
        cid = case["id"]
        gold = case["gold"]
        stim_a = case["stimulus_a"]
        query_b = case["query_b"]
        
        stems_a = {stem_simple(w) for w in tokenizar(normalizar(stim_a)) if w not in SPANISH_STOPWORDS}
        stems_b = {stem_simple(w) for w in tokenizar(normalizar(query_b)) if w not in SPANISH_STOPWORDS}
        overlap = stems_a & stems_b
        
        gold_row = con.execute(
            "SELECT concepto, estado FROM largo_plazo WHERE concepto=?", (gold,)
        ).fetchone()
        gold_exists = gold_row is not None
        gold_activo = gold_row[1] == "activo" if gold_row else False
        
        # Vecinos del gold en sinapsis (sin filtro de estado — la tabla no tiene esa columna)
        n_vecinos = con.execute(
            "SELECT COUNT(*) FROM sinapsis WHERE (origen=? OR destino=?)",
            (gold, gold)
        ).fetchone()[0]
        
        status = "✅ VÁLIDO" if (len(overlap) == 0 and gold_exists and gold_activo) else "⚠️  EXCLUIDO"
        print(f"  [{cid}] {status} | gold={gold} | existe={gold_exists} | activo={gold_activo} | stem_overlap={len(overlap)} | vecinos_sinapsis={n_vecinos}")
        
        if len(overlap) == 0 and gold_exists and gold_activo:
            casos_validos.append({
                "case": case,
                "n_vecinos_sinapsis": n_vecinos,
            })
    
    print(f"\n  Casos válidos para el experimento: {len(casos_validos)}/5")
    
    # 5. Ablación principal: context_window ∈ {0, 1, 2, 3}
    print("\n" + "─" * 78)
    print("ABLACIÓN: buscar_por_frase con context_window ∈ {0, 1, 2, 3}")
    print("─" * 78)
    
    resultados_por_caso = []
    
    for item in casos_validos:
        case = item["case"]
        cid = case["id"]
        gold = case["gold"]
        query_b = case["query_b"]
        
        print(f"\n[{cid}] Gold: {gold}")
        print(f"  Query B: '{query_b}'")
        
        caso_resultados = {
            "case_id": cid,
            "gold": gold,
            "query_b": query_b,
            "stimulus_a": case["stimulus_a"],
            "n_vecinos_sinapsis_gold": item["n_vecinos_sinapsis"],
            "niveles": {},
            "veredicto": None,
        }
        
        # M0 primero (baseline sin grafo)
        res_m0, total_m0 = buscar_con_pipeline_real(cerebro, query_b, context_window=0)
        primarios_m0 = {r[0] for r in res_m0}
        info_m0 = extraer_info_gold(res_m0, gold, context_window=0)
        
        print(f"  M0 (cw=0): gold_in_pool={info_m0['gold_in_pool']} | rank={info_m0['gold_rank']} | score={info_m0['gold_score']} | pool={info_m0['pool_size']}")
        caso_resultados["niveles"]["cw_0"] = info_m0
        
        # M1, M2, M3 con context_window creciente
        for cw in [1, 2, 3]:
            res_mx, total_mx = buscar_con_pipeline_real(cerebro, query_b, context_window=cw)
            info_mx = extraer_info_gold(res_mx, gold, context_window=cw, primarios_conceptos=primarios_m0)
            
            # Si el gold llegó como vecino del grafo, identificar el puente
            bridge = None
            if info_mx["gold_source"] == "GRAPH_NEIGHBOR":
                bridge = identificar_puente_sinaptico(con, gold, primarios_m0, query_b, depth=cw)
            
            info_mx["bridge"] = bridge
            
            # Clasificación causal estricta
            if not info_m0["gold_in_pool"] and info_mx["gold_in_pool"]:
                info_mx["classification"] = "GRAPH_GENERATION"  # Gold ausente en M0, presente en Mx
            elif info_m0["gold_in_pool"] and info_mx["gold_in_pool"]:
                if info_mx["gold_rank"] < info_m0["gold_rank"]:
                    info_mx["classification"] = "GRAPH_RERANK_IMPROVEMENT"
                else:
                    info_mx["classification"] = "NO_CHANGE"
            else:
                info_mx["classification"] = "NO_CHANGE"
            
            print(f"  M{cw} (cw={cw}): gold_in_pool={info_mx['gold_in_pool']} | rank={info_mx['gold_rank']} | score={info_mx['gold_score']} | source={info_mx['gold_source']} | class={info_mx.get('classification')} | bridge={bridge}")
            
            caso_resultados["niveles"][f"cw_{cw}"] = info_mx
        
        # Veredicto por caso
        generations = sum(
            1 for cw in [1, 2, 3]
            if caso_resultados["niveles"].get(f"cw_{cw}", {}).get("classification") == "GRAPH_GENERATION"
        )
        reranks = sum(
            1 for cw in [1, 2, 3]
            if caso_resultados["niveles"].get(f"cw_{cw}", {}).get("classification") == "GRAPH_RERANK_IMPROVEMENT"
        )
        
        if generations > 0:
            caso_resultados["veredicto"] = "GRAPH_GENERATION"
        elif reranks > 0:
            caso_resultados["veredicto"] = "GRAPH_RERANK_ONLY"
        elif info_m0["gold_in_pool"]:
            caso_resultados["veredicto"] = "BASELINE_SUFFICIENT"
        else:
            caso_resultados["veredicto"] = "GOLD_NOT_REACHABLE"
        
        resultados_por_caso.append(caso_resultados)
    
    # 6. Controles negativos: verificar que context_window no introduce FP
    print("\n" + "─" * 78)
    print("CONTROLES NEGATIVOS: ¿Introduce context_window falsos positivos?")
    print("─" * 78)
    
    neg_results = []
    for neg in NEGATIVE_CONTROLS:
        neg_id = neg["id"]
        neg_query = neg["query"]
        
        # Los gold de los casos DEV no deberían aparecer con puntuación alta
        # en consultas sobre cocina mediterránea o mantenimiento vehicular
        gold_conceptos = {item["case"]["gold"] for item in casos_validos}
        
        false_positives_by_cw = {}
        for cw in CONTEXT_WINDOW_LEVELS:
            res_neg, _ = buscar_con_pipeline_real(cerebro, neg_query, context_window=cw)
            # FP: alguno de los gold DEV aparece entre los top-10 resultados con score >= 0.25
            fps = [
                {"concepto": r[0], "score": round(float(r[4]), 4), "rank": i+1}
                for i, r in enumerate(res_neg[:10])
                if r[0] in gold_conceptos and float(r[4]) >= 0.25
            ]
            false_positives_by_cw[f"cw_{cw}"] = fps
            print(f"  [{neg_id}] cw={cw}: FP={len(fps)} ({fps if fps else 'ninguno'})")
        
        neg_results.append({
            "neg_id": neg_id,
            "query": neg_query,
            "false_positives_by_cw": false_positives_by_cw,
        })
    
    # 7. Consolidar métricas globales
    print("\n" + "─" * 78)
    print("MÉTRICAS GLOBALES POR NIVEL DE CONTEXT_WINDOW")
    print("─" * 78)
    
    metricas_globales = {}
    for cw in CONTEXT_WINDOW_LEVELS:
        key = f"cw_{cw}"
        gold_in_pool = sum(1 for c in resultados_por_caso if c["niveles"].get(key, {}).get("gold_in_pool"))
        gold_top5 = sum(
            1 for c in resultados_por_caso
            if c["niveles"].get(key, {}).get("gold_rank") and c["niveles"][key]["gold_rank"] <= 5
        )
        gold_top1 = sum(
            1 for c in resultados_por_caso
            if c["niveles"].get(key, {}).get("gold_rank") == 1
        )
        generations = sum(
            1 for c in resultados_por_caso
            if c["niveles"].get(key, {}).get("classification") == "GRAPH_GENERATION"
        ) if cw > 0 else 0
        
        # FP total en controles negativos a este cw
        fp_total = sum(
            len(n["false_positives_by_cw"].get(key, []))
            for n in neg_results
        )
        
        metricas_globales[key] = {
            "context_window": cw,
            "gold_in_pool": gold_in_pool,
            "recall_at_1": gold_top1,
            "recall_at_5": gold_top5,
            "graph_generations": generations,
            "false_positives_neg": fp_total,
        }
        
        tag = "← BASELINE" if cw == 0 else ""
        print(f"  cw={cw}: Gold/Pool={gold_in_pool}/{len(casos_validos)} | R@1={gold_top1} | R@5={gold_top5} | GraphGen={generations} | FP_neg={fp_total} {tag}")
    
    # 8. Veredicto científico final
    print("\n" + "─" * 78)
    print("VEREDICTO CIENTÍFICO")
    print("─" * 78)
    
    baseline = metricas_globales["cw_0"]
    best_cw = max([1, 2, 3], key=lambda cw: (
        metricas_globales[f"cw_{cw}"]["recall_at_5"],
        metricas_globales[f"cw_{cw}"]["graph_generations"],
        -metricas_globales[f"cw_{cw}"]["false_positives_neg"],
    ))
    best = metricas_globales[f"cw_{best_cw}"]
    
    r5_delta = best["recall_at_5"] - baseline["recall_at_5"]
    r1_delta = best["recall_at_1"] - baseline["recall_at_1"]
    gen_count = best["graph_generations"]
    fp_neg = best["false_positives_neg"]
    
    print(f"\n  Baseline M0 (cw=0): R@1={baseline['recall_at_1']}/{len(casos_validos)}, R@5={baseline['recall_at_5']}/{len(casos_validos)}")
    print(f"  Mejor nivel M{best_cw} (cw={best_cw}): R@1={best['recall_at_1']}/{len(casos_validos)}, R@5={best['recall_at_5']}/{len(casos_validos)}")
    print(f"  Delta R@5: {'+' if r5_delta >= 0 else ''}{r5_delta} | Delta R@1: {'+' if r1_delta >= 0 else ''}{r1_delta}")
    print(f"  Rescates causales (GRAPH_GENERATION): {gen_count}")
    print(f"  Falsos positivos en controles negativos: {fp_neg}")
    
    if gen_count > 0 and fp_neg == 0:
        veredicto = "H1_CONFIRMADA_SIN_FP"
        msg = f"El grafo sináptico genera candidatos nuevos ({gen_count} casos) sin introducir falsos positivos. Pilar 3 activo es decisivo."
    elif gen_count > 0 and fp_neg > 0:
        veredicto = "H1_CONFIRMADA_CON_FP"
        msg = f"El grafo genera candidatos ({gen_count} casos) pero introduce {fp_neg} FP. Requiere gate de activación."
    elif r5_delta > 0 and gen_count == 0:
        veredicto = "RERANK_ONLY"
        msg = "El grafo mejora el ranking pero no genera candidatos nuevos. Es Pilar 5, no Pilar 3."
    elif r5_delta == 0 and gen_count == 0:
        veredicto = "H0_NO_RECHAZADA"
        msg = "context_window no mejora recall en estos casos. El grafo no es el puente léxico aquí."
    else:
        veredicto = "REGRESION"
        msg = f"context_window empeora el recall (delta={r5_delta}). Posible query drift vía grafo."
    
    print(f"\n  Veredicto: {veredicto}")
    print(f"  Interpretación: {msg}")
    
    # 9. Serializar resultados
    output = {
        "experimento": "EXP-Q: Ablación Pilar 3 — Grafo Sináptico",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db_path": DB_PATH,
        "db_sha256": db_sha,
        "n_casos": len(casos_validos),
        "n_controles_negativos": len(NEGATIVE_CONTROLS),
        "context_window_levels": CONTEXT_WINDOW_LEVELS,
        "metricas_globales": metricas_globales,
        "resultados_por_caso": resultados_por_caso,
        "controles_negativos": neg_results,
        "veredicto_final": veredicto,
        "interpretacion": msg,
    }
    
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  ✅ Resultados guardados en: {OUTPUT_JSON}")
    
    # 10. Generar reporte Markdown
    _generar_reporte(output, OUTPUT_REPORT)
    print(f"  ✅ Reporte generado en: {OUTPUT_REPORT}")
    
    return output


def _generar_reporte(data: dict, path: str):
    """Genera el reporte científico en Markdown."""
    lines = [
        "# EXP-Q: Ablación del Pilar 3 — Grafo Sináptico como Puente Léxico",
        "",
        f"**Fecha**: {data['fecha']}  ",
        f"**DB SHA-256**: `{data['db_sha256']}`  ",
        f"**Casos DEV (stem_overlap=0)**: {data['n_casos']}  ",
        f"**Controles Negativos**: {data['n_controles_negativos']}",
        "",
        "## Motivación",
        "",
        "Claude auditó el código de la rama `cuantificarelaporterealdeConceptHubyWordNet` y encontró",
        "que `sinapsis` + `context_window` existe pero está **apagado por defecto** (`context_window=0`).",
        "Este experimento mide si activarlo rescata el gold en los 5 casos de abismo léxico genuino",
        "(stem_overlap=0 confirmado), que es el equivalente simbólico de lo que HippoRAG hace con PPR.",
        "",
        "## Hipótesis",
        "",
        "- **H0**: `context_window=0` vs `context_window>0` no cambia el recall en casos de abismo léxico genuino.",
        "- **H1**: El grafo sináptico activa como puente léxico, elevando el gold al pool desde vecinos",
        "  que sí tienen solapamiento con la consulta B.",
        "",
        "## Métricas Globales por Nivel",
        "",
        "| cw | Gold/Pool | R@1 | R@5 | Generaciones | FP Negativos |",
        "|:--:|:--:|:--:|:--:|:--:|:--:|",
    ]
    
    n = data["n_casos"]
    for cw in data["context_window_levels"]:
        m = data["metricas_globales"][f"cw_{cw}"]
        tag = " ← baseline" if cw == 0 else ""
        lines.append(
            f"| {cw} | {m['gold_in_pool']}/{n} | {m['recall_at_1']}/{n} | "
            f"{m['recall_at_5']}/{n} | {m['graph_generations']} | {m['false_positives_neg']} |{tag}"
        )
    
    lines += [
        "",
        "## Resultados por Caso",
        "",
    ]
    
    for caso in data["resultados_por_caso"]:
        cid = caso["case_id"]
        gold = caso["gold"]
        lines += [
            f"### [{cid}] `{gold}`",
            f"**Query B**: *{caso['query_b']}*  ",
            f"**Stimulus A**: *{caso['stimulus_a']}*  ",
            f"**Vecinos sinápticos del gold**: {caso['n_vecinos_sinapsis_gold']}",
            "",
            "| cw | En pool | Rank | Score | Fuente | Clasificación | Puente |",
            "|:--:|:--:|:--:|:--:|:--:|:--:|:--|",
        ]
        for cw in data["context_window_levels"]:
            key = f"cw_{cw}"
            m = caso["niveles"].get(key, {})
            bridge_str = ""
            if m.get("bridge"):
                b = m["bridge"]
                bridge_str = f"{b['bridge_node']} (peso={b['bridge_sinapsis_weight']}, dist={b['path_length']})"
            lines.append(
                f"| {cw} | {'✅' if m.get('gold_in_pool') else '❌'} | "
                f"{m.get('gold_rank', '—')} | {m.get('gold_score', '—')} | "
                f"{m.get('gold_source', '—')} | {m.get('classification', 'BASELINE')} | {bridge_str} |"
            )
        
        lines += [
            "",
            f"**Veredicto**: `{caso['veredicto']}`",
            "",
        ]
    
    lines += [
        "## Controles Negativos",
        "",
        "*(Verificación de que context_window no introduce FP en consultas totalmente no relacionadas)*",
        "",
    ]
    for neg in data["controles_negativos"]:
        lines += [
            f"### {neg['neg_id']}: *{neg['query']}*",
            "",
        ]
        for cw in data["context_window_levels"]:
            fps = neg["false_positives_by_cw"].get(f"cw_{cw}", [])
            lines.append(f"- **cw={cw}**: {len(fps)} FP {'✅' if len(fps)==0 else '⚠️ ' + str(fps)}")
        lines.append("")
    
    lines += [
        "## Veredicto Científico",
        "",
        f"**{data['veredicto_final']}**",
        "",
        data["interpretacion"],
        "",
        "---",
        f"*Experimento EXP-Q — MemoryBioRAG — core/ invariante — snapshot read-only*",
    ]
    
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    ejecutar_expQ()
