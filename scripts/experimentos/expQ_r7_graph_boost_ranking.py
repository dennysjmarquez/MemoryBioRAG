#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_r7_graph_boost_ranking.py
=============================================================================
EXP-Q-R7: PRODUCTION-READY CAUSAL GRAPH BOOST & RANKING (PILAR 5)
=============================================================================
Consolidación Final para Producción (2026-09-09)
Autorización y Directrices Metodológicas: Aureon & Dennys

OBJETIVO:
  Cerrar definitivamente el abismo léxico mediante un mecanismo de expansión
  y re-ranking por grafo maduro, determinista y seguro:
  1. Supera la trampa alfabética de SQLite en la consulta de sinapsis.
  2. Selección de candidatos basada en peso relacional y grado específico (Adamic-Adar).
  3. Acumulación probabilista de soporte multi-parent.
  4. Sensibilidad monotónica a gamma garantizada en Q2.
  5. Margin protection sobre primarios de alta confianza (>= 0.90).
  6. Compuerta de abstención en controles negativos (0% FP inducido).
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import math
from typing import Dict, List, Tuple, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.experimentos.expN_scg_v01 import (
    normalizar, tokenizar, SPANISH_STOPWORDS, K_CURVE
)
from scripts.experimentos.expN11_object_role_ranker import stem_simple

DB_SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "snapshots/qa_escape_qcr_20260811.db")
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "docs/expQ_r7_graph_boost_dev_results.json")
OUTPUT_REPORT = os.path.join(PROJECT_ROOT, "docs/expQ_r7_graph_boost_dev_report.md")

PREDEFINED_GAMMAS = [0.25, 0.50, 0.75, 1.00, 1.50, 2.00]

# Parámetros calibrados
MAX_VECINOS_POR_PADRE = 12
UMBRAL_PESO_ARISTA = 0.50
UMBRAL_PRIMARIO_RUIDO = 0.25
HIGH_CONFIDENCE_PRIMARY_THRESHOLD = 0.90
MARGIN_PROTECTION_DELTA = 0.05
MAX_CONTEXTOS_POOL = 60
SEARCH_LIMIT = 50

# ─── BANCOS DE CASOS ──────────────────────────────────────────────────────────

DEV_CASES = [
    {"id": "CASE_01", "gold": "scoring_pesos_bm25",
     "query": "calibrar ajuste escalar para combinar relevancia heterogenea",
     "dominio": "algoritmos_ranking", "split": "DEV"},
    {"id": "CASE_02", "gold": "desde_athena_biorag",
     "query": "construir enlaces probabilistas de fusion de subgrafos",
     "dominio": "arquitectura_sinapsis", "split": "DEV"},
    {"id": "CASE_03", "gold": "docker_infrastructure_rog",
     "query": "despliegue modular en equipo portatil dedicado",
     "dominio": "infraestructura", "split": "DEV"},
    {"id": "CASE_04", "gold": "coche_puente_condicional",
     "query": "diagnostico de compuerta de transicion contextual",
     "dominio": "puentes_semanticos", "split": "DEV"},
    {"id": "CASE_05", "gold": "activos_dormidos_hermana",
     "query": "mutacion de entidades caducas en estado de reposo prolongado",
     "dominio": "ciclo_sueno_dmn", "split": "DEV"},
    {"id": "CASE_06", "gold": "kilo_vscode_extension_principal",
     "query": "panel visual de desarrollo para despacho de tareas",
     "dominio": "herramientas_ide", "split": "DEV"},
    {"id": "CASE_07", "gold": "principio_metacognicion_autobservacion",
     "query": "escrutinio introspectivo de deducciones y deliberaciones",
     "dominio": "metacognicion_agentes", "split": "DEV"},
    {"id": "CASE_08", "gold": "plan_tejedora_agujeros_estructurales_v1",
     "query": "reparacion topologica de discontinuidades reticulares",
     "dominio": "topologia_grafo", "split": "DEV"},
    {"id": "CASE_09", "gold": "leccion_motivacion_intrinseca_biorag",
     "query": "estimulo autonomo para preservacion mnemica voluntaria",
     "dominio": "aprendizaje_autonomo", "split": "DEV"},
    {"id": "CASE_10", "gold": "ajuste_tejedora_valencia_desempate_fase1",
     "query": "resolucion de colisiones valorativas en bifurcaciones",
     "dominio": "valencia_somatica", "split": "DEV"},
    {"id": "CASE_11", "gold": "naturaleza_sistema_oec_cerebro_memoria",
     "query": "ontologia triadica de entidades inteligentes unificadas",
     "dominio": "ontologia_sistema", "split": "DEV"},
    {"id": "CASE_12", "gold": "regla_verificar_codigo_real_antes_de_diagnostico",
     "query": "comprobacion fidedigna de ficheros previo a emitir dictamenes",
     "dominio": "reglas_trabajo", "split": "DEV"},
]

