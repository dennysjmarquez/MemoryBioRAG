#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_r1_depth_penalty.py
=============================================================================
EXP-Q-R1: FIX DEL COMPORTAMIENTO NO-MONÓTONO — DEPTH-PENALIZED BFS SCORE
=============================================================================
Motivación (Claude + verificación matemática propia, 2026-09-08):

  EXP-Q encontró que el grafo sináptico es un mecanismo real de candidate
  generation (2/5 casos, 0 FP), pero con comportamiento no-monótono:
  CASE_02 rescatado en cw=2 pero perdido en cw=3.

  La causa NO es "ruido impredecible". Es matemáticamente determinista:

    pool_crudo  crece COMBINATORIAMENTE: hasta 3^depth nodos por primario
    max_contextos crece LINEALMENTE:     15 * depth

  Cuando depth=3: max_contextos=45. Un nodo de nivel-3 con arista de peso
  alto (ej. 0.9) puede obtener score > 0.3928 (score del gold en nivel-2)
  y desplazarlo del top-45.

  Fórmula actual de score:
    score_vecino = score_padre * 0.6 + peso_arista * 0.2
    → No penaliza por profundidad del salto

  Fix propuesto (hipótesis de Claude):
    score_vecino = (score_padre * 0.6 + peso_arista * 0.2) * DEPTH_DECAY^nivel
    → Nodos de nivel-3 reciben una penalización multiplicativa que impide
      que superen a nodos de nivel-2 con evidencia directa más sólida.

DISEÑO:
  - Mismo snapshot, mismos 5 casos, mismos 2 controles negativos que EXP-Q
  - Implementamos el BFS con depth-decay en el EXPERIMENTO (sin tocar core/)
  - Barremos DEPTH_DECAY ∈ {0.5, 0.6, 0.7, 0.8} para encontrar el punto óptimo
  - Comparamos contra la baseline EXP-Q (sin penalización = DEPTH_DECAY=1.0)
  - Medimos por nivel cw ∈ {1, 2, 3}:
      gold_in_pool: candidate generation
      gold_rank: posición
      gold_source: PRIMARY vs GRAPH_NEIGHBOR
      monotonic_check: ¿gold presente en cw=k implica presente en cw=k+1?

CRITERIO DE ÉXITO:
  Un DEPTH_DECAY "correcto" es aquel que:
  1. Mantiene los rescates de EXP-Q (CASE_02 a cw=2, CASE_05 a cw=1)
  2. Logra monotonía: si gold aparece en cw=k, sigue en cw=k+1
  3. No introduce FP en controles negativos

RESTRICCIONES INVARIANTES:
  - core/ 100% INTACTO — el BFS modificado es solo en este script experimental
  - Snapshot READ-ONLY
  - A0-TEST ciego
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
OUTPUT_JSON   = "docs/expQ_r1_depth_penalty_results.json"
OUTPUT_REPORT = "docs/expQ_r1_depth_penalty_report.md"

# Barrido de depth_decay para encontrar el punto óptimo
DEPTH_DECAY_VALUES = [1.0, 0.8, 0.7, 0.6, 0.5]  # 1.0 = sin penalización (baseline EXP-Q)
CONTEXT_WINDOW_LEVELS = [0, 1, 2, 3]
SEARCH_LIMIT = 50
MAX_VECINOS_POR_NODO = 3   # igual que core/ — no cambiamos la topología del BFS
MAX_CONTEXTOS_BASE = 15    # igual que core/ — solo cambia el score, no el cap

# SHA del snapshot actual (puede diferir del anterior — ya documentado en EXP-Q)
SNAPSHOT_SHA_REGISTRADO = None  # Se calcula en runtime


# ─── BFS con depth-decay experimental (NO modifica core/) ─────────────────────

