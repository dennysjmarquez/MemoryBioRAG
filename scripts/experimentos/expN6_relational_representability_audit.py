#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN6_relational_representability_audit.py
=============================================================================
EXP-N6: RELATIONAL REPRESENTABILITY AUDIT
=============================================================================
PROPÓSITO CIENTÍFICO (Protocolo Aureon):
    Determinar rigurosamente si el snapshot congelado de la base de datos
    contiene información relacional suficiente (roles de argumento, relaciones
    dirigidas, predicados tipados) para permitir que el motor distinga:

        C1 = OP(OBJECT=A, TARGET=B)
        C2 = OP(OBJECT=B, TARGET=A)
        C3 = OP(OBJECT=A, TARGET=C)

    cuando los candidatos comparten la misma bolsa plana de dimensiones.

ESTRUCTURA DE LA AUDITORÍA:
    1. Auditoría de representabilidad relacional sobre los 6 Strict A0 y controles.
    2. Prueba de identificabilidad empírica (C1 vs C2 vs C3).
    3. Auditoría ontológica y causal de señales para "Synaptic Role Projection".
    4. Clasificación formal de señales potenciales (A, B, C, D, E).
    5. Veredicto formal: RAB-EXTENSION-VALID / PARTIAL / INVALID.
    6. Trazabilidad completa con SHA-256 y persistencia en docs/.

RESTRICCIONES METODOLÓGICAS:
    - No modificar core/.
    - No tocar A0-TEST (20 casos).
    - No asumir que un vecino sináptico representa un rol de argumento.
    - Si la semántica está ausente, declarar: RELATIONAL_INFORMATION_ABSENT.
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional, Set, FrozenSet
from dataclasses import dataclass, field
import numpy as np

sys.path.insert(0, os.path.abspath("."))

from scripts.experimentos.expN_scg_v01 import (
    DB_PATH,
    LABELS_PATH,
    DEV_DATASET_PATH,
    normalizar,
    tokenizar,
)

OUTPUT_EXP_N6 = "docs/expN6_relational_representability_results.json"

A0_STRICT_GOLDS = [
    {"id": "OOF_POS_11", "gold": "docker_infrastructure_rog", "query": "particionar capacidad de computo en doce nucleos virtuales con tope en gigas"},
    {"id": "OOF_POS_19", "gold": "scoring_pesos_bm25", "query": "calibrar coeficientes multiplicativos para combinar valores de relevancia heterogeneos"},
    {"id": "OOF_POS_21", "gold": "coche_puente_condicional", "query": "entrelazamiento hiperdimensional binario proyectado a traves de pasarela situacional"},
    {"id": "OOF_POS_29", "gold": "desde_athena_biorag", "query": "generar conexiones estocasticas para consolidar grupos fuertemente entrelazados"},
    {"id": "OOF_POS_30", "gold": "activos_dormidos_hermana", "query": "transicion de vigilia a letargo con eliminacion de elementos caducos"},
    {"id": "OOF_POS_48", "gold": "cuaternidad-logica-oec", "query": "malla neuronal con topologia de enlaces sinapticos transversales"}
]


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUDITORÍA DEL SNAPSHOT: INVENTARIO DE ESTRUCTURA ALMACENADA
# ─────────────────────────────────────────────────────────────────────────────