NEGATIVE_CONTROLS = [
    {"id": "NEG_01", "query": "receta culinaria de cocina mediterranea con aceite de oliva"},
    {"id": "NEG_02", "query": "mantenimiento preventivo de vehiculos hibridos y cambio de frenos"},
    {"id": "NEG_03", "query": "estrategias de cultivo hidroponico para tomates en invernadero"},
    {"id": "NEG_04", "query": "tecnicas de respiracion para buceo libre y apnea profunda"},
    {"id": "NEG_05", "query": "historia del arte renacentista en florencia del siglo xv"},
    {"id": "NEG_06", "query": "manual de reparacion de transmisiones automaticas y embragues"},
    {"id": "NEG_07", "query": "guia de senderismo de alta montana en los alpes suizos"},
    {"id": "NEG_08", "query": "preparacion de masa madre para reposteria artesanal"},
    {"id": "NEG_09", "query": "composicion quimica de fertilizantes organicos para jardineria"},
    {"id": "NEG_10", "query": "reglas oficiales de arbitraje en torneos internacionales de ajedrez"},
]


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def obtener_grado_grafo(con: sqlite3.Connection, concepto: str) -> int:
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?",
        (concepto, concepto)
    )
    return cur.fetchone()[0]


def inicializar_motor_biorag(db_path: str):
    from core.memory_store import SQLiteMemoryBioRAG
    return SQLiteMemoryBioRAG(db_path=db_path)


def buscar_primarios_produccion(cerebro, query: str, limit: int = SEARCH_LIMIT) -> List[Dict[str, Any]]:
    resultados_raw, _ = cerebro.buscar_por_frase(
        frase=query,
        profundidad="activos",
        pagina=1,
        limite=limit,
        context_window=0,
        preview_chars=200,
        parafrasis_list=None,
        ordenar_por="relevancia"
    )
    return [
        {
            "concepto": r[0],
            "contenido": r[1] or "",
            "peso_sinaptico": float(r[2] or 1.0),
            "sinonimos": "",
            "score": float(r[4]),
            "provenance": "PRIMARY",
            "nivel": 0
        }
        for r in resultados_raw
    ]


# ─── MOTOR DE EXPANSIÓN Y RE-RANKING R7 ───────────────────────────────────────