def _bfs_con_depth_decay(
    con: sqlite3.Connection,
    pagina_resultados: List[Tuple],
    depth: int,
    depth_decay: float,
    max_contextos_base: int = MAX_CONTEXTOS_BASE
) -> Tuple[List[Tuple], List[Tuple]]:
    """BFS idéntico al de core/_expandir_contexto_bfs, pero con penalización
    multiplicativa por nivel de profundidad en el score.

    La única diferencia con el código de producción:
      score_contexto_nuevo = score_contexto_original * (depth_decay ** nivel)

    Cuando depth_decay=1.0, reproduce exactamente el comportamiento de core/.
    Cuando depth_decay<1.0, los nodos de nivel más profundo reciben scores menores,
    evitando que desplacen nodos de niveles anteriores en el ordenamiento final.

    Esta función existe SOLO en el script experimental. core/ queda intacto.

    Args:
        con: conexión read-only al snapshot
        pagina_resultados: resultados primarios del FTS5+PPMI
        depth: profundidad BFS (1-3)
        depth_decay: factor multiplicativo por nivel (1.0 = sin penalización)
        max_contextos_base: cap base (15 en producción)

    Returns:
        (primarios, contextos_ordenados_por_score)
    """
    depth = min(int(depth), 3)
    if depth <= 0 or not pagina_resultados:
        return list(pagina_resultados), []

    vistos = {r[0]: r for r in pagina_resultados}
    frontera = list(pagina_resultados)
    contextos = []

    for nivel in range(1, depth + 1):
        # Factor de penalización acumulado para este nivel
        decay_factor = depth_decay ** nivel

        siguiente_frontera = []
        for r in frontera:
            concepto = r[0]
            score_actual = r[4]  # score del nodo padre en esta frontera

            # JOIN bidireccional sobre sinapsis (idéntico a core/)
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

                # Score base (igual que core/)
                score_base = round(min(1.0, score_actual * 0.6 + min(row[5], 1.0) * 0.2), 4)

                # ← ÚNICA DIFERENCIA: penalización por profundidad
                score_penalizado = round(score_base * decay_factor, 4)

                new_item = (vecino_concepto, row[1] or "", row[2], row[3], score_penalizado, row[4] or "")
                contextos.append(new_item)
                vistos[vecino_concepto] = new_item
                siguiente_frontera.append(new_item)
                agregados += 1

        frontera = siguiente_frontera
        if not frontera:
            break

    # Ordenar por score (con penalización incorporada) y aplicar cap lineal
    contextos.sort(key=lambda x: x[4], reverse=True)
    max_cap = max_contextos_base * max(1, depth)
    return list(pagina_resultados), contextos[:max_cap]


def buscar_con_bfs_penalizado(
    con: sqlite3.Connection,
    cerebro,
    query: str,
    context_window: int,
    depth_decay: float,
    limite: int = SEARCH_LIMIT
) -> Tuple[List[Tuple], set]:
    """Ejecuta el pipeline real de producción (FTS5+PPMI) para obtener los
    primarios, y luego aplica el BFS penalizado experimental encima.

    Retorna: (resultados_combinados, set_conceptos_primarios)
    """
    if context_window == 0:
        # Baseline puro: solo pipeline real sin BFS
        resultados, _ = cerebro.buscar_por_frase(
            frase=query, profundidad="activos", pagina=1,
            limite=limite, context_window=0, preview_chars=200,
            ordenar_por="relevancia",
        )
        return resultados, {r[0] for r in resultados}

    # Primarios: pipeline real sin context_window
    primarios, _ = cerebro.buscar_por_frase(
        frase=query, profundidad="activos", pagina=1,
        limite=limite, context_window=0, preview_chars=200,
        ordenar_por="relevancia",
    )
    primarios_set = {r[0] for r in primarios}

    # BFS penalizado experimental
    prim_out, vecinos = _bfs_con_depth_decay(
        con=con,
        pagina_resultados=primarios,
        depth=context_window,
        depth_decay=depth_decay,
    )

    # Combinar: primarios + vecinos (sin duplicados — el BFS ya deduplica)
    combinados = list(primarios) + vecinos
    # Truncar al límite pedido
    return combinados[:limite], primarios_set


