#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_r3_level_first_ordering.py
=============================================================================
EXP-Q-R3: ORDENAMIENTO POR NIVEL-PRIMERO — CAMBIO ESTRUCTURAL DEL CAP
=============================================================================
Recomendación de Claude (2026-09-09):

  De las 3 opciones propuestas para resolver el problema estructural del cap
  (pool crece exponencial, cap crece lineal), Claude recomienda la Opción C:

    Ordenar los contextos por (nivel ASC, score DESC) en vez de solo score DESC.

  Principio: "un nodo más cercano en el grafo siempre gana a uno más lejano,
  sin importar el peso de una arista puntual. La distancia es evidencia más
  confiable que un peso aislado."

  Por qué es la mejor primera opción:
    - 0 hiperparámetros nuevos (no hay qué calibrar con solo 2 casos)
    - Es una regla de orden, no un número ajustable → no hay sobreajuste
    - Con 5 primarios × 3 vecinos máx = 15 nodos de nivel-1, estos nunca
      saturan el cap de 45 (= 15×3), dejando espacio real para nivel-2
    - Si funciona: el problema era el criterio de orden, no el tamaño del cap
    - Si NO funciona: entonces sí se justifica probar B (slots reservados)
      con más casos de prueba antes de fijar porcentajes

  Advertencia de protocolo #18 (Claude):
    Con n=2 rescates positivos, cualquier ajuste con hiperparámetros corre
    riesgo de sobreajuste. Opción C no tiene hiperparámetros → es la única
    que se puede probar limpiamente con n=2 sin violar el protocolo.

DISEÑO:
  - Mismos 5 casos DEV, mismos 2 controles negativos
  - 2 modos de ordenamiento:
    MODE_A: score DESC (actual — baseline de EXP-Q)
    MODE_C: (nivel ASC, score DESC) — propuesta de Claude
  - Para cada modo, cw ∈ {1, 2, 3}
  - Métricas: gold_in_pool, gold_rank, monotonía, FP
  - Test específico: ¿CASE_02 se preserva en cw=2 con MODE_C? ¿Y en cw=3?

RESTRICCIONES INVARIANTES:
  - core/ 100% INTACTO
  - Snapshot READ-ONLY (sqlite3 URI)
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

# ─── Constantes ───────────────────────────────────────────────────────────────
OUTPUT_JSON   = "docs/expQ_r3_level_first_results.json"
OUTPUT_REPORT = "docs/expQ_r3_level_first_report.md"

CONTEXT_WINDOW_LEVELS = [0, 1, 2, 3]
SEARCH_LIMIT = 50
MAX_VECINOS_POR_NODO = 3
MAX_CONTEXTOS_BASE = 15


# ─── BFS con ordenamiento configurable ────────────────────────────────────────

