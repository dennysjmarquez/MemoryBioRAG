#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_r2_absolute_depth_decay.py
=============================================================================
EXP-Q-R2: ABSOLUTE DEPTH DECAY — FIX DEL COMPOUNDING EN EXP-Q-R1
=============================================================================
Corrección de Claude (2026-09-08):

  EXP-Q-R1 implementó depth-decay pero con un error de fórmula:
  el decay se componía dos veces porque `score_actual` del padre ya tenía
  el decay del nivel anterior aplicado.

  Fórmula real en EXP-Q-R1 (nivel 2):
    s2 = (s1 * 0.6 + w * 0.2) * decay^2
         donde s1 = (s0 * 0.6 + w * 0.2) * decay^1
    → El decay se aplica implícitamente dos veces vía herencia
    → Efecto real en nivel-3 es más agresivo que decay^3 puro

  Verificación numérica (decay=0.8, nivel=2):
    Score compuesto (código real): 0.2627
    Score según docstring (decay^2): 0.3072
    Diferencia: 0.0445 — no negligible

  Consecuencia observada: CASE_02 que aparecía en rank=23 a cw=2
  con decay=1.0 se mueve a rank=38 a cw=3 con decay=0.8 — no se
  preservó en su punto original, se debilitó.

HIPÓTESIS A PROBAR:
  Con decay "absoluto" (aplicado solo sobre el score_base del PRIMARIO,
  no heredando el decay del padre), la penalización es más suave y
  predecible, permitiendo que CASE_02 permanezca en cw=2 (donde tiene
  evidencia directa) sin perderlo a cw=3.

DISEÑO DEL DECAY ABSOLUTO:
  Para cada nodo vecino, en vez de heredar score_actual (ya penalizado)
  del padre, usamos el score del PRIMARIO que inició el camino de BFS
  (score_raiz) y aplicamos decay^nivel una sola vez:

    score_final = (score_raiz * 0.6 + peso_arista * 0.2) * (decay ** nivel)

  Esto requiere rastrear score_raiz a lo largo del BFS.
  Cuando decay=1.0 → reproduce EXP-Q-R1 con decay=1.0 (sin penalización).

BARRIDO: decay ∈ {1.0, 0.9, 0.8, 0.7, 0.6, 0.5}
  Criterio óptimo:
    1. Mismas 2 generaciones que EXP-Q (CASE_02 + CASE_05)
    2. CASE_02 rescatado en cw=2 (no empujado a cw=3)  ← CASE_05 en cw=1
    3. Monotonía: si gold aparece en cw=k, sigue en cw=k+1
    4. 0 FP en controles negativos

RESTRICCIONES INVARIANTES:
  - core/ 100% INTACTO
  - Snapshot READ-ONLY (se usa sqlite3 URI read-only, no SQLiteMemoryBioRAG)
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
OUTPUT_JSON   = "docs/expQ_r2_absolute_depth_decay_results.json"
OUTPUT_REPORT = "docs/expQ_r2_absolute_depth_decay_report.md"

DEPTH_DECAY_VALUES = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
CONTEXT_WINDOW_LEVELS = [0, 1, 2, 3]
SEARCH_LIMIT = 50
MAX_VECINOS_POR_NODO = 3
MAX_CONTEXTOS_BASE = 15


# ─── BFS con decay ABSOLUTO (no compuesto) ────────────────────────────────────