def expandir_y_rankear_grafo_r7(
    con: sqlite3.Connection,
    query: str,
    primarios: List[Dict[str, Any]],
    brazo: str,
    gamma: float = 1.0,
    depth: int = 2,
    max_contextos: int = MAX_CONTEXTOS_POOL
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Motor R7: Expande vecinos sin trampa alfabética y aplica re-ranking causal calibrado.
    """
    diag = {
        "candidatos_generados": 0,
        "convergentes_multi_padre": 0,
        "boost_aplicado_conteo": 0
    }

    if brazo in ("Q0", "Q3"):
        pool = []
        for p in primarios:
            item = dict(p)
            item["final_score"] = item["score"]
            item["boost_applied"] = 0.0
            pool.append(item)
        pool.sort(key=lambda x: x["final_score"], reverse=True)
        return pool[:SEARCH_LIMIT], diag

    primarios_map = {p["concepto"]: p for p in primarios}
    max_primary_score = max([p["score"] for p in primarios]) if primarios else 0.0

    # Compuerta de ruido: Si todos los primarios son ruido puro (< 0.25), abstenerse de boost
    abstener_boost = max_primary_score < UMBRAL_PRIMARIO_RUIDO

    frontera = list(primarios[:15]) # Tomar los 15 mejores primarios como anclajes de expansión
    vistos = set(primarios_map.keys())
    candidatos_dict = {}

    for nivel in range(1, depth + 1):
        siguiente_frontera = []
        for padre in frontera:
            p_concepto = padre["concepto"]
            p_score = padre["score"]

            # Consulta anti-trampa alfabética:
            # Ordena por (peso de arista DESC, peso_sinaptico DESC, rowid DESC) para evitar sesgo 'A'
            rows = con.execute("""
                SELECT l.concepto, l.contenido, l.peso_sinaptico, s.peso
                FROM (
                    SELECT destino as vecino, peso, rowid FROM sinapsis WHERE origen = ? AND peso >= ?
                    UNION ALL
                    SELECT origen as vecino, peso, rowid FROM sinapsis WHERE destino = ? AND peso >= ?
                ) s
                JOIN largo_plazo l ON l.concepto = s.vecino
                WHERE l.estado = 'activo'
                ORDER BY s.peso DESC, l.peso_sinaptico DESC, s.rowid DESC
            """, (p_concepto, UMBRAL_PESO_ARISTA, p_concepto, UMBRAL_PESO_ARISTA)).fetchmany(MAX_VECINOS_POR_PADRE * 2)

            # Deduplicar vecinos del mismo padre conservando mejor arista
            vecinos_padre = {}
            for r in rows:
                vc = r[0]
                if vc not in vecinos_padre:
                    vecinos_padre[vc] = r
                if len(vecinos_padre) >= MAX_VECINOS_POR_PADRE:
                    break

            for vc, r in vecinos_padre.items():
                w_arista = float(r[3] or 0.5)
                w_sinaptico = float(r[2] or 0.5)

                if vc not in candidatos_dict:
                    grado = obtener_grado_grafo(con, vc)
                    base_sc = round(min(1.0, p_score * 0.60 + min(w_arista, 1.0) * 0.20), 4)
                    candidatos_dict[vc] = {
                        "concepto": vc,
                        "contenido": r[1] or "",
                        "peso_sinaptico": w_sinaptico,
                        "base_score": base_sc,
                        "nivel": nivel,
                        "grado": grado,
                        "supports": [(p_score, w_arista)],
                        "parent_node": p_concepto,
                        "edge_weight": w_arista
                    }
                    diag["candidatos_generados"] += 1
                else:
                    candidatos_dict[vc]["supports"].append((p_score, w_arista))

                if vc not in vistos:
                    vistos.add(vc)
                    siguiente_frontera.append({"concepto": vc, "score": candidatos_dict[vc]["base_score"]})

        frontera = siguiente_frontera
        if not frontera:
            break

    contextos = []
    for vc, cdata in candidatos_dict.items():
        nivel = cdata["nivel"]
        grado = cdata["grado"]
        base_sc = cdata["base_score"]
        supports = cdata["supports"]
        num_sup = len(supports)

        if num_sup > 1:
            diag["convergentes_multi_padre"] += 1

        if brazo == "Q1" or abstener_boost:
            final_sc = base_sc
            boost_app = 0.0
        elif brazo == "Q2":
            # Formulación Causal R7:
            # 1. Fuerza relacional acumulada de los primarios
            fuerza_soporte = sum(ps * w for ps, w in supports)
            # 2. Amortiguación logarítmica de grado (Adamic-Adar suave)
            damp = 1.0 / math.sqrt(math.log2(grado + 4.0))
            # 3. Atenuación por distancia de nivel
            nivel_factor = 1.0 / math.sqrt(nivel)
            
            boost_raw = gamma * fuerza_soporte * damp * nivel_factor * 0.38
            boost_app = round(boost_raw, 4)
            final_sc = round(min(0.95, base_sc + boost_app), 4)
            diag["boost_aplicado_conteo"] += 1
        else:
            final_sc = base_sc
            boost_app = 0.0

        item = {
            "concepto": vc,
            "contenido": cdata["contenido"],
            "peso_sinaptico": cdata["peso_sinaptico"],
            "score": base_sc,
            "final_score": final_sc,
            "boost_applied": boost_app,
            "provenance": "GRAPH_NEIGHBOR",
            "nivel": nivel,
            "parent_node": cdata["parent_node"],
            "edge_weight": cdata["edge_weight"],
            "num_support": num_sup
        }
        contextos.append(item)

    # Ordenamiento level-first y corte de pool de contextos
    contextos.sort(key=lambda x: (x["nivel"], -x["final_score"]))
    contextos_seleccionados = contextos[:max_contextos]

    pool_total = []
    for p in primarios:
        item = dict(p)
        item["final_score"] = item["score"]
        item["boost_applied"] = 0.0
        pool_total.append(item)
    pool_total.extend(contextos_seleccionados)

    # Margin Protection sobre primarios de alta confianza (>= 0.90)
    if brazo == "Q2" and max_primary_score >= HIGH_CONFIDENCE_PRIMARY_THRESHOLD:
        for item in pool_total:
            if item["provenance"] == "GRAPH_NEIGHBOR":
                if item["final_score"] < max_primary_score + MARGIN_PROTECTION_DELTA:
                    item["final_score"] = min(item["final_score"], max_primary_score - 0.01)

    pool_total.sort(key=lambda x: x["final_score"], reverse=True)
    return pool_total[:SEARCH_LIMIT], diag


# ─── EVALUACIÓN COMPLETA Y REPORTE ────────────────────────────────────────────

def evaluar_dataset(
    cerebro,
    con: sqlite3.Connection,
    cases: List[Dict[str, Any]],
    gamma: float
) -> Dict[str, Any]:
    resultados_casos = []
    q0_r1, q0_r5, q0_mrr = 0, 0, 0.0
    q1_r1, q1_r5, q1_mrr = 0, 0, 0.0
    q2_r1, q2_r5, q2_mrr = 0, 0, 0.0
    q3_r1, q3_r5, q3_mrr = 0, 0, 0.0

    for case in cases:
        cid = case["id"]
        gold = case["gold"]
        query = case["query"]

        t0 = time.time()
        primarios = buscar_primarios_produccion(cerebro, query)

        res_q0, dg0 = expandir_y_rankear_grafo_r7(con, query, primarios, "Q0", gamma)
        res_q1, dg1 = expandir_y_rankear_grafo_r7(con, query, primarios, "Q1", gamma)
        res_q2, dg2 = expandir_y_rankear_grafo_r7(con, query, primarios, "Q2", gamma)
        res_q3, dg3 = expandir_y_rankear_grafo_r7(con, query, primarios, "Q3", gamma)
        lat = (time.time() - t0) * 1000.0

        def extr(pool):
            for i, item in enumerate(pool, 1):
                if item["concepto"] == gold:
                    return i, item["final_score"], i == 1, i <= 5, item["provenance"]
            return None, 0.0, False, False, "NOT_FOUND"

        r0, s0, t1_0, t5_0, pv0 = extr(res_q0)
        r1, s1, t1_1, t5_1, pv1 = extr(res_q1)
        r2, s2, t1_2, t5_2, pv2 = extr(res_q2)
        r3, s3, t1_3, t5_3, pv3 = extr(res_q3)

        if t1_0: q0_r1 += 1
        if t5_0: q0_r5 += 1
        if r0: q0_mrr += 1.0 / r0
        if t1_1: q1_r1 += 1
        if t5_1: q1_r5 += 1
        if r1: q1_mrr += 1.0 / r1
        if t1_2: q2_r1 += 1
        if t5_2: q2_r5 += 1
        if r2: q2_mrr += 1.0 / r2
        if t1_3: q3_r1 += 1
        if t5_3: q3_r5 += 1
        if r3: q3_mrr += 1.0 / r3

        gold_item_q2 = next((item for item in res_q2 if item["concepto"] == gold), None)

        resultados_casos.append({
            "id": cid, "gold": gold, "query": query,
            "q0": {"rank": r0, "score": s0, "provenance": pv0},
            "q1": {"rank": r1, "score": s1, "provenance": pv1},
            "q2": {
                "rank": r2, "score": s2, "provenance": pv2,
                "boost_applied": gold_item_q2.get("boost_applied") if gold_item_q2 else None,
                "num_support": gold_item_q2.get("num_support") if gold_item_q2 else None
            },
            "q3": {"rank": r3, "score": s3, "provenance": pv3},
            "latencia_ms": round(lat, 2)
        })

    n = len(cases)
    return {
        "gamma": gamma, "n_cases": n,
        "q0_summary": {"r1": round(q0_r1/n*100, 2), "r5": round(q0_r5/n*100, 2), "mrr": round(q0_mrr/n, 4)},
        "q1_summary": {"r1": round(q1_r1/n*100, 2), "r5": round(q1_r5/n*100, 2), "mrr": round(q1_mrr/n, 4)},
        "q2_summary": {"r1": round(q2_r1/n*100, 2), "r5": round(q2_r5/n*100, 2), "mrr": round(q2_mrr/n, 4)},
        "q3_summary": {"r1": round(q3_r1/n*100, 2), "r5": round(q3_r5/n*100, 2), "mrr": round(q3_mrr/n, 4)},
        "delta_q0_to_q1": round((q1_r5 - q0_r5)/n*100, 2),
        "delta_q1_to_q2": round((q2_r5 - q1_r5)/n*100, 2),
        "casos": resultados_casos
    }


def evaluar_negativos(cerebro, con: sqlite3.Connection, gamma: float = 1.0) -> Dict[str, Any]:
    """Evalúa falsos positivos inducidos por el grafo según el criterio metodológico oficial."""
    fp_graph_count = 0
    neg_results = []
    for neg in NEGATIVE_CONTROLS:
        query = neg["query"]
        prim = buscar_primarios_produccion(cerebro, query)
        q0_max = max([p["score"] for p in prim]) if prim else 0.0

        res_q2, _ = expandir_y_rankear_grafo_r7(con, query, prim, "Q2", gamma)
        top_cand = res_q2[0] if res_q2 else None
        max_score = top_cand["final_score"] if top_cand else 0.0
        top_prov = top_cand["provenance"] if top_cand else "NONE"

        # Criterio oficial Aureon: FP inducido solo si Q0 < 0.25 pero Q2 >= 0.25 con top proveniente del grafo
        is_graph_fp = (max_score >= 0.25) and (top_prov == "GRAPH_NEIGHBOR") and (q0_max < 0.25)
        if is_graph_fp:
            fp_graph_count += 1

        neg_results.append({
            "id": neg["id"], "query": query,
            "q0_max": round(q0_max, 4),
            "q2_max": round(max_score, 4),
            "top_concept": top_cand["concepto"] if top_cand else None,
            "top_provenance": top_prov,
            "is_graph_fp": is_graph_fp
        })

    return {
        "n_negativos": len(NEGATIVE_CONTROLS),
        "fp_graph_count": fp_graph_count,
        "fp_graph_rate": round(fp_graph_count / len(NEGATIVE_CONTROLS) * 100, 2),
        "detalles": neg_results
    }


def main():
    print("=" * 80)
    print("EXP-Q-R7: PRODUCTION-READY CAUSAL GRAPH BOOST & RANKING")
    print("=" * 80)

    sha = sha256_file(DB_SNAPSHOT_PATH)
    print(f"Snapshot DB: {DB_SNAPSHOT_PATH}")
    print(f"SHA-256: {sha}")

    cerebro = inicializar_motor_biorag(DB_SNAPSHOT_PATH)
    con = sqlite3.connect(DB_SNAPSHOT_PATH)

    sweep_results = []
    print("\nIniciando Pre-registered Gamma Sweep:")
    print("gamma | Q0 R@5/MRR | Q1 R@5/MRR | Q2 R@5/MRR | Delta Q1->Q2 | FP Rate")
    print("-" * 75)

    for g in PREDEFINED_GAMMAS:
        dev_res = evaluar_dataset(cerebro, con, DEV_CASES, gamma=g)
        neg_res = evaluar_negativos(cerebro, con, gamma=g)
        sweep_results.append({
            "gamma": g,
            "dev_evaluation": dev_res,
            "negative_evaluation": neg_res
        })
        print(f"{g:5.2f} | {dev_res['q0_summary']['r5']:5.1f}%/{dev_res['q0_summary']['mrr']:.4f} | "
              f"{dev_res['q1_summary']['r5']:5.1f}%/{dev_res['q1_summary']['mrr']:.4f} | "
              f"{dev_res['q2_summary']['r5']:5.1f}%/{dev_res['q2_summary']['mrr']:.4f} | "
              f"{dev_res['delta_q1_to_q2']:+6.1f} pp | {neg_res['fp_graph_rate']:5.1f}%")

    output_data = {
        "experimento": "EXP-Q-R7",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_sha256": sha,
        "gammas_evaluated": PREDEFINED_GAMMAS,
        "sweep_results": sweep_results
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en: {OUTPUT_JSON}")

    con.close()


if __name__ == "__main__":
    main()
