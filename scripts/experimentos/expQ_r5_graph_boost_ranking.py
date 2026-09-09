#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expQ_r5_graph_boost_ranking.py
=============================================================================
EXP-Q-R5: CAUSAL GRAPH BOOST & MONOTONIC RANKING (PILAR 5) — Revisión 5
=============================================================================
Autorización y Directrices Metodológicas: Aureon (2026-09-09)

DIAGNÓSTICO DE R4 (2026-09-09):
  El Theme Gate en R4 rechazaba el 100% de los candidatos de grafo bajo
  'insufficient_seed_confidence' o 'none'. Las condiciones del gate
  (solapamiento de tokens de la query con NOMBRES de dimensiones semánticas,
  o pertenencia a grupos semánticos) son imposibles de satisfacer en el
  régimen de abismo léxico: las queries usan vocabulario deliberadamente
  disjunto del contenido del nodo gold.

  Contradicción epistemológica: el gate filtraba exactamente los casos
  que el experimento intenta rescatar.

REDISEÑO DE R5:
  1. Theme Gate Estructural (evidencia 100% independiente de la query):
     - Arista sináptica >= 0.55 (reducido de 0.80).
     - Peso sináptico del vecino >= 0.70 (nodo consolidado en memoria).
     - Grado en grafo >= 2 (hub con múltiples conexiones).
     Cualquiera de las 3 es suficiente.

  2. Score Injection (reemplaza boost aditivo débil):
     s_inj = gamma * (w_arista * 0.60 + w_sin * 0.40) * gate_score / sqrt(nivel)
     Clampado a [base_score, 0.95].

  3. Margin Protection ajustada a >= 0.90 (antes 0.85).

  4. Q3 Control = Q0 (mismos scores), para confirmar que Q3 ≈ Q0.

  5. Diagnóstico detallado por caso: gate_passed, gate_rejected, razones.

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
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "docs/expQ_r5_graph_boost_dev_results.json")
OUTPUT_REPORT = os.path.join(PROJECT_ROOT, "docs/expQ_r5_graph_boost_dev_report.md")

PREDEFINED_GAMMAS = [0.25, 0.50, 0.75, 1.00, 1.50, 2.00]

# Theme Gate estructural (sin semántica léxica)
GATE_EDGE_WEIGHT_MIN = 0.55   # Umbral de arista sináptica (reducido de 0.80)
GATE_SINAPTICO_MIN = 0.70     # Peso sináptico mínimo del vecino
GATE_DEGREE_MIN = 2           # Grado mínimo en grafo (hub estructural)

# Score Injection: combinación lineal de evidencia relacional
INJECT_ALPHA = 0.60   # Contribución del peso de la arista
INJECT_BETA = 0.40    # Contribución del peso sináptico del vecino

# Margin Protection: solo protege primarios de muy alta confianza
HIGH_CONFIDENCE_PRIMARY_THRESHOLD = 0.90
MARGIN_PROTECTION_DELTA = 0.05