def _bfs_con_ordenamiento(
    con: sqlite3.Connection,
    pagina_resultados: List[Tuple],
    depth: int,
    order_mode: str,  # "score_desc" o "level_first"
) -> Tuple[List[Tuple], List[Tuple]]:
    """BFS sobre el grafo sináptico con dos modos de ordenamiento.

    El BFS en sí es idéntico al de core/_expandir_contexto_bfs:
    - Recorre nivel por nivel hasta depth (máx 3)
    - Máximo 3 vecinos por nodo por nivel
    - Score = score_padre * 0.6 + peso_arista * 0.2 (sin decay, como core/)
    - Deduplica estrictamente

    La ÚNICA diferencia es cómo se ordenan los contextos antes de aplicar el cap:

    MODE "score_desc" (actual en core/):
      contextos.sort(key=lambda x: x[4], reverse=True)
      → Un nodo de nivel-3 con arista de peso alto puede superar a uno de nivel-2

    MODE "level_first" (Opción C de Claude):
      contextos.sort(key=lambda x: (x_nivel, -x[4]))
      → Todos los de nivel-1 van primero, luego nivel-2, luego nivel-3
      → Dentro de cada nivel, ordenados por score descendente
      → Un nodo de nivel-3 NUNCA puede desplazar a uno de nivel-2

    El cap sigue siendo MAX_CONTEXTOS_BASE * depth (sin cambio).

    Args:
        con: conexión read-only al snapshot
        pagina_resultados: resultados primarios del FTS5+PPMI
        depth: profundidad BFS (1-3)
        order_mode: "score_desc" | "level_first"

    Returns:
        (primarios, contextos_ordenados_según_mode)
    """
    depth = min(int(depth), 3)
    if depth <= 0 or not pagina_resultados:
        return list(pagina_resultados), []

    vistos = {r[0]: r for r in pagina_resultados}
    frontera = list(pagina_resultados)
    # Cada contexto lleva su nivel de descubrimiento para el ordenamiento level_first
    contextos_con_nivel: List[Tuple[Tuple, int]] = []  # (item, nivel)

    for nivel in range(1, depth + 1):
        siguiente_frontera = []
        for r in frontera:
            concepto = r[0]
            score_actual = r[4]

            rows = con.execute("""
                SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
                FROM sinapsis s
                JOIN largo_plazo l ON l.concepto = s.destino
                WHERE s.origen = ? AND l.estado = 'activo'
                UNION
                SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
                FROM sinapsis s
                JOIN largo_plazo l ON l.concepto = s.origen
                WHERE s.destino = ? AND l.estado = 'activo'
                ORDER BY s.peso DESC
            """, (concepto, concepto)).fetchall()

            agregados = 0
            for row in rows:
                if agregados >= MAX_VECINOS_POR_NODO:
                    break
                vecino_concepto = row[0]
                if vecino_concepto in vistos:
                    continue

                # Score idéntico a core/ (sin decay)
                score_contexto = round(min(1.0, score_actual * 0.6 + min(row[5], 1.0) * 0.2), 4)

                new_item = (vecino_concepto, row[1] or "", row[2], row[3], score_contexto, row[4] or "")
                contextos_con_nivel.append((new_item, nivel))
                vistos[vecino_concepto] = new_item
                siguiente_frontera.append(new_item)
                agregados += 1

        frontera = siguiente_frontera
        if not frontera:
            break

    # Aplicar el ordenamiento según el modo
    if order_mode == "level_first":
        # Opción C: nivel ASC (más cercano primero), luego score DESC dentro del nivel
        contextos_con_nivel.sort(key=lambda x: (x[1], -x[0][4]))
    else:
        # Baseline: solo score DESC (actual en core/)
        contextos_con_nivel.sort(key=lambda x: -x[0][4])

    # Extraer solo los items, aplicar cap
    contextos = [item for item, _nivel in contextos_con_nivel]
    max_cap = MAX_CONTEXTOS_BASE * max(1, depth)
    return list(pagina_resultados), contextos[:max_cap]


# ─── Métricas ──────────────────────────────────────────────────────────────────

def extraer_metricas(resultados: List[Tuple], gold: str, primarios_set: set) -> Dict:
    """Extrae posición y procedencia del gold en los resultados."""
    conceptos = [r[0] for r in resultados]
    if gold not in conceptos:
        return {"gold_in_pool": False, "gold_rank": None, "gold_score": None,
                "gold_source": "NOT_FOUND", "pool_size": len(resultados)}
    rank = conceptos.index(gold) + 1
    score = resultados[rank - 1][4]
    source = "PRIMARY" if gold in primarios_set else "GRAPH_NEIGHBOR"
    return {"gold_in_pool": True, "gold_rank": rank, "gold_score": round(float(score), 4),
            "gold_source": source, "pool_size": len(resultados)}


# ─── Experimento principal ─────────────────────────────────────────────────────