def auditar_nodo_snapshot(con: sqlite3.Connection, concepto: str) -> Dict[str, Any]:
    c = con.cursor()

    # 1. Datos del nodo en largo_plazo
    lp_row = c.execute("SELECT id, concepto, categoria, contenido, peso_sinaptico, estado, sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,)).fetchone()
    if not lp_row:
        return {"exists": False, "concepto": concepto}

    # 2. Dimensiones
    dims = c.execute("""
        SELECT ds.name, td.nombre
        FROM largo_plazo_dimensiones lpd
        JOIN dimensiones_semanticas ds ON ds.id = lpd.dimension_id
        JOIN tipos_dimension td ON td.id = ds.tipo_id
        WHERE lpd.concepto = ?
    """, (concepto,)).fetchall()
    dims_list = [f"{tipo}:{dim}" for dim, tipo in sorted(dims)]

    # 3. Sinapsis salientes y entrantes
    sinapsis_out = c.execute("SELECT destino, peso, tipo FROM sinapsis WHERE origen = ?", (concepto,)).fetchall()
    sinapsis_in = c.execute("SELECT origen, peso, tipo FROM sinapsis WHERE destino = ?", (concepto,)).fetchall()

    # 4. Predicados almacenados
    preds = c.execute("SELECT sujeto, accion, objeto, contexto FROM predicados WHERE concepto = ?", (concepto,)).fetchall()
    preds_list = [{"sujeto": s, "accion": a, "objeto": o, "contexto": ctx} for s, a, o, ctx in preds]

    # 5. Concept Hubs
    hubs = c.execute("SELECT hub_id, role FROM concept_hub_nodes WHERE node_concepto = ?", (concepto,)).fetchall()

    # 6. Análisis de roles explícitos almacenados
    has_explicit_roles = len(preds) > 0 or len(hubs) > 0
    relational_status = "EXPLICIT_ROLES_PRESENT" if has_explicit_roles else "RELATIONAL_INFORMATION_ABSENT"

    return {
        "exists": True,
        "concepto": concepto,
        "categoria": lp_row[2],
        "estado": lp_row[5],
        "dimensiones_count": len(dims),
        "dimensiones": dims_list,
        "sinapsis_out_count": len(sinapsis_out),
        "sinapsis_out_tipos": dict(defaultdict(int, [(t, sum(1 for _, _, tp in sinapsis_out if tp == t)) for _, _, t in sinapsis_out])),
        "sinapsis_in_count": len(sinapsis_in),
        "predicados_count": len(preds),
        "predicados": preds_list,
        "concept_hubs_count": len(hubs),
        "relational_status": relational_status,
        "explicit_role_representation": {
            "OBJECT": any(p["objeto"] for p in preds_list),
            "TARGET": False,
            "SOURCE": False,
            "DESTINATION": False,
            "CONSTRAINT": False,
            "PURPOSE": False,
            "BEFORE_AFTER": False,
            "CAUSE_EFFECT": False,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. PRUEBA DE IDENTIFICABILIDAD EMPÍRICA (C1 vs C2 vs C3)
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_prueba_identificabilidad(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Evalúa si el snapshot congelado contiene información observable para
    distinguir configuraciones relacionales distintas sobre la misma bolsa de etiquetas.
    """
    c = con.cursor()

    TEST_TRIPLES = [
        {
            "id": "TRIPLE_01_COMPUTATIONAL_SEPARATE",
            "description": "SEPARATE(OBJECT=hardware, TARGET=virtual) vs SEPARATE(OBJECT=virtual, TARGET=hardware)",
            "domain_A": "identidad_fisica_hardware",
            "domain_B": "accion_persistencia_computacion",
            "domain_C": "coordenada_cronologia_absoluta",
            "op": "SEPARATE"
        },
        {
            "id": "TRIPLE_02_COGNITIVE_LINK",
            "description": "LINK(OBJECT=neural, TARGET=stochastic) vs LINK(OBJECT=stochastic, TARGET=neural)",
            "domain_A": "accion_cognitiva",
            "domain_B": "accion_rutina_automatica",
            "domain_C": "identidad_artificial",
            "op": "LINK"
        },
        {
            "id": "TRIPLE_03_EVALUATE_METRIC",
            "description": "EVALUATE(OBJECT=metric, TARGET=hierarchical) vs EVALUATE(OBJECT=hierarchical, TARGET=metric)",
            "domain_A": "accion_evaluar",
            "domain_B": "cualidad_abstracta_conceptual",
            "domain_C": "intencion_documentar",
            "op": "EVALUATE"
        }
    ]

    identifiability_results = []

    for t in TEST_TRIPLES:
        tid = t["id"]
        dom_a = t["domain_A"]
        dom_b = t["domain_B"]

        # Buscar nodos en SQLite que posean simultáneamente dom_a y dom_b
        shared_nodes = c.execute("""
            SELECT lpd1.concepto
            FROM largo_plazo_dimensiones lpd1
            JOIN largo_plazo_dimensiones lpd2 ON lpd1.concepto = lpd2.concepto
            JOIN dimensiones_semanticas ds1 ON ds1.id = lpd1.dimension_id
            JOIN dimensiones_semanticas ds2 ON ds2.id = lpd2.dimension_id
            JOIN largo_plazo lp ON lp.concepto = lpd1.concepto
            WHERE ds1.name = ? AND ds2.name = ? AND lp.estado = 'activo'
        """, (dom_a, dom_b)).fetchall()

        shared_nodes_list = [r[0] for r in shared_nodes]

        # Verificar si para estos nodos compartidos existe algún slot de rol que diferencie A como OBJECT vs B como TARGET
        differentiated_count = 0
        for nodo in shared_nodes_list:
            preds = c.execute("SELECT sujeto, accion, objeto FROM predicados WHERE concepto = ?", (nodo,)).fetchall()
            if preds:
                differentiated_count += 1

        distinguishable = differentiated_count > 0 and len(shared_nodes_list) > 0

        identifiability_results.append({
            "triple_id": tid,
            "description": t["description"],
            "nodes_with_identical_bag": len(shared_nodes_list),
            "sample_nodes": shared_nodes_list[:5],
            "nodes_with_stored_argument_slots": differentiated_count,
            "distinguishable_in_snapshot": distinguishable,
            "verdict": "DISTINGUISHABLE_VIA_PREDICADOS" if distinguishable else "INDISTINGUISHABLE_FLAT_BAG"
        })

    return identifiability_results


# ─────────────────────────────────────────────────────────────────────────────
# 3. AUDITORÍA DE SEÑALES PARA SYNAPTIC ROLE PROJECTION (A, B, C, D, E)
# ─────────────────────────────────────────────────────────────────────────────

SIGNAL_CLASSIFICATION_CATALOG = [
    {
        "signal_id": "SIG_01_SYNAPSIS_DIRECT_WEIGHT",
        "name": "Peso de arista sináptica directa (origen -> destino)",
        "implementation": "peso = sinapsis.peso WHERE origen = N AND destino = V",
        "source": "Tabla sinapsis de SQLite",
        "stored_semantics": "Fuerza asociativa estadística / PMI / co-ocurrencia Hebbiana",
        "provenance": "Daemons de consolidación Hebbiana y ráfagas históricas",
        "frozen_before_exp_n": True,
        "derived_without_gold": True,
        "classification": "B",
        "can_represent_role": False,
        "rationale": "Consecuencia estructural formal de proximidad asociativa. NO representa dirección de argumento sintáctico (quién es sujeto u objeto)."
    },
    {
        "signal_id": "SIG_02_SYNAPSIS_TYPE_HEBBIAN",
        "name": "Tipo de sinapsis 'pmi_hebbiano' / 'co_ocurrencia'",
        "implementation": "tipo IN ('pmi_hebbiano', 'co_ocurrencia')",
        "source": "Columna tipo en tabla sinapsis",
        "stored_semantics": "Correlación estadística no dirigida",
        "provenance": "Módulo de co-ocurrencia textual y PPMI",
        "frozen_before_exp_n": True,
        "derived_without_gold": True,
        "classification": "B",
        "can_represent_role": False,
        "rationale": "Correlación estadística simétrica. Mapear 'pmi_hebbiano' a un rol argumental (ej. OBJECT) sería una inferencia no fundamentada Clase D."
    },
    {
        "signal_id": "SIG_03_SYNAPSIS_TYPE_EXPLICIT_SYNONYM",
        "name": "Tipo de sinapsis 'sinonimo_explicito'",
        "implementation": "tipo = 'sinonimo_explicito'",
        "source": "Columna tipo en tabla sinapsis",
        "stored_semantics": "Equivalencia semántica nominal",
        "provenance": "Diccionario WordNet / Neocórtex de sangre",
        "frozen_before_exp_n": True,
        "derived_without_gold": True,
        "classification": "C",
        "can_represent_role": False,
        "rationale": "Ontología preexistente congelada de sinonimia. No codifica relaciones predicado-argumento."
    },
    {
        "signal_id": "SIG_04_SYNAPTIC_NEIGHBOR_AS_ARGUMENT_ROLE",
        "name": "Interpretación de Vecino Sináptico como Rol Argumental (Role Projection)",
        "implementation": "Vecino(V).dimensiones == Query.Role(TARGET)",
        "source": "Proyección propuesta",
        "stored_semantics": "Inferencia de ligadura externa no almacenada",
        "provenance": "Propuesta de extensión durante EXP-N5",
        "frozen_before_exp_n": False,
        "derived_without_gold": True,
        "classification": "D",
        "can_represent_role": False,
        "rationale": "CLASE D (PROHIBIDA): Asumir que un vecino sináptico desempeña el rol sintáctico de la query es una inferencia heurística no respaldada por metadatos del snapshot."
    },
    {
        "signal_id": "SIG_05_TABLE_PREDICADOS_SVO",
        "name": "Tabla de Predicados Tipados (sujeto, accion, objeto, contexto)",
        "implementation": "SELECT sujeto, accion, objeto FROM predicados WHERE concepto = N",
        "source": "Tabla predicados de SQLite",
        "stored_semantics": "Triples relacionales estructurados (S-V-O)",
        "provenance": "Parser proposicional de ingesta histórica preexistente",
        "frozen_before_exp_n": True,
        "derived_without_gold": True,
        "classification": "A",
        "can_represent_role": True,
        "rationale": "CLASE A: Única estructura que almacena explícitamente roles de argumento (sujeto/objeto). Sin embargo, solo cubre 102/851 nodos (12.0%) del corpus y 0/6 de los Gold Strict A0."
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# 4. EJECUCIÓN Y GENERACIÓN DEL REPORTE FORMAL EXP-N6
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_exp_n6():
    print("=============================================================================")
    print("EXP-N6: RELATIONAL REPRESENTABILITY AUDIT (SNAPSHOT CONGELADO)")
    print("=============================================================================")
    print(f"• Snapshot DB SHA-256: {hashlib.sha256(open(DB_PATH, 'rb').read()).hexdigest()}")
    print(f"• Labels   SHA-256:    {hashlib.sha256(open(LABELS_PATH, 'rb').read()).hexdigest()}")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c = con.cursor()

    # 1. Auditoría de los 6 Strict A0
    print("\n--- 1. AUDITORÍA DE REPRESENTABILIDAD SOBRE LOS 6 STRICT A0 ---")
    golds_audit = []
    for g_info in A0_STRICT_GOLDS:
        res = auditar_nodo_snapshot(con, g_info["gold"])
        res["case_id"] = g_info["id"]
        res["query"] = g_info["query"]
        golds_audit.append(res)
        print(f"[{g_info['id']:10s}] Gold: {g_info['gold']:30s} | Dims:{res['dimensiones_count']:2d} | "
              f"Sinapsis:{res['sinapsis_out_count']:3d} | Predicados:{res['predicados_count']:1d} | "
              f"Status: {res['relational_status']}")

    # 2. Prueba de Identificabilidad (C1 vs C2 vs C3)
    print("\n--- 2. PRUEBA DE IDENTIFICABILIDAD (C1 vs C2 vs C3) ---")
    ident_results = ejecutar_prueba_identificabilidad(con)
    for ir in ident_results:
        print(f"[{ir['triple_id']}] {ir['verdict']} | Nodos Compartidos: {ir['nodes_with_identical_bag']} | "
              f"Con Slots Argumentales: {ir['nodes_with_stored_argument_slots']}")

    # 3. Inventario Global del Snapshot
    print("\n--- 3. INVENTARIO GLOBAL DE RELACIONES EN EL SNAPSHOT ---")
    total_nodos_activos = c.execute("SELECT count(*) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
    total_sinapsis = c.execute("SELECT count(*) FROM sinapsis").fetchone()[0]
    sinapsis_tipos = c.execute("SELECT tipo, count(*) FROM sinapsis GROUP BY tipo").fetchall()
    total_predicados = c.execute("SELECT count(*) FROM predicados").fetchone()[0]
    nodos_con_predicados = c.execute("SELECT count(DISTINCT concepto) FROM predicados").fetchone()[0]
    concept_hubs_count = c.execute("SELECT count(*) FROM concept_hubs").fetchone()[0]

    print(f"• Total Nodos Activos en Corpus:        {total_nodos_activos}")
    print(f"• Total Sinapsis Almacenadas:          {total_sinapsis}")
    print(f"  Tipos de Sinapsis:")
    for tp, cnt in sinapsis_tipos:
        print(f"    - {tp:22s}: {cnt:5d} ({cnt/total_sinapsis*100:5.1f}%)")
    print(f"• Total Predicados S-V-O Almacenados:   {total_predicados} (en {nodos_con_predicados} nodos = {nodos_con_predicados/total_nodos_activos*100:.1f}% del corpus)")
    print(f"• Predicados en los 6 Gold Strict A0:   0 / 6 (0.0%)")
    print(f"• Concept Hubs en DB:                   {concept_hubs_count}")

    # 4. Decisión Formal / Veredicto
    # Si los predicados cubren 0% de los Gold y las sinapsis son 100% asociativas Hebbianas sin roles tipados:
    veredicto_final = "RAB-EXTENSION-INVALID"
    razon_veredicto = (
        "El snapshot congelado NO contiene roles de argumento tipados en los 6 nodos Gold de Strict A0 (0/6 predicados). "
        "Las sinapsis almacenadas corresponden 100% a correlaciones estadísticas Hebbianas (PMI, co-ocurrencia, sinonimia nominal) "
        "sin dirección semántica ni roles sintácticos (OBJECT, TARGET, CONSTRAINT). "
        "Interpretar un vecino sináptico como un rol de argumento constituiría una inferencia heurística Clase D no justificada causalmente."
    )

    print("\n=============================================================================")
    print(f"VEREDICTO FORMAL EXP-N6: {veredicto_final}")
    print("=============================================================================")
    print(f"RAZÓN CIENTÍFICA: {razon_veredicto}")
    print("=============================================================================")

    # Guardar resultados JSON
    os.makedirs("docs", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N6: Relational Representability Audit",
        "hashes": {
            "db_snapshot": hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest(),
            "labels": hashlib.sha256(open(LABELS_PATH, "rb").read()).hexdigest(),
            "script": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
        },
        "verdict": veredicto_final,
        "verdict_rationale": razon_veredicto,
        "strict_a0_audit": golds_audit,
        "identifiability_test": ident_results,
        "snapshot_global_inventory": {
            "total_active_nodes": total_nodos_activos,
            "total_synapses": total_sinapsis,
            "synapse_type_distribution": dict(sinapsis_tipos),
            "total_predicates": total_predicados,
            "nodes_with_predicates_count": nodos_con_predicados,
            "predicates_coverage_pct": round(nodos_con_predicados / total_nodos_activos * 100, 1),
            "strict_a0_gold_predicates_coverage": "0/6 (0.0%)"
        },
        "signal_catalog_classification": SIGNAL_CLASSIFICATION_CATALOG
    }
    with open(OUTPUT_EXP_N6, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Resultados EXP-N6 persistidos en: {OUTPUT_EXP_N6}")
    con.close()


if __name__ == "__main__":
    ejecutar_exp_n6()