MAX_VECINOS_POR_NODO = 3
MAX_CONTEXTOS_BASE = 15
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


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def sha256_file(filepath: str) -> str:
    """Calcula SHA-256 del snapshot para verificar integridad."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_node_full_text(con: sqlite3.Connection, concepto: str) -> str:
    """Recupera texto completo del nodo para auditoría de overlap léxico."""
    cur = con.cursor()
    cur.execute(
        "SELECT contenido, sinonimos, asociaciones FROM largo_plazo WHERE concepto = ?",
        (concepto,)
    )
    row = cur.fetchone()
    if not row:
        return ""
    return f"{concepto} {row[0] or ''} {row[1] or ''} {row[2] or ''}"


def obtener_grado_grafo(con: sqlite3.Connection, concepto: str) -> int:
    """
    Cuenta aristas del nodo en el grafo sináptico.
    Evidencia estructural: grado alto = hub bien conectado = más confiable.
    """
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?",
        (concepto, concepto)
    )
    return cur.fetchone()[0]


# ─── AUDITORÍA MULTICANAL ─────────────────────────────────────────────────────

def auditar_multicanal(
    con: sqlite3.Connection,
    case: Dict[str, Any],
    fts_primaries: List[str]
) -> Dict[str, Any]:
    """
    Verifica que el caso sea un 'abismo léxico genuino':
    literal_overlap = 0 y stem_overlap = 0 entre query y gold_full_text.
    También audita 7 canales de conectividad adicionales.
    """
    cur = con.cursor()
    gold = case["gold"]
    query = case["query"]

    q_tokens = tokenizar(query)
    q_stems = {stem_simple(t) for t in q_tokens if len(t) > 2 and t not in SPANISH_STOPWORDS}

    node_text = get_node_full_text(con, gold)
    node_tokens = tokenizar(node_text)
    node_stems = {stem_simple(t) for t in node_tokens if len(t) > 2 and t not in SPANISH_STOPWORDS}

    literal_overlap = len(set(q_tokens).intersection(set(node_tokens)))
    stem_overlap = len(q_stems.intersection(node_stems))

    cur.execute("SELECT canonical_node FROM concept_hubs WHERE canonical_node = ?", (gold,))
    alias_overlap = 1 if cur.fetchone() else 0

    cur.execute("SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (gold,))
    syn_row = cur.fetchone()
    syn_text = (syn_row[0] or "") if syn_row else ""
    synonym_overlap = len(set(q_tokens).intersection(set(tokenizar(syn_text))))

    cur.execute("SELECT asociaciones FROM largo_plazo WHERE concepto = ?", (gold,))
    assoc_row = cur.fetchone()
    assoc_text = (assoc_row[0] or "") if assoc_row else ""
    association_path = any(t in assoc_text for t in q_tokens if len(t) > 3)

    cur.execute("""
        SELECT COUNT(*) FROM concept_hub_bridges b
        JOIN concept_hubs h ON b.hub_id = h.hub_id
        WHERE h.canonical_node = ?
    """, (gold,))
    concept_hub_path = cur.fetchone()[0] > 0

    shortest_path = 999
    for p in fts_primaries:
        if p == gold:
            shortest_path = 0
            break
        cur.execute(
            "SELECT COUNT(*) FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
            (p, gold, gold, p)
        )
        if cur.fetchone()[0] > 0:
            shortest_path = min(shortest_path, 1)
            continue
        cur.execute("""
            SELECT COUNT(*) FROM sinapsis s1
            JOIN sinapsis s2 ON (s1.destino = s2.origen OR s1.destino = s2.destino)
            WHERE (s1.origen=? OR s1.destino=?) AND (s2.origen=? OR s2.destino=?)
        """, (p, p, gold, gold))
        if cur.fetchone()[0] > 0:
            shortest_path = min(shortest_path, 2)
            continue
        if shortest_path > 2:
            shortest_path = min(shortest_path, 3)

    return {
        "literal_overlap": literal_overlap,
        "stem_overlap": stem_overlap,
        "alias_overlap": alias_overlap,
        "synonym_overlap": synonym_overlap,
        "association_path": association_path,
        "concept_hub_path": concept_hub_path,
        "graph_path_distance": shortest_path if shortest_path != 999 else -1
    }


# ─── MOTOR PRIMARIO ───────────────────────────────────────────────────────────

def inicializar_motor_biorag(db_path: str):
    from core.memory_store import SQLiteMemoryBioRAG
    return SQLiteMemoryBioRAG(db_path=db_path)


def buscar_primarios_produccion(cerebro, query: str, limit: int = SEARCH_LIMIT) -> List[Dict[str, Any]]:
    """
    Búsqueda primaria real (FTS5 + PPMI + QCR + Jaccard) con context_window=0.
    Es la línea base del sistema de producción sin modificación alguna.
    """
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


# ─── THEME GATE ESTRUCTURAL (R5) ──────────────────────────────────────────────

def evaluar_theme_gate_estructural(
    con: sqlite3.Connection,
    candidato_concepto: str,
    peso_arista: float,
    peso_sinaptico_vecino: float
) -> Dict[str, Any]:
    """
    Theme Gate R5: evidencia 100% estructural, independiente de la query.

    Principio: en abismo léxico NO puede haber solapamiento léxico entre
    query y candidato (es la definición del problema). El gate mide la
    CALIDAD RELACIONAL del nodo, no su similitud con la query.

    3 condiciones (basta una para pasar):
    1. strong_edge: peso_arista >= GATE_EDGE_WEIGHT_MIN (0.55).
       Relación directa y establecida entre padre y vecino en el grafo.
    2. consolidated_node: peso_sinaptico_vecino >= GATE_SINAPTICO_MIN (0.70).
       El vecino tiene alta relevancia sistémica en la memoria a largo plazo.
    3. structural_hub: grado_grafo >= GATE_DEGREE_MIN (2).
       El vecino tiene múltiples conexiones: rol central en la red.

    El campo 'score' (0.0–1.0) escala la intensidad del boost para esa condición.
    """
    # Condición 1: arista fuerte
    if peso_arista >= GATE_EDGE_WEIGHT_MIN:
        return {
            "passed": True,
            "source": "strong_edge",
            "score": min(1.0, peso_arista),
            "provenance": f"arista={peso_arista:.3f}"
        }

    # Condición 2: nodo consolidado en memoria
    if peso_sinaptico_vecino >= GATE_SINAPTICO_MIN:
        return {
            "passed": True,
            "source": "consolidated_node",
            "score": min(1.0, peso_sinaptico_vecino),
            "provenance": f"w_sin={peso_sinaptico_vecino:.3f}"
        }

    # Condición 3: hub estructural
    grado = obtener_grado_grafo(con, candidato_concepto)
    if grado >= GATE_DEGREE_MIN:
        return {
            "passed": True,
            "source": "structural_hub",
            "score": min(1.0, 0.50 + grado * 0.05),
            "provenance": f"grado={grado}"
        }

    return {
        "passed": False,
        "source": "peripheral_node",
        "score": 0.0,
        "provenance": f"arista={peso_arista:.3f} w_sin={peso_sinaptico_vecino:.3f}"
    }


# ─── SCORE INJECTION (R5) ─────────────────────────────────────────────────────

def calcular_score_inyectado(
    gamma: float,
    base_score: float,
    peso_arista: float,
    peso_sinaptico: float,
    gate_score: float,
    nivel: int
) -> Tuple[float, float]:
    """
    Score Injection R5.

    Fórmula:
      s_inj = gamma * (w_arista * INJECT_ALPHA + w_sin * INJECT_BETA) * gate_score / sqrt(nivel)

    El score final se clampea a:
    - Mínimo: base_score (monotonía hacia arriba garantizada).
    - Máximo: 0.95 (reserva espacio para matches exactos del FTS5).

    Returns: (final_score, boost_applied)
    donde boost_applied = final_score - base_score >= 0.
    """
    evidencia = (
        min(peso_arista, 1.0) * INJECT_ALPHA +
        min(peso_sinaptico, 1.0) * INJECT_BETA
    )
    boost_raw = gamma * evidencia * gate_score * (1.0 / math.sqrt(nivel))
    score_inyectado = round(min(0.95, max(base_score, boost_raw)), 4)
    boost_applied = round(score_inyectado - base_score, 4)
    return score_inyectado, boost_applied


# ─── BRAZOS CAUSALES ──────────────────────────────────────────────────────────

def ejecutar_brazo_experimental(
    con: sqlite3.Connection,
    query: str,
    primarios: List[Dict[str, Any]],
    brazo: str,
    gamma: float = 1.0,
    depth: int = 3,
    max_contextos: int = 45
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Ejecuta uno de los 4 brazos causales con provenance y diagnóstico estrictos.

    Q0: Solo primarios (baseline puro, sin modificación).
    Q1: Primarios + candidatos de grafo SIN boost.
    Q2: Primarios + candidatos de grafo CON Score Injection + Theme Gate.
    Q3: Solo primarios con scores inalterados (control = Q0 replicado).

    Returns: (pool_rankeado[:SEARCH_LIMIT], diagnostico_brazo)
    """
    diag = {
        "candidates_found_in_graph": 0,
        "gate_passed": 0,
        "gate_rejected": 0,
        "gate_rejection_reasons": []
    }

    # Q0 y Q3: solo primarios sin modificación
    if brazo in ("Q0", "Q3"):
        res = []
        for p in primarios:
            item = dict(p)
            item["final_score"] = item["score"]
            item["boost_applied"] = 0.0
            res.append(item)
        res.sort(key=lambda x: x["final_score"], reverse=True)
        return res[:SEARCH_LIMIT], diag

    # Q1, Q2: expansión por grafo con level-first ordering
    vistos = {p["concepto"]: p for p in primarios}
    frontera = list(primarios)
    candidatos_con_nivel = []

    for nivel in range(1, depth + 1):
        siguiente_frontera = []
        for padre in frontera:
            padre_concepto = padre["concepto"]
            padre_score = padre["score"]

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
            """, (padre_concepto, padre_concepto)).fetchall()

            agregados = 0
            for row in rows:
                if agregados >= MAX_VECINOS_POR_NODO:
                    break
                v_concepto = row[0]
                if v_concepto in vistos:
                    continue

                v_peso_arista = float(row[5] or 0.5)
                v_peso_sinaptico = float(row[2] or 0.5)

                # Score base: hereda del padre + contribución de la arista
                base_score = round(min(1.0, padre_score * 0.6 + min(v_peso_arista, 1.0) * 0.2), 4)
                diag["candidates_found_in_graph"] += 1

                # Theme Gate estructural (independiente de la query)
                theme_info = evaluar_theme_gate_estructural(
                    con, v_concepto, v_peso_arista, v_peso_sinaptico
                )

                if brazo == "Q1":
                    final_score = base_score
                    boost_applied = 0.0
                elif brazo == "Q2":
                    if theme_info["passed"]:
                        final_score, boost_applied = calcular_score_inyectado(
                            gamma=gamma,
                            base_score=base_score,
                            peso_arista=v_peso_arista,
                            peso_sinaptico=v_peso_sinaptico,
                            gate_score=theme_info["score"],
                            nivel=nivel
                        )
                        diag["gate_passed"] += 1
                    else:
                        final_score = base_score
                        boost_applied = 0.0
                        diag["gate_rejected"] += 1
                        diag["gate_rejection_reasons"].append({
                            "concepto": v_concepto,
                            "reason": theme_info["source"],
                            "detail": theme_info["provenance"]
                        })
                else:
                    final_score = base_score
                    boost_applied = 0.0

                item = {
                    "concepto": v_concepto,
                    "contenido": row[1] or "",
                    "sinonimos": "",
                    "peso_sinaptico": v_peso_sinaptico,
                    "score": base_score,
                    "final_score": final_score,
                    "boost_applied": boost_applied,
                    "provenance": "GRAPH_NEIGHBOR",
                    "nivel": nivel,
                    "parent_node": padre_concepto,
                    "edge_weight": v_peso_arista,
                    "theme_gate": theme_info
                }
                vistos[v_concepto] = item
                siguiente_frontera.append(item)
                candidatos_con_nivel.append((item, nivel))
                agregados += 1

        frontera = siguiente_frontera
        if not frontera:
            break

    # Level-first ordering: nivel ASC, score DESC (garantiza monotonía)
    candidatos_con_nivel.sort(key=lambda x: (x[1], -x[0]["final_score"]))
    contextos_grafo = [item for item, _ in candidatos_con_nivel][:max_contextos]

    pool_total = []
    for p in primarios:
        item = dict(p)
        item["final_score"] = item["score"]
        item["boost_applied"] = 0.0
        pool_total.append(item)
    pool_total.extend(contextos_grafo)

    # Margin Protection: solo cuando hay primario de muy alta confianza (>= 0.90)
    if brazo == "Q2":
        max_prim = max([p["score"] for p in primarios]) if primarios else 0.0
        if max_prim >= HIGH_CONFIDENCE_PRIMARY_THRESHOLD:
            for item in pool_total:
                if item["provenance"] == "GRAPH_NEIGHBOR":
                    if item["final_score"] < max_prim + MARGIN_PROTECTION_DELTA:
                        item["final_score"] = min(item["final_score"], max_prim - 0.01)

    pool_total.sort(key=lambda x: x["final_score"], reverse=True)
    return pool_total[:SEARCH_LIMIT], diag


# ─── EVALUACIÓN ───────────────────────────────────────────────────────────────

def evaluar_dataset(
    cerebro,
    con: sqlite3.Connection,
    cases: List[Dict[str, Any]],
    gamma: float
) -> Dict[str, Any]:
    """Evalúa los 4 brazos causales sobre el conjunto de casos."""
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
        fts_primaries_names = [p["concepto"] for p in primarios]
        audit = auditar_multicanal(con, case, fts_primaries_names)

        res_q0, dg0 = ejecutar_brazo_experimental(con, query, primarios, "Q0", gamma)
        res_q1, dg1 = ejecutar_brazo_experimental(con, query, primarios, "Q1", gamma)
        res_q2, dg2 = ejecutar_brazo_experimental(con, query, primarios, "Q2", gamma)
        res_q3, dg3 = ejecutar_brazo_experimental(con, query, primarios, "Q3", gamma)
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
        gold_in_q2 = gold_item_q2 is not None

        resultados_casos.append({
            "id": cid, "gold": gold, "query": query,
            "audit_multicanal": audit,
            "n_primarios": len(primarios),
            "max_primary_score": round(max([p["score"] for p in primarios]) if primarios else 0.0, 4),
            "q0": {"rank": r0, "score": s0, "provenance": pv0},
            "q1": {"rank": r1, "score": s1, "provenance": pv1, "diag": dg1},
            "q2": {
                "rank": r2, "score": s2, "provenance": pv2, "diag": dg2,
                "gold_in_pool": gold_in_q2,
                "gold_detail": {
                    "boost_applied": gold_item_q2.get("boost_applied") if gold_item_q2 else None,
                    "edge_weight": gold_item_q2.get("edge_weight") if gold_item_q2 else None,
                    "parent_node": gold_item_q2.get("parent_node") if gold_item_q2 else None,
                    "theme_gate": gold_item_q2.get("theme_gate") if gold_item_q2 else None,
                } if gold_item_q2 else None
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
        "delta_q0_to_q1": {
            "delta_r1_pp": round((q1_r1-q0_r1)/n*100, 2),
            "delta_r5_pp": round((q1_r5-q0_r5)/n*100, 2),
            "delta_mrr": round((q1_mrr-q0_mrr)/n, 4)
        },
        "delta_q1_to_q2": {
            "delta_r1_pp": round((q2_r1-q1_r1)/n*100, 2),
            "delta_r5_pp": round((q2_r5-q1_r5)/n*100, 2),
            "delta_mrr": round((q2_mrr-q1_mrr)/n, 4)
        },
        "casos": resultados_casos
    }


def evaluar_negativos(cerebro, con: sqlite3.Connection, gamma: float) -> Dict[str, Any]:
    """
    Evalúa 10 controles negativos fuera de dominio.
    Un FP se define como: score Q2 >= 0.25 inducido por el grafo
    (top provenance = GRAPH_NEIGHBOR y Q0 no superaba 0.25).
    """
    fp_graph, fp_total = 0, 0
    neg_results = []

    for neg in NEGATIVE_CONTROLS:
        query = neg["query"]
        primarios = buscar_primarios_produccion(cerebro, query)
        q0_max = max([p["score"] for p in primarios]) if primarios else 0.0

        res_q2, dg2 = ejecutar_brazo_experimental(con, query, primarios, "Q2", gamma)
        max_score = res_q2[0]["final_score"] if res_q2 else 0.0
        top_prov = res_q2[0]["provenance"] if res_q2 else "NONE"
        top_concept = res_q2[0]["concepto"] if res_q2 else "NONE"

        is_graph_fp = (max_score >= 0.25) and (top_prov == "GRAPH_NEIGHBOR") and (q0_max < 0.25)
        is_total_fp = max_score >= 0.25

        if is_graph_fp: fp_graph += 1
        if is_total_fp: fp_total += 1

        neg_results.append({
            "id": neg["id"], "query": query,
            "q0_max_score": round(q0_max, 4),
            "q2_max_score": round(max_score, 4),
            "top_concept": top_concept, "top_provenance": top_prov,
            "is_graph_fp": is_graph_fp, "is_total_fp": is_total_fp,
            "gate_passed": dg2.get("gate_passed", 0),
            "gate_rejected": dg2.get("gate_rejected", 0)
        })

    return {
        "total_negativos": len(NEGATIVE_CONTROLS),
        "fp_graph_count": fp_graph,
        "fp_graph_rate": round(fp_graph / len(NEGATIVE_CONTROLS) * 100, 2),
        "fp_total_count": fp_total,
        "negativos": neg_results
    }


# ─── REPORTE ──────────────────────────────────────────────────────────────────

def generar_reporte_md(data: Dict[str, Any], filepath: str):
    """Genera el reporte markdown para revisión de Aureon."""
    sweep = data["sweep_results"]
    best_run = max(sweep, key=lambda x: (
        x["dev_evaluation"]["q2_summary"]["r5"],
        x["dev_evaluation"]["q2_summary"]["mrr"]
    ))

    lines = [
        "# EXP-Q-R5: Informe Fase DEV — Theme Gate Estructural + Score Injection",
        f"## Aureon (2026-09-09) | R5\n",
        f"- **SHA-256 DB**: `{data['db_sha256']}`",
        f"- **Gate**: arista>={data['gate_config']['edge_weight_min']}, "
        f"w_sin>={data['gate_config']['sinaptico_min']}, "
        f"grado>={data['gate_config']['degree_min']}",
        f"- **Inject**: α={data['inject_config']['alpha']}, β={data['inject_config']['beta']}",
        "",
        "---",
        "### 1. Matriz por γ\n",
        "| γ | Q0 R@5/MRR | Q1 R@5/MRR | Q2 R@5/MRR | ΔR@5(Q1→Q2) | FP Grafo |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for s in sweep:
        g = s["gamma"]
        d = s["dev_evaluation"]
        neg = s["negative_evaluation"]
        lines.append(
            f"| **{g}** | {d['q0_summary']['r5']}%/{d['q0_summary']['mrr']} "
            f"| {d['q1_summary']['r5']}%/{d['q1_summary']['mrr']} "
            f"| **{d['q2_summary']['r5']}%/{d['q2_summary']['mrr']}** "
            f"| **{d['delta_q1_to_q2']['delta_r5_pp']:+.2f}pp** "
            f"| {neg['fp_graph_count']}/{neg['total_negativos']} ({neg['fp_graph_rate']}%) |"
        )

    best_d = best_run["dev_evaluation"]
    lines += [
        "",
        "---",
        f"### 2. Desglose Caso por Caso — γ = {best_run['gamma']}\n",
        "| Caso | Gold | Q0 | Q1 | Q2 | Gate✓ | Gold@Pool | Boost |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for c in best_d["casos"]:
        gd = c["q2"].get("gold_detail")
        boost_str = f"{gd.get('boost_applied', 0.0):+.4f}" if gd else "—"
        lines.append(
            f"| **{c['id']}** | `{c['gold']}` "
            f"| {c['q0']['rank'] or '❌'} | {c['q1']['rank'] or '❌'} | **{c['q2']['rank'] or '❌'}** "
            f"| {c['q2']['diag']['gate_passed']} "
            f"| {'✅' if c['q2']['gold_in_pool'] else '❌'} "
            f"| {boost_str} |"
        )

    lines += [
        "",
        "---",
        "### 3. Diagnóstico del Theme Gate por Caso\n",
        "| Caso | Cands. Grafo | Gate✓ | Gate✗ | Razón Rechazo |",
        "|:---|:---:|:---:|:---:|:---|"
    ]

    for c in best_d["casos"]:
        dg = c["q2"]["diag"]
        reasons = dg.get("gate_rejection_reasons", [])
        reason_str = reasons[0]["reason"] if reasons else "N/A"
        lines.append(
            f"| **{c['id']}** | {dg['candidates_found_in_graph']} "
            f"| {dg['gate_passed']} | {dg['gate_rejected']} | {reason_str} |"
        )

    delta = best_d["delta_q1_to_q2"]["delta_r5_pp"]
    fp_cnt = best_run["negative_evaluation"]["fp_graph_count"]
    lines += [
        "",
        "---",
        "### 4. Veredicto\n",
        f"1. **Efecto Causal Q1→Q2**: ΔR@5 = **{delta:+.2f} pp** con γ = {best_run['gamma']}.",
        f"2. **FP Inducido por Grafo**: {fp_cnt}/10 ({best_run['negative_evaluation']['fp_graph_rate']}%).",
        "",
        "> **VEREDICTO**: " + (
            "GO — Solicitar aprobación Aureon para TEST ciego."
            if delta > 0 and fp_cnt == 0
            else "NO-GO — Requiere ajuste."
        )
    ]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("EXP-Q-R5: CAUSAL GRAPH BOOST — Theme Gate Estructural + Score Injection")
    print("=" * 80)

    if not os.path.exists(DB_SNAPSHOT_PATH):
        raise FileNotFoundError(f"Snapshot no encontrado: {DB_SNAPSHOT_PATH}")

    db_sha = sha256_file(DB_SNAPSHOT_PATH)
    print(f"[INFO] Snapshot: {DB_SNAPSHOT_PATH}")
    print(f"[INFO] SHA-256:  {db_sha}")
    print(f"[INFO] Gate: arista>={GATE_EDGE_WEIGHT_MIN} | w_sin>={GATE_SINAPTICO_MIN} | grado>={GATE_DEGREE_MIN}")
    print(f"[INFO] Inject: α={INJECT_ALPHA} β={INJECT_BETA} | HC_threshold={HIGH_CONFIDENCE_PRIMARY_THRESHOLD}")

    cerebro = inicializar_motor_biorag(DB_SNAPSHOT_PATH)
    con = sqlite3.connect(f"file:{DB_SNAPSHOT_PATH}?mode=ro", uri=True)

    sweep_results = []

    for gamma in PREDEFINED_GAMMAS:
        print(f"\n{'─' * 60}")
        print(f"  γ = {gamma}")
        print(f"{'─' * 60}")

        dev_res = evaluar_dataset(cerebro, con, DEV_CASES, gamma)
        neg_res = evaluar_negativos(cerebro, con, gamma)

        print(
            f"  Q0: R@1={dev_res['q0_summary']['r1']:5.1f}%  "
            f"R@5={dev_res['q0_summary']['r5']:5.1f}%  "
            f"MRR={dev_res['q0_summary']['mrr']:.4f}"
        )
        print(
            f"  Q1: R@1={dev_res['q1_summary']['r1']:5.1f}%  "
            f"R@5={dev_res['q1_summary']['r5']:5.1f}%  "
            f"MRR={dev_res['q1_summary']['mrr']:.4f}  "
            f"(ΔQ0→Q1={dev_res['delta_q0_to_q1']['delta_r5_pp']:+.2f}pp)"
        )
        print(
            f"  Q2: R@1={dev_res['q2_summary']['r1']:5.1f}%  "
            f"R@5={dev_res['q2_summary']['r5']:5.1f}%  "
            f"MRR={dev_res['q2_summary']['mrr']:.4f}  "
            f"(ΔQ1→Q2={dev_res['delta_q1_to_q2']['delta_r5_pp']:+.2f}pp)"
        )
        print(
            f"  Q3: R@1={dev_res['q3_summary']['r1']:5.1f}%  "
            f"R@5={dev_res['q3_summary']['r5']:5.1f}%  "
            f"MRR={dev_res['q3_summary']['mrr']:.4f}"
        )
        print(f"  FP Grafo: {neg_res['fp_graph_count']}/{neg_res['total_negativos']}")

        for c in dev_res["casos"]:
            r0 = str(c["q0"]["rank"]) if c["q0"]["rank"] else "❌"
            r1 = str(c["q1"]["rank"]) if c["q1"]["rank"] else "❌"
            r2 = str(c["q2"]["rank"]) if c["q2"]["rank"] else "❌"
            dg = c["q2"]["diag"]
            gd = c["q2"].get("gold_detail")
            boost_str = f"boost={gd.get('boost_applied', 0):+.4f}" if gd else "gold_NOT_in_pool"
            pool_str = "Pool✅" if c["q2"]["gold_in_pool"] else "Pool❌"
            print(
                f"    {c['id']}  Q0:{r0:>4} Q1:{r1:>4} Q2:{r2:>4}  "
                f"Gate✓:{dg['gate_passed']} Gate✗:{dg['gate_rejected']}  "
                f"{pool_str}  {boost_str}"
            )

        sweep_results.append({
            "gamma": gamma,
            "dev_evaluation": dev_res,
            "negative_evaluation": neg_res
        })

    con.close()

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    full_output = {
        "experimento": "EXP-Q-R5",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db_sha256": db_sha,
        "gammas_evaluated": PREDEFINED_GAMMAS,
        "gate_config": {
            "edge_weight_min": GATE_EDGE_WEIGHT_MIN,
            "sinaptico_min": GATE_SINAPTICO_MIN,
            "degree_min": GATE_DEGREE_MIN
        },
        "inject_config": {"alpha": INJECT_ALPHA, "beta": INJECT_BETA},
        "margin_protection": MARGIN_PROTECTION_DELTA,
        "high_confidence_threshold": HIGH_CONFIDENCE_PRIMARY_THRESHOLD,
        "sweep_results": sweep_results
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] JSON: {OUTPUT_JSON}")

    generar_reporte_md(full_output, OUTPUT_REPORT)
    print(f"[OK] Reporte: {OUTPUT_REPORT}")

    best_run = max(sweep_results, key=lambda x: (
        x["dev_evaluation"]["q2_summary"]["r5"],
        x["dev_evaluation"]["q2_summary"]["mrr"]
    ))
    bd = best_run["dev_evaluation"]
    print("\n" + "=" * 80)
    print(f"  MEJOR γ = {best_run['gamma']}")
    print(
        f"  Q2: R@1={bd['q2_summary']['r1']:.1f}%  "
        f"R@5={bd['q2_summary']['r5']:.1f}%  "
        f"MRR={bd['q2_summary']['mrr']:.4f}"
    )
    print(
        f"  ΔR@5 (Q1→Q2) = {bd['delta_q1_to_q2']['delta_r5_pp']:+.2f} pp  |  "
        f"FP Grafo: {best_run['negative_evaluation']['fp_graph_count']}/10"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