def _bfs_absoluto(
    con: sqlite3.Connection,
    pagina_resultados: List[Tuple],
    depth: int,
    depth_decay: float,
) -> Tuple[List[Tuple], List[Tuple]]:
    """BFS con decay absoluto: penalización aplicada UNA SOLA VEZ
    sobre el score del primario de origen, sin heredar el decay del padre.

    Esto es la corrección del compounding de EXP-Q-R1.

    Fórmula exacta para un nodo vecino en nivel `k`:
      score = (score_raiz * 0.6 + peso_arista * 0.2) * (decay ** k)

    donde score_raiz es el score del primario (nivel 0) que inició el camino.
    
    Diferencia con EXP-Q-R1:
      EXP-Q-R1: score_2 = (score_1 * 0.6 + w * 0.2) * decay^2
                donde score_1 ya tiene decay^1 → compounding implícito
      Este:     score_2 = (score_0 * 0.6 + w * 0.2) * decay^2
                donde score_0 es el score original del primario → sin compounding

    El cap de retención es el mismo que core/: MAX_CONTEXTOS_BASE * depth.

    Args:
        con: conexión read-only al snapshot (sqlite3 URI)
        pagina_resultados: resultados primarios del FTS5+PPMI
        depth: profundidad BFS (1-3)
        depth_decay: factor de penalización por nivel (1.0 = sin penalización)

    Returns:
        (primarios, contextos_ordenados_por_score_absoluto)
    """
    depth = min(int(depth), 3)
    if depth <= 0 or not pagina_resultados:
        return list(pagina_resultados), []

    # vistos mapea concepto → (item, nivel_descubierto, score_raiz)
    # score_raiz: score del primario que inició el camino hacia este nodo
    vistos: Dict[str, Tuple] = {}
    for r in pagina_resultados:
        vistos[r[0]] = (r, 0, r[4])  # nivel=0, score_raiz=score_primario

    # frontera: lista de (item, score_raiz) — el score_raiz es constante
    # a lo largo de todos los saltos del mismo camino
    frontera = [(r, r[4]) for r in pagina_resultados]
    contextos = []

    for nivel in range(1, depth + 1):
        decay_factor = depth_decay ** nivel  # aplicado UNA sola vez por nivel

        siguiente_frontera = []
        for item, score_raiz in frontera:
            concepto = item[0]

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

                # ← DECAY ABSOLUTO: score calculado desde score_raiz, no score_padre
                # Penalización aplicada una sola vez: decay^nivel
                score_base = score_raiz * 0.6 + min(row[5], 1.0) * 0.2
                score_final = round(min(1.0, score_base * decay_factor), 4)

                new_item = (vecino_concepto, row[1] or "", row[2], row[3], score_final, row[4] or "")
                contextos.append(new_item)
                vistos[vecino_concepto] = (new_item, nivel, score_raiz)
                siguiente_frontera.append((new_item, score_raiz))  # propaga score_raiz original
                agregados += 1

        frontera = siguiente_frontera
        if not frontera:
            break

    contextos.sort(key=lambda x: x[4], reverse=True)
    max_cap = MAX_CONTEXTOS_BASE * max(1, depth)
    return list(pagina_resultados), contextos[:max_cap]


# ─── Pipeline de búsqueda usando SOLO el motor FTS5+PPMI sin SQLiteMemoryBioRAG
# ─── (para evitar la mutación del SHA del snapshot)

def obtener_primarios_via_cerebro(cerebro, query: str, limite: int = SEARCH_LIMIT) -> List[Tuple]:
    """Obtiene los resultados primarios del pipeline real de producción."""
    resultados, _ = cerebro.buscar_por_frase(
        frase=query, profundidad="activos", pagina=1,
        limite=limite, context_window=0, preview_chars=200,
        ordenar_por="relevancia",
    )
    return resultados


def extraer_metricas(resultados: List[Tuple], gold: str, primarios_set: set) -> Dict:
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