def ejecutar_expQ_r3():
    print("=" * 78)
    print("EXP-Q-R3: LEVEL-FIRST ORDERING — CAMBIO ESTRUCTURAL DEL CAP")
    print("=" * 78)
    print()
    print("Opción C (Claude): ordenar por (nivel ASC, score DESC)")
    print("en vez de solo score DESC. Cero hiperparámetros nuevos.")
    print()

    h = hashlib.sha256()
    with open(DB_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    db_sha_inicio = h.hexdigest()
    print(f"  DB SHA-256 inicio: {db_sha_inicio}")

    con_ro = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    print("  Inicializando motor BioRAG para primarios FTS5+PPMI...")
    t0 = time.perf_counter()
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)
    print(f"  Motor listo en {(time.perf_counter()-t0)*1000:.0f}ms")

    # Pre-calcular primarios
    print("\n  Pre-calculando primarios...")
    primarios_cache = {}
    for case in DEV_TRANSFER_CASES:
        primarios, _ = cerebro.buscar_por_frase(
            frase=case["query_b"], profundidad="activos", pagina=1,
            limite=SEARCH_LIMIT, context_window=0, preview_chars=200,
            ordenar_por="relevancia",
        )
        primarios_cache[case["id"]] = {
            "primarios": primarios,
            "primarios_set": {r[0] for r in primarios},
        }
        gold_in_m0 = case["gold"] in primarios_cache[case["id"]]["primarios_set"]
        print(f"  [{case['id']}] gold_in_M0={gold_in_m0}, primarios={len(primarios)}")

    # ─── Comparar MODE_A (score_desc) vs MODE_C (level_first) ──────────────────
    modes = [
        ("score_desc", "Baseline (core/ actual)"),
        ("level_first", "Opción C — nivel primero"),
    ]

    resultados_por_modo = {}

    for mode, mode_label in modes:
        print(f"\n{'─' * 78}")
        print(f"MODO: {mode_label} ({mode})")
        print(f"{'─' * 78}")

        gen_total = 0
        mono_viol = 0
        casos_detail = []

        for case in DEV_TRANSFER_CASES:
            cid = case["id"]
            gold = case["gold"]
            cache = primarios_cache[cid]
            niveles = {}

            # M0 baseline (idéntico para ambos modos)
            m0 = extraer_metricas(cache["primarios"], gold, cache["primarios_set"])
            m0["classification"] = "BASELINE"
            niveles["cw_0"] = m0

            gold_prev = m0["gold_in_pool"]
            for cw in [1, 2, 3]:
                prim_out, vecinos = _bfs_con_ordenamiento(
                    con=con_ro,
                    pagina_resultados=cache["primarios"],
                    depth=cw,
                    order_mode=mode,
                )
                combinados = (prim_out + vecinos)[:SEARCH_LIMIT]
                mx = extraer_metricas(combinados, gold, cache["primarios_set"])

                if not gold_prev and mx["gold_in_pool"]:
                    mx["classification"] = "GRAPH_GENERATION"
                    gen_total += 1
                elif gold_prev and mx["gold_in_pool"]:
                    mx["classification"] = "MAINTAINED"
                elif gold_prev and not mx["gold_in_pool"]:
                    mx["classification"] = "REGRESION_MONOTONICA"
                    mono_viol += 1
                else:
                    mx["classification"] = "NO_CHANGE"

                gold_prev = mx["gold_in_pool"]
                niveles[f"cw_{cw}"] = mx

            casos_detail.append({"case_id": cid, "gold": gold, "niveles": niveles})

            rescue_info = ""
            for cw in [1, 2, 3]:
                m = niveles[f"cw_{cw}"]
                if m.get("classification") == "GRAPH_GENERATION":
                    rescue_info = f" ★ RESCUED cw={cw} R{m['gold_rank']} score={m['gold_score']}"
                    break
                elif m.get("classification") == "REGRESION_MONOTONICA":
                    rescue_info = f" ⚠ MONO_VIOL at cw={cw}"
                    break
            # Mostrar estabilidad: qué cw's tienen el gold
            stability = []
            for cw in [1, 2, 3]:
                if niveles[f"cw_{cw}"].get("gold_in_pool"):
                    r = niveles[f"cw_{cw}"]["gold_rank"]
                    stability.append(f"cw{cw}:R{r}")
            stab_str = f" | stable in: [{', '.join(stability)}]" if stability else ""
            print(f"  [{cid}]{rescue_info}{stab_str}")

        # FP en controles negativos
        gold_conceptos = {c["gold"] for c in DEV_TRANSFER_CASES}
        fp_total = 0
        for neg in NEGATIVE_CONTROLS:
            prim_neg, _ = cerebro.buscar_por_frase(
                frase=neg["query"], profundidad="activos", pagina=1,
                limite=SEARCH_LIMIT, context_window=0, preview_chars=200,
                ordenar_por="relevancia",
            )
            for cw in [1, 2, 3]:
                _, vec_neg = _bfs_con_ordenamiento(con_ro, prim_neg, cw, mode)
                combinados_neg = (list(prim_neg) + vec_neg)[:SEARCH_LIMIT]
                fps = [r for r in combinados_neg[:10]
                       if r[0] in gold_conceptos and float(r[4]) >= 0.25]
                fp_total += len(fps)

        resultados_por_modo[mode] = {
            "mode": mode,
            "label": mode_label,
            "graph_generations": gen_total,
            "monotonic_violations": mono_viol,
            "false_positives_neg": fp_total,
            "casos": casos_detail,
        }
        print(f"\n  → Gen={gen_total} | MonoViol={mono_viol} | FP_neg={fp_total}")

    # ─── Tabla comparativa lado a lado ─────────────────────────────────────────
    print(f"\n{'─' * 78}")
    print("COMPARACIÓN DIRECTA: score_desc vs level_first")
    print(f"{'─' * 78}")
    print(f"  {'Métrica':<25} | {'score_desc':>12} | {'level_first':>12}")
    print(f"  {'-'*25} | {'-'*12} | {'-'*12}")

    sd = resultados_por_modo["score_desc"]
    lf = resultados_por_modo["level_first"]

    print(f"  {'Generaciones':<25} | {sd['graph_generations']:>12} | {lf['graph_generations']:>12}")
    print(f"  {'Violaciones monotónicas':<25} | {sd['monotonic_violations']:>12} | {lf['monotonic_violations']:>12}")
    print(f"  {'FP negativos':<25} | {sd['false_positives_neg']:>12} | {lf['false_positives_neg']:>12}")

    # Detalle por caso
    print()
    print(f"  {'Caso':<12} | {'score_desc':>20} | {'level_first':>20}")
    print(f"  {'-'*12} | {'-'*20} | {'-'*20}")

    for case in DEV_TRANSFER_CASES:
        cid = case["id"]
        def summarize(mode_data, cid):
            caso = next(c for c in mode_data["casos"] if c["case_id"] == cid)
            parts = []
            for cw in [1, 2, 3]:
                m = caso["niveles"].get(f"cw_{cw}", {})
                if m.get("gold_in_pool"):
                    parts.append(f"cw{cw}:R{m['gold_rank']}")
            return ", ".join(parts) if parts else "NOT_FOUND"

        s_sd = summarize(sd, cid)
        s_lf = summarize(lf, cid)
        marker = ""
        if s_sd != s_lf:
            marker = " ← CHANGED"
        print(f"  {cid:<12} | {s_sd:>20} | {s_lf:>20}{marker}")

    # ─── Veredicto ─────────────────────────────────────────────────────────────
    print(f"\n{'─' * 78}")
    print("VEREDICTO CIENTÍFICO")
    print(f"{'─' * 78}")

    # Verificar si CASE_02 está en cw=2 con level_first
    caso02_lf = next(c for c in lf["casos"] if c["case_id"] == "CASE_02")
    case02_cw2_lf = caso02_lf["niveles"].get("cw_2", {}).get("gold_in_pool", False)
    case02_cw3_lf = caso02_lf["niveles"].get("cw_3", {}).get("gold_in_pool", False)

    caso02_sd = next(c for c in sd["casos"] if c["case_id"] == "CASE_02")
    case02_cw2_sd = caso02_sd["niveles"].get("cw_2", {}).get("gold_in_pool", False)

    if case02_cw2_lf and lf["monotonic_violations"] == 0 and lf["false_positives_neg"] == 0:
        veredicto = "LEVEL_FIRST_RESUELVE_CASO02"
        msg = ("Opción C confirma la hipótesis de Claude: CASE_02 se preserva en cw=2 "
               "con level_first Y mantiene monotonía (aparece también en cw=3). "
               "El problema era el criterio de orden, no el tamaño del cap. "
               "0 hiperparámetros nuevos, 0 riesgo de sobreajuste.")
    elif lf["graph_generations"] >= sd["graph_generations"] and lf["monotonic_violations"] < sd["monotonic_violations"]:
        veredicto = "LEVEL_FIRST_MEJORA_PARCIAL"
        msg = (f"Level_first mejora monotonía ({sd['monotonic_violations']}→{lf['monotonic_violations']}) "
               f"sin perder generaciones. Pero CASE_02 {'SÍ' if case02_cw2_lf else 'NO'} aparece en cw=2. "
               f"Mejora sobre baseline pero no resuelve completamente el problema estructural.")
    elif lf["graph_generations"] < sd["graph_generations"]:
        veredicto = "LEVEL_FIRST_REGRESION"
        msg = (f"Level_first pierde generaciones ({sd['graph_generations']}→{lf['graph_generations']}). "
               f"El ordenamiento por nivel sacrifica candidatos que solo el score detecta. "
               f"Opción C no es viable — considerar Opción B con más casos de prueba.")
    else:
        veredicto = "SIN_CAMBIO_SIGNIFICATIVO"
        msg = "Level_first no cambia el comportamiento relevante respecto al baseline."

    print(f"\n  {veredicto}")
    print(f"  {msg}")

    db_sha_final = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    print(f"\n  SHA inicio: {db_sha_inicio}")
    print(f"  SHA final:  {db_sha_final}")
    print(f"  SHA estable: {'✅' if db_sha_inicio == db_sha_final else '⚠️ MUTÓ'}")

    output = {
        "experimento": "EXP-Q-R3: Level-First Ordering",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db_sha256_inicio": db_sha_inicio,
        "db_sha256_final": db_sha_final,
        "sha_estable": (db_sha_inicio == db_sha_final),
        "resultados_por_modo": resultados_por_modo,
        "veredicto": veredicto,
        "interpretacion": msg,
    }

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    _generar_reporte(output)
    print(f"\n  ✅ JSON:    {OUTPUT_JSON}")
    print(f"  ✅ Reporte: {OUTPUT_REPORT}")
    return output


