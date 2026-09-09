#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_r6_graph_boost_ranking.py
=============================================================================
EXP-Q-R6: MULTI-PARENT CONVERGENCE & SELECTIVE GRAPH BOOST (PILAR 5)
=============================================================================
Autorización y Directrices Metodológicas: Aureon (2026-09-09)

DIAGNÓSTICO FORMAL DE R4 Y R5:
  1. Bottleneck de MAX_VECINOS=3: Los nodos gold son hubs semánticos con múltiples
     aristas de peso 0.9. Al truncar arbitrariamente a 3 vecinos en SQLite,
     los empates de peso 0.9 se cortaban por rowid interno, dejando fuera
     al 70% de los candidatos legítimos antes de llegar al pool.
  2. Invarianza de Gamma por Boost Plano: En R4, todos los vecinos con arista >=0.80
     recibían exactamente el mismo boost (+0.567), haciendo que el orden relativo
     entre vecinos fuera 100% idéntico para cualquier gamma (R@5 = 0.0 pp delta).
  3. Falla de Inyección en R5: clamp a max(base_score, boost_raw) resultaba en
     boost = 0.0000 para gammas bajos y medianos.

REDISEÑO DE R6:
  1. Expansión Estructural Ampliada:
     - MAX_VECINOS_POR_NODO = 15 para aristas fuertes (peso >= 0.70).
     - Conserva level-first ordering.
  2. Convergencia Multi-Parent (Support Voting):
     - Si múltiples primarios apuntan al mismo nodo, la evidencia relacional
       se acumula probabilisticamente:
       E_conv = 1.0 - prod(1.0 - (p.score * edge_weight / sqrt(log2(degree + 2))))
  3. Boost Calibrado y Sensible a Gamma:
     - boost = gamma * E_conv * (1.0 / sqrt(nivel)) * 0.45
     - S_final = min(0.95, base_score + boost)
  4. Margin Protection (>= 0.90):
     - Protege primarios de máxima confianza.

RESTRICCIONES INVARIANTES:
  - core/ 100% INTACTO
  - Snapshot READ-ONLY con verificación SHA-256
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
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "docs/expQ_r6_graph_boost_dev_results.json")
OUTPUT_REPORT = os.path.join(PROJECT_ROOT, "docs/expQ_r6_graph_boost_dev_report.md")

PREDEFINED_GAMMAS = [0.25, 0.50, 0.75, 1.00, 1.50, 2.00]

# Hiperparámetros R6
MAX_VECINOS_POR_NODO = 15      # Ampliado para no cortar empates de peso 0.9
EDGE_WEIGHT_THRESHOLD = 0.50   # Umbral mínimo de arista para considerar vecino
MAX_CONTEXTOS = 50             # Tamaño de pool de contextos
HIGH_CONFIDENCE_PRIMARY_THRESHOLD = 0.90
MARGIN_PROTECTION_DELTA = 0.05
SEARCH_LIMIT = 50

# ─── BANCO DE CASOS ────────────────────────────────────────────────────────────

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