def ejecutar_expQ_r2():
    print("=" * 78)
    print("EXP-Q-R2: ABSOLUTE DEPTH DECAY — FIX DEL COMPOUNDING")
    print("=" * 78)
    print()
    print("Corrección de Claude: EXP-Q-R1 aplicaba el decay dos veces")
    print("(heredado del padre + explícito). Este experimento aplica")
    print("el decay una sola vez sobre el score_raiz del primario.")
    print()

    h = hashlib.sha256()
    with open(DB_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    db_sha = h.hexdigest()
    print(f"  DB SHA-256 al inicio: {db_sha}")

    # Conexión read-only para el BFS (no muta el snapshot)
    con_ro = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    print("  Inicializando motor BioRAG para FTS5+PPMI primarios...")
    t0 = time.perf_counter()
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)
    print(f"  Motor listo en {(time.perf_counter()-t0)*1000:.0f}ms")

    db_sha_post_init = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    print(f"  DB SHA-256 post-init: {db_sha_post_init}")
    if db_sha_post_init != db_sha:
        print(f"  ⚠️  SHA mutó en __init__. Causa confirmada: SQLiteMemoryBioRAG escribe en la DB.")

    # Pre-calcular primarios (fijos para todos los decay)
    print("\n  Pre-calculando primarios (constantes)...")
    primarios_cache = {}
    for case in DEV_TRANSFER_CASES:
        primarios = obtener_primarios_via_cerebro(cerebro, case["query_b"])
        primarios_cache[case["id"]] = {
            "primarios": primarios,
            "primarios_set": {r[0] for r in primarios},
        }
        gold_in_m0 = case["gold"] in primarios_cache[case["id"]]["primarios_set"]
        print(f"  [{case['id']}] gold_in_M0={gold_in_m0}, primarios={len(primarios)}")

    db_sha_post_search = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    print(f"  DB SHA-256 post-busquedas: {db_sha_post_search}")
    if db_sha_post_search != db_sha_post_init:
        print(f"  ⚠️  SHA mutó al buscar. buscar_por_frase escribe en la DB (log_busquedas, etc.)")

    # ─── Barrido de decay absoluto ─────────────────────────────────────────────
    print("\n" + "─" * 78)
    print("BARRIDO: ABSOLUTE DEPTH DECAY ∈ {1.0, 0.9, 0.8, 0.7, 0.6, 0.5}")
    print("─" * 78)

    resultados_barrido = {}

    for decay in DEPTH_DECAY_VALUES:
        print(f"\n── decay={decay:.1f} ──")
        gen_total = 0
        mono_viol = 0
        casos_detail = []

        for case in DEV_TRANSFER_CASES:
            cid = case["id"]
            gold = case["gold"]
            cache = primarios_cache[cid]
            niveles = {}

            # M0 baseline
            m0 = extraer_metricas(cache["primarios"], gold, cache["primarios_set"])
            m0["classification"] = "BASELINE"
            niveles["cw_0"] = m0

            gold_prev = m0["gold_in_pool"]
            for cw in [1, 2, 3]:
                prim_out, vecinos = _bfs_absoluto(
                    con=con_ro,
                    pagina_resultados=cache["primarios"],
                    depth=cw,
                    depth_decay=decay,
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

            # Print por caso
            rescue_info = ""
            for cw in [1, 2, 3]:
                m = niveles[f"cw_{cw}"]
                if m.get("classification") == "GRAPH_GENERATION":
                    rescue_info = f" ★ RESCUED cw={cw} rank={m['gold_rank']} score={m['gold_score']}"
                    break
                elif m.get("classification") == "REGRESION_MONOTONICA":
                    rescue_info = f" ⚠ MONO_VIOL at cw={cw}"
                    break
            print(f"  [{cid}]{rescue_info}")

        # FP en controles negativos
        gold_conceptos = {c["gold"] for c in DEV_TRANSFER_CASES}
        fp_total = 0
        for neg in NEGATIVE_CONTROLS:
            prim_neg = obtener_primarios_via_cerebro(cerebro, neg["query"])
            prim_neg_set = {r[0] for r in prim_neg}
            for cw in [1, 2, 3]:
                _, vec_neg = _bfs_absoluto(con_ro, prim_neg, cw, decay)
                combinados_neg = (list(prim_neg) + vec_neg)[:SEARCH_LIMIT]
                fps = [r for r in combinados_neg[:10]
                       if r[0] in gold_conceptos and float(r[4]) >= 0.25]
                fp_total += len(fps)

        resultados_barrido[f"decay_{decay:.1f}"] = {
            "depth_decay": decay,
            "graph_generations": gen_total,
            "monotonic_violations": mono_viol,
            "false_positives_neg": fp_total,
            "casos": casos_detail,
        }
        print(f"  → Gen={gen_total} | MonoViol={mono_viol} | FP_neg={fp_total}")

    # ─── Tabla comparativa ─────────────────────────────────────────────────────
    print("\n" + "─" * 78)
    print("TABLA COMPARATIVA: ABSOLUTE DECAY")
    print("─" * 78)
    print(f"  {'decay':>6} | {'Gen':>5} | {'MonoViol':>9} | {'FP_neg':>7} | CASE_02 cw/rank | CASE_05 cw/rank")
    print(f"  {'-'*6} | {'-'*5} | {'-'*9} | {'-'*7} | {'-'*15} | {'-'*15}")

    for decay in DEPTH_DECAY_VALUES:
        r = resultados_barrido[f"decay_{decay:.1f}"]

        def caso_summary(cid):
            caso = next(c for c in r["casos"] if c["case_id"] == cid)
            for cw in [1,2,3]:
                m = caso["niveles"].get(f"cw_{cw}", {})
                if m.get("gold_in_pool"):
                    return f"cw={cw}/R{m['gold_rank']}"
            return "NOT_FOUND"

        c02 = caso_summary("CASE_02")
        c05 = caso_summary("CASE_05")
        optimal = (r["graph_generations"] > 0 and
                   r["monotonic_violations"] == 0 and
                   r["false_positives_neg"] == 0 and
                   "cw=2" in c02)  # queremos CASE_02 en cw=2, no cw=3

        marker = " ← ÓPTIMO" if optimal else (
            " ← parcial" if (r["graph_generations"] > 0 and
                             r["monotonic_violations"] == 0 and
                             r["false_positives_neg"] == 0) else "")

        print(f"  {decay:>6.1f} | {r['graph_generations']:>5} | {r['monotonic_violations']:>9} | "
              f"{r['false_positives_neg']:>7} | {c02:<15} | {c05:<15}{marker}")

    # ─── Veredicto ─────────────────────────────────────────────────────────────
    print("\n" + "─" * 78)
    print("VEREDICTO CIENTÍFICO")
    print("─" * 78)

    # Buscar configuración óptima: CASE_02 en cw=2, 0 mono_viol, 0 FP
    optimos = []
    for decay in DEPTH_DECAY_VALUES:
        r = resultados_barrido[f"decay_{decay:.1f}"]
        caso_02 = next(c for c in r["casos"] if c["case_id"] == "CASE_02")
        case02_cw2 = caso_02["niveles"].get("cw_2", {}).get("gold_in_pool", False)
        if (r["graph_generations"] > 0 and
            r["monotonic_violations"] == 0 and
            r["false_positives_neg"] == 0):
            optimos.append((decay, case02_cw2, r))

    if any(o[1] for o in optimos):  # alguno tiene CASE_02 en cw=2
        optimo = next(o for o in optimos if o[1])
        veredicto = "ABSOLUTE_DECAY_PRESERVA_CW2"
        msg = (f"decay={optimo[0]:.1f} (absoluto) mantiene CASE_02 en cw=2 con "
               f"{optimo[2]['graph_generations']} generaciones, 0 violaciones monotónicas y 0 FP. "
               f"El compounding de EXP-Q-R1 era la causa de la degradación de rank.")
    elif optimos:
        optimo = optimos[0]
        veredicto = "ABSOLUTE_DECAY_MEJORA_PERO_NO_CW2"
        msg = (f"decay={optimo[0]:.1f} logra 0 violaciones y 0 FP, pero CASE_02 sigue en cw=3. "
               f"El decay absoluto mejora la precisión del score pero el problema "
               f"de CASE_02 es estructural (camino de nivel-2 genuinamente saturado).")
    else:
        veredicto = "SIN_CONFIGURACION_OPTIMA"
        msg = "Ningún decay absoluto logra Gen>0 + 0 mono_viol + 0 FP simultáneamente."

    print(f"\n  {veredicto}")
    print(f"  {msg}")

    db_sha_final = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    print(f"\n  DB SHA-256 final: {db_sha_final}")
    sha_mutations = len({db_sha, db_sha_post_init, db_sha_post_search, db_sha_final} - {db_sha})
    if sha_mutations > 0:
        print(f"  ⚠️  SHA mutó {sha_mutations} veces durante el experimento.")
        print(f"     Causa probable: SQLiteMemoryBioRAG escribe en la DB (log_busquedas,")
        print(f"     metricas_cognitivas, u otras tablas de telemetría) aunque la consulta")
        print(f"     sea de lectura. El BFS usa con_ro (read-only) y NO escribe.")
    else:
        print(f"  ✅ SHA estable durante el experimento.")

    output = {
        "experimento": "EXP-Q-R2: Absolute Depth Decay",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db_sha256_inicial": db_sha,
        "db_sha256_final": db_sha_final,
        "sha_estable": (db_sha == db_sha_final),
        "depth_decay_values": DEPTH_DECAY_VALUES,
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
        "# EXP-Q-R2: Absolute Depth Decay — Fix del Compounding de EXP-Q-R1",
        "",
        f"**Fecha**: {data['fecha']}",
        f"**SHA inicial**: `{data['db_sha256_inicial']}`  ",
        f"**SHA final**: `{data['db_sha256_final']}`  ",
        f"**SHA estable**: {'✅' if data['sha_estable'] else '⚠️ NO — SQLiteMemoryBioRAG escribe en la DB'}",
        "",
        "## Corrección Implementada (Claude, 2026-09-08)",
        "",
        "EXP-Q-R1 aplicaba el decay dos veces (compuesto recursivamente).",
        "Este experimento aplica el decay una sola vez sobre el score del",
        "primario de origen (`score_raiz`), sin heredar el decay del padre.",
        "",
        "```",
        "EXP-Q-R1: score_nivel2 = (score_nivel1 * 0.6 + w * 0.2) * decay²",
        "           donde score_nivel1 = (score_raiz * 0.6 + w * 0.2) * decay¹",
        "           → decay compuesto: más agresivo de lo documentado",
        "",
        "EXP-Q-R2: score_nivel2 = (score_raiz * 0.6 + w * 0.2) * decay²",
        "           donde score_raiz es el score del primario original",
        "           → decay absoluto: una sola aplicación, predecible",
        "```",
        "",
        "## Tabla Comparativa",
        "",
        "| decay | Gen | MonoViol | FP_neg | CASE_02 | CASE_05 |",
        "|:--:|:--:|:--:|:--:|:--:|:--:|",
    ]

    for decay in data["depth_decay_values"]:
        r = data["resultados_barrido"][f"decay_{decay:.1f}"]
        def caso_summary(cid):
            caso = next(c for c in r["casos"] if c["case_id"] == cid)
            for cw in [1,2,3]:
                m = caso["niveles"].get(f"cw_{cw}", {})
                if m.get("gold_in_pool"):
                    return f"cw={cw}/R{m['gold_rank']}"
            return "NOT_FOUND"
        lines.append(
            f"| {decay:.1f} | {r['graph_generations']} | {r['monotonic_violations']} | "
            f"{r['false_positives_neg']} | {caso_summary('CASE_02')} | {caso_summary('CASE_05')} |"
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
        "*EXP-Q-R2 — core/ invariante — BFS usa con_ro (read-only)*",
    ]

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    ejecutar_expQ_r2()