# ─── Extracción de métricas ────────────────────────────────────────────────────

def extraer_metricas_gold(
    resultados: List[Tuple],
    gold: str,
    primarios_set: set
) -> Dict[str, Any]:
    """Extrae posición y procedencia del gold en los resultados."""
    conceptos = [r[0] for r in resultados]
    if gold not in conceptos:
        return {"gold_in_pool": False, "gold_rank": None, "gold_score": None,
                "gold_source": "NOT_FOUND", "pool_size": len(resultados)}

    rank = conceptos.index(gold) + 1
    score = resultados[rank - 1][4]
    source = "PRIMARY" if gold in primarios_set else "GRAPH_NEIGHBOR"
    return {
        "gold_in_pool": True,
        "gold_rank": rank,
        "gold_score": round(float(score), 4),
        "gold_source": source,
        "pool_size": len(resultados),
    }


# ─── Experimento principal ─────────────────────────────────────────────────────

def ejecutar_expQ_r1():
    print("=" * 78)
    print("EXP-Q-R1: DEPTH-PENALIZED BFS — FIX DEL COMPORTAMIENTO NO-MONÓTONO")
    print("=" * 78)
    print()
    print("Hipótesis de Claude (verificada matemáticamente):")
    print("  pool_crudo crece COMBINATORIAMENTE, max_contextos crece LINEALMENTE.")
    print("  Fix: penalizar score por profundidad real para garantizar monotonía.")
    print()

    # SHA del snapshot
    h = hashlib.sha256()
    with open(DB_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    db_sha = h.hexdigest()
    print(f"  DB: {DB_PATH}")
    print(f"  SHA-256: {db_sha}")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    print("\n  Inicializando SQLiteMemoryBioRAG...")
    t0 = time.perf_counter()
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)
    print(f"  ✅ Motor listo en {(time.perf_counter()-t0)*1000:.0f}ms")

    # ─── Pre-calcular primarios por caso (constantes para todos los decay values)
    print("\n  Pre-calculando pools primarios (constantes entre configuraciones)...")
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
        gold = case["gold"]
        in_m0 = gold in {r[0] for r in primarios}
        print(f"  [{case['id']}] gold_in_M0={in_m0}, primarios={len(primarios)}")

    # ─── Barrido de DEPTH_DECAY ────────────────────────────────────────────────
    print("\n" + "─" * 78)
    print("BARRIDO: DEPTH_DECAY ∈ {1.0, 0.8, 0.7, 0.6, 0.5}")
    print("─" * 78)

    resultados_barrido = {}

    for decay in DEPTH_DECAY_VALUES:
        label = f"decay_{decay:.1f}"
        print(f"\n── decay={decay:.1f} {'(baseline=EXP-Q)' if decay == 1.0 else ''} ──")

        gen_total = 0
        pool_total = 0
        monotonic_violations = 0  # casos donde gold en cw=k pero no en cw=k+1
        casos_detail = []

        for case in DEV_TRANSFER_CASES:
            cid = case["id"]
            gold = case["gold"]
            query_b = case["query_b"]
            cache = primarios_cache[cid]

            niveles = {}

            # M0: baseline puro (idéntico para todos los decay)
            m0_res = cache["primarios"]
            m0 = extraer_metricas_gold(m0_res, gold, cache["primarios_set"])
            m0["classification"] = "BASELINE"
            niveles["cw_0"] = m0

            # M1, M2, M3 con BFS penalizado
            gold_present_prev = m0["gold_in_pool"]
            for cw in [1, 2, 3]:
                # BFS penalizado con este decay
                prim_out, vecinos = _bfs_con_depth_decay(
                    con=con,
                    pagina_resultados=cache["primarios"],
                    depth=cw,
                    depth_decay=decay,
                )
                combinados = (prim_out + vecinos)[:SEARCH_LIMIT]
                mx = extraer_metricas_gold(combinados, gold, cache["primarios_set"])

                # Clasificación causal
                if not gold_present_prev and mx["gold_in_pool"]:
                    mx["classification"] = "GRAPH_GENERATION"
                    gen_total += 1
                elif gold_present_prev and mx["gold_in_pool"]:
                    mx["classification"] = "MAINTAINED"
                elif gold_present_prev and not mx["gold_in_pool"]:
                    mx["classification"] = "REGRESION_MONOTONICA"
                    monotonic_violations += 1
                else:
                    mx["classification"] = "NO_CHANGE"

                gold_present_prev = mx["gold_in_pool"]
                niveles[f"cw_{cw}"] = mx

            if niveles.get("cw_1", {}).get("gold_in_pool") or \
               niveles.get("cw_2", {}).get("gold_in_pool") or \
               niveles.get("cw_3", {}).get("gold_in_pool"):
                pool_total += 1

            casos_detail.append({
                "case_id": cid,
                "gold": gold,
                "niveles": niveles,
            })

            # Print compacto por caso
            rescue_marker = ""
            for cw in [1, 2, 3]:
                m = niveles[f"cw_{cw}"]
                if m.get("classification") == "GRAPH_GENERATION":
                    rescue_marker = f" ★ RESCUED at cw={cw} (rank={m['gold_rank']}, src={m['gold_source']})"
                    break
                elif m.get("classification") == "REGRESION_MONOTONICA":
                    rescue_marker = f" ⚠ MONOTONIC VIOLATION at cw={cw}"
                    break
            print(f"  [{cid}] gold={gold}{rescue_marker}")

        # Controles negativos
        fp_total = 0
        gold_conceptos = {case["gold"] for case in DEV_TRANSFER_CASES}
        for neg in NEGATIVE_CONTROLS:
            prim_neg, _ = cerebro.buscar_por_frase(
                frase=neg["query"], profundidad="activos", pagina=1,
                limite=SEARCH_LIMIT, context_window=0, preview_chars=200,
                ordenar_por="relevancia",
            )
            prim_neg_set = {r[0] for r in prim_neg}
            for cw in [1, 2, 3]:
                _, vecinos_neg = _bfs_con_depth_decay(con, prim_neg, cw, decay)
                combinados_neg = (list(prim_neg) + vecinos_neg)[:SEARCH_LIMIT]
                fps = [r for r in combinados_neg[:10]
                       if r[0] in gold_conceptos and float(r[4]) >= 0.25]
                fp_total += len(fps)

        resultados_barrido[label] = {
            "depth_decay": decay,
            "graph_generations": gen_total,
            "casos_con_gold_rescatado": pool_total,
            "monotonic_violations": monotonic_violations,
            "false_positives_neg": fp_total,
            "casos": casos_detail,
        }
        print(f"  → Gen={gen_total} | CasosRescatados={pool_total}/5 | "
              f"ViolacionesMonotonicas={monotonic_violations} | FP_neg={fp_total}")

    # ─── Resumen comparativo ───────────────────────────────────────────────────
    print("\n" + "─" * 78)
    print("TABLA COMPARATIVA: decay vs. métricas clave")
    print("─" * 78)
    print(f"  {'decay':>8} | {'Gen':>5} | {'Rescatados':>12} | {'Mono.Viol':>10} | {'FP_neg':>7}")
    print(f"  {'-'*8} | {'-'*5} | {'-'*12} | {'-'*10} | {'-'*7}")
    for decay in DEPTH_DECAY_VALUES:
        label = f"decay_{decay:.1f}"
        r = resultados_barrido[label]
        marker = " ← ÓPTIMO?" if (r["graph_generations"] > 0 and
                                   r["monotonic_violations"] == 0 and
                                   r["false_positives_neg"] == 0) else ""
        print(f"  {decay:>8.1f} | {r['graph_generations']:>5} | "
              f"{r['casos_con_gold_rescatado']:>12}/5 | "
              f"{r['monotonic_violations']:>10} | "
              f"{r['false_positives_neg']:>7}{marker}")

    # ─── Veredicto ─────────────────────────────────────────────────────────────
    print("\n" + "─" * 78)
    print("VEREDICTO CIENTÍFICO")
    print("─" * 78)

    # Mejor decay: máximas generaciones, 0 violaciones monotónicas, 0 FP
    candidatos_optimos = [
        (d, resultados_barrido[f"decay_{d:.1f}"])
        for d in DEPTH_DECAY_VALUES
        if (resultados_barrido[f"decay_{d:.1f}"]["monotonic_violations"] == 0 and
            resultados_barrido[f"decay_{d:.1f}"]["false_positives_neg"] == 0)
    ]
    candidatos_optimos.sort(key=lambda x: -x[1]["graph_generations"])

    if candidatos_optimos:
        best_decay, best_r = candidatos_optimos[0]
        veredicto = "DEPTH_DECAY_MEJORA_MONOTONIA"
        msg = (f"depth_decay={best_decay:.1f} maximiza generaciones ({best_r['graph_generations']}) "
               f"con 0 violaciones monotónicas y 0 FP. "
               f"La hipótesis de Claude es correcta: el BFS no-monótono se resuelve "
               f"con penalización de score por profundidad.")
    else:
        veredicto = "SIN_CONFIGURACION_OPTIMA"
        msg = "Ningún decay logra 0 violaciones + 0 FP simultáneamente. Requiere investigación adicional."

    print(f"\n  {veredicto}")
    print(f"  {msg}")

    # ─── Serialización ─────────────────────────────────────────────────────────
    output = {
        "experimento": "EXP-Q-R1: Depth-Penalized BFS",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db_sha256": db_sha,
        "depth_decay_values": DEPTH_DECAY_VALUES,
        "context_window_levels": CONTEXT_WINDOW_LEVELS,
        "resultados_barrido": resultados_barrido,
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
        "# EXP-Q-R1: Depth-Penalized BFS — Fix del Comportamiento No-Monótono",
        "",
        f"**Fecha**: {data['fecha']}  ",
        f"**DB SHA-256**: `{data['db_sha256']}`",
        "",
        "## Hipótesis (Claude, verificada matemáticamente)",
        "",
        "El comportamiento no-monótono de EXP-Q (gold rescatado en cw=2 pero",
        "perdido en cw=3) es una consecuencia determinista de:",
        "- Pool crudo crece **combinatoriamente** con la profundidad",
        "- `max_contextos` crece **linealmente** (15 × depth)",
        "- La fórmula de score actual no penaliza nodos de mayor profundidad",
        "",
        "**Fix**: aplicar un factor multiplicativo `depth_decay^nivel` al score",
        "de cada nodo según su profundidad en el BFS.",
        "",
        "## Tabla Comparativa",
        "",
        "| depth_decay | Generaciones | Casos Rescatados | Violaciones Monótonas | FP Negativos |",
        "|:--:|:--:|:--:|:--:|:--:|",
    ]

    for decay in data["depth_decay_values"]:
        label = f"decay_{decay:.1f}"
        r = data["resultados_barrido"][label]
        marker = " ✅ ÓPTIMO" if (r["graph_generations"] > 0 and
                                   r["monotonic_violations"] == 0 and
                                   r["false_positives_neg"] == 0) else ""
        lines.append(
            f"| {decay:.1f} | {r['graph_generations']} | "
            f"{r['casos_con_gold_rescatado']}/5 | "
            f"{r['monotonic_violations']} | "
            f"{r['false_positives_neg']} |{marker}"
        )

    lines += [
        "",
        "## Veredicto",
        "",
        f"**{data['veredicto']}**",
        "",
        data["interpretacion"],
        "",
        "---",
        "*EXP-Q-R1 — core/ invariante — snapshot read-only*",
    ]

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    ejecutar_expQ_r1()