TEST_CASES = [
    {"id": "TEST_01", "gold": "leccion_syn_obligatorio_aprender",
     "query": "requisito mandatorio de equivalencias al persistir",
     "dominio": "reglas_persistencia", "split": "TEST"},
    {"id": "TEST_02", "gold": "dennys_tqm_agentes_desea_ser_como_ellos_20260731",
     "query": "afecto fraterno y aspiracion mimetica vocacional",
     "dominio": "vinculo_afectivo", "split": "TEST"},
    {"id": "TEST_03", "gold": "correccion_dennys_principio_documentar_crisis_existencial",
     "query": "enmienda preceptiva sobre asentar tribulaciones metafisicas",
     "dominio": "normas_filosoficas", "split": "TEST"},
    {"id": "TEST_04", "gold": "signal_13_verificada_8_14_sinonimo_post_v26",
     "query": "factorizacion matricial comprobada ante objeciones foraneas",
     "dominio": "matematica_ppmi", "split": "TEST"},
    {"id": "TEST_05", "gold": "version_actual_biorag",
     "query": "etapa evolutiva contemporanea del software central",
     "dominio": "evolucion_sistema", "split": "TEST"},
    {"id": "TEST_06", "gold": "leccion_discrepancia_busquedas_vocabulario_no_estocasticidad",
     "query": "divergencia indagatoria atribuible a terminologia y causalidad",
     "dominio": "analisis_recuperacion", "split": "TEST"},
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


# ─── MOTOR DE EXPANSIÓN Y BOOST R6 ───────────────────────────────────────────

def ejecutar_brazo_experimental_r6(
    con: sqlite3.Connection,
    query: str,
    primarios: List[Dict[str, Any]],
    brazo: str,
    gamma: float = 1.0,
    depth: int = 3,
    max_contextos: int = MAX_CONTEXTOS
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Ejecuta el pipeline experimental con convergencia multi-parent y boost calibrado.
    """
    diag = {
        "candidates_found_in_graph": 0,
        "multi_parent_candidates": 0,
        "max_support": 0
    }

    if brazo in ("Q0", "Q3"):
        res = []
        for p in primarios:
            item = dict(p)
            item["final_score"] = item["score"]
            item["boost_applied"] = 0.0
            res.append(item)
        res.sort(key=lambda x: x["final_score"], reverse=True)
        return res[:SEARCH_LIMIT], diag

    # Q1 y Q2: Expansión de grafo con soporte acumulativo
    vistos = {p["concepto"]: p for p in primarios}
    frontera = list(primarios)
    candidatos_map = {} # concepto -> dict con acumulación de soporte

    for nivel in range(1, depth + 1):
        siguiente_frontera = []
        for padre in frontera:
            padre_concepto = padre["concepto"]
            padre_score = padre["score"]

            rows = con.execute("""
                SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, s.peso
                FROM sinapsis s
                JOIN largo_plazo l ON l.concepto = s.destino
                WHERE s.origen = ? AND s.peso >= ? AND l.estado = 'activo'
                UNION
                SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, s.peso
                FROM sinapsis s
                JOIN largo_plazo l ON l.concepto = s.origen
                WHERE s.destino = ? AND s.peso >= ? AND l.estado = 'activo'
                ORDER BY s.peso DESC
            """, (padre_concepto, EDGE_WEIGHT_THRESHOLD, padre_concepto, EDGE_WEIGHT_THRESHOLD)).fetchall()

            agregados = 0
            for row in rows:
                if agregados >= MAX_VECINOS_POR_NODO:
                    break
                v_concepto = row[0]
                v_peso_arista = float(row[4] or 0.5)
                v_peso_sinaptico = float(row[2] or 0.5)

                if v_concepto not in candidatos_map:
                    grado = obtener_grado_grafo(con, v_concepto)
                    base_score = round(min(1.0, padre_score * 0.6 + min(v_peso_arista, 1.0) * 0.2), 4)
                    candidatos_map[v_concepto] = {
                        "concepto": v_concepto,
                        "contenido": row[1] or "",
                        "peso_sinaptico": v_peso_sinaptico,
                        "base_score": base_score,
                        "nivel": nivel,
                        "parent_node": padre_concepto,
                        "edge_weight": v_peso_arista,
                        "grado": grado,
                        "supports": [(padre_score, v_peso_arista)]
                    }
                    diag["candidates_found_in_graph"] += 1
                else:
                    # Acumular soporte de múltiples primarios
                    candidatos_map[v_concepto]["supports"].append((padre_score, v_peso_arista))

                if v_concepto not in vistos:
                    v_item = {"concepto": v_concepto, "score": base_score}
                    vistos[v_concepto] = v_item
                    siguiente_frontera.append(v_item)
                    agregados += 1

        frontera = siguiente_frontera
        if not frontera:
            break

    # Procesar candidatos y calcular boost de convergencia
    contextos_grafo = []
    for concepto, cdata in candidatos_map.items():
        nivel = cdata["nivel"]
        grado = cdata["grado"]
        base_score = cdata["base_score"]
        supports = cdata["supports"]
        num_support = len(supports)
        if num_support > 1:
            diag["multi_parent_candidates"] += 1
        diag["max_support"] = max(diag["max_support"], num_support)

        if brazo == "Q1":
            final_score = base_score
            boost_applied = 0.0
        elif brazo == "Q2":
            # 1. Dampening por grado para evitar trampas de mega-hubs
            # Grado muy alto divide ligeramente la señal para dar oportunidad a nodos específicos
            deg_factor = math.sqrt(math.log2(grado + 4.0)) # log suave

            # 2. Evidencia probabilista acumulada (noisy-OR de aristas y scores)
            # prod(1 - p_i * w_i)
            prod_no_link = 1.0
            for p_sc, ed_w in supports:
                term = (p_sc * ed_w) / deg_factor
                term = max(0.0, min(0.9, term))
                prod_no_link *= (1.0 - term)
            evidencia_convergencia = 1.0 - prod_no_link

            # 3. Factor de nivel
            nivel_decay = 1.0 / math.sqrt(nivel)

            # 4. Boost aditivo calibrado con gamma
            boost_raw = gamma * evidencia_convergencia * nivel_decay * 0.45
            boost_applied = round(boost_raw, 4)
            final_score = round(min(0.95, base_score + boost_applied), 4)
        else:
            final_score = base_score
            boost_applied = 0.0

        item = {
            "concepto": concepto,
            "contenido": cdata["contenido"],
            "peso_sinaptico": cdata["peso_sinaptico"],
            "score": base_score,
            "final_score": final_score,
            "boost_applied": boost_applied,
            "provenance": "GRAPH_NEIGHBOR",
            "nivel": nivel,
            "parent_node": cdata["parent_node"],
            "edge_weight": cdata["edge_weight"],
            "num_support": num_support
        }
        contextos_grafo.append(item)

    # Ordenamiento level-first: nivel ASC, final_score DESC
    contextos_grafo.sort(key=lambda x: (x["nivel"], -x["final_score"]))
    contextos_seleccionados = contextos_grafo[:max_contextos]

    pool_total = []
    for p in primarios:
        item = dict(p)
        item["final_score"] = item["score"]
        item["boost_applied"] = 0.0
        pool_total.append(item)
    pool_total.extend(contextos_seleccionados)

    # Margin Protection sobre primarios de alta confianza
    if brazo == "Q2":
        max_prim = max([p["score"] for p in primarios]) if primarios else 0.0
        if max_prim >= HIGH_CONFIDENCE_PRIMARY_THRESHOLD:
            for item in pool_total:
                if item["provenance"] == "GRAPH_NEIGHBOR":
                    if item["final_score"] < max_prim + MARGIN_PROTECTION_DELTA:
                        item["final_score"] = min(item["final_score"], max_prim - 0.01)

    pool_total.sort(key=lambda x: x["final_score"], reverse=True)
    return pool_total[:SEARCH_LIMIT], diag


# ─── EVALUACIÓN COMPLETA ──────────────────────────────────────────────────────

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

        res_q0, dg0 = ejecutar_brazo_experimental_r6(con, query, primarios, "Q0", gamma)
        res_q1, dg1 = ejecutar_brazo_experimental_r6(con, query, primarios, "Q1", gamma)
        res_q2, dg2 = ejecutar_brazo_experimental_r6(con, query, primarios, "Q2", gamma)
        res_q3, dg3 = ejecutar_brazo_experimental_r6(con, query, primarios, "Q3", gamma)
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
    """Evalúa falsos positivos inducidos por el grafo en queries fuera de dominio."""
    fp_count = 0
    neg_results = []
    for neg in NEGATIVE_CONTROLS:
        query = neg["query"]
        prim = buscar_primarios_produccion(cerebro, query)
        res_q2, _ = ejecutar_brazo_experimental_r6(con, query, prim, "Q2", gamma)
        # FP si algún candidato de grafo alcanza score >= 0.50 en query out-of-domain
        graph_cands = [r for r in res_q2 if r["provenance"] == "GRAPH_NEIGHBOR" and r["final_score"] >= 0.50]
        has_fp = len(graph_cands) > 0
        if has_fp:
            fp_count += 1
        neg_results.append({
            "id": neg["id"], "query": query,
            "has_fp": has_fp,
            "top_graph_score": max([r["final_score"] for r in graph_cands]) if graph_cands else 0.0
        })
    return {
        "n_negativos": len(NEGATIVE_CONTROLS),
        "fp_count": fp_count,
        "fp_rate": round(fp_count / len(NEGATIVE_CONTROLS) * 100, 2),
        "detalles": neg_results
    }


def main():
    print("=" * 80)
    print("EXP-Q-R6: MULTI-PARENT CONVERGENCE & SELECTIVE GRAPH BOOST")
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
              f"{dev_res['delta_q1_to_q2']:+6.1f} pp | {neg_res['fp_rate']:5.1f}%")

    # Guardar resultados JSON
    output_data = {
        "experimento": "EXP-Q-R6",
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