def _generar_reporte(data: dict):
    lines = [
        "# EXP-Q-R3: Level-First Ordering — Cambio Estructural del Cap",
        "",
        f"**Fecha**: {data['fecha']}",
        f"**SHA estable**: {'✅' if data['sha_estable'] else '⚠️'}",
        "",
        "## Hipótesis (Claude)",
        "",
        "Ordenar contextos por `(nivel ASC, score DESC)` en vez de solo `score DESC`.",
        "Un nodo más cercano en el grafo siempre gana a uno más lejano.",
        "Cero hiperparámetros nuevos → cero riesgo de sobreajuste con n=2.",
        "",
        "## Comparación Directa",
        "",
        "| Caso | score_desc | level_first |",
        "|:--|:--:|:--:|",
    ]
    sd = data["resultados_por_modo"]["score_desc"]
    lf = data["resultados_por_modo"]["level_first"]
    for case in DEV_TRANSFER_CASES:
        cid = case["id"]
        def summarize(mode_data, cid):
            caso = next(c for c in mode_data["casos"] if c["case_id"] == cid)
            parts = []
            for cw in [1, 2, 3]:
                m = caso["niveles"].get(f"cw_{cw}", {})
                if m.get("gold_in_pool"):
                    parts.append(f"cw{cw}:R{m['gold_rank']}")
            return ", ".join(parts) if parts else "NOT_FOUND"
        lines.append(f"| {cid} | {summarize(sd, cid)} | {summarize(lf, cid)} |")

    lines += [
        "",
        f"| **Generaciones** | {sd['graph_generations']} | {lf['graph_generations']} |",
        f"| **MonoViol** | {sd['monotonic_violations']} | {lf['monotonic_violations']} |",
        f"| **FP neg** | {sd['false_positives_neg']} | {lf['false_positives_neg']} |",
        "",
        "## Veredicto",
        "",
        f"**{data['veredicto']}**",
        "",
        data["interpretacion"],
        "",
        "---",
        "*EXP-Q-R3 — core/ invariante — BFS con ordenamiento experimental*",
    ]

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    ejecutar_expQ_r3()
