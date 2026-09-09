#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN2_synthetic_heldout_composition.py
=============================================================================
EXP-N2: BENCHMARK SINTÉTICO DE COMPOSICIÓN RETENIDA (HELD-OUT COMPOSITION)
=============================================================================
PROPÓSITO CIENTÍFICO (Protocolo Aureon):
    Demostrar que el generador estructural es capaz de:
    1. Reconocer primitivas atómicas de manera invariante.
    2. Componer primitivas conocidas en estructuras válidas.
    3. Construir representaciones composicionales sobre COMBINACIONES RETENIDAS
       (Held-out compositions) que NUNCA fueron observadas durante el diseño.
    4. Manejar composiciones complejas abiertas nunca vistas.
    5. Rechazar de forma dura e inequívoca las NEGATIVAS ESTRUCTURALES
       (contradicciones, incompatibilidades de polaridad y anomalías lógicas).

CATEGORÍAS DEL BENCHMARK SINTÉTICO:
    CAT-1: Primitivas Atómicas (10 casos)
    CAT-2: Composiciones Canónicas Conocidas (8 casos)
    CAT-3: Composiciones Retenidas No Observadas (Held-out, 10 casos)
    CAT-4: Composiciones Abiertas Multiclausal (8 casos)
    CAT-5: Negativas Estructurales Duras / Contradicciones (8 casos)
    TOTAL: 44 casos sintéticos congelados con ground truth estructural.

MÉTRICAS FORMALES:
    - Atomic Primitive Accuracy (APA)
    - Held-out Compositional Generalization Accuracy (CGA)
    - Structural Negative Rejection Rate (NRR) [Meta: 100%]
    - Global Synthetic Score (GSS)
=============================================================================
"""

import os
import sys
import json
import hashlib
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional, Set, FrozenSet
from dataclasses import dataclass, field
import numpy as np

sys.path.insert(0, os.path.abspath("."))

from scripts.experimentos.expN_scg_v01 import (
    StructuralForm,
    ComposedHypothesis,
    parsear_query,
    generar_hipotesis,
    normalizar,
    tokenizar,
)

OUTPUT_BENCHMARK_RESULTS = "docs/expN2_synthetic_heldout_results.json"

# =============================================================================
# DEFINICIÓN DEL DATASET SINTÉTICO CONGELADO (44 CASOS)
# =============================================================================

SYNTHETIC_BENCHMARK = [
    # ── CAT-1: PRIMITIVAS ATÓMICAS (10 casos) ────────────────────────────────
    {
        "id": "ATOM_01",
        "category": "ATOMIC",
        "query": "generar nueva memoria en el sistema",
        "expected_ops": {"CREATE"},
        "expected_rels": set(),
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: CREATE puro"
    },
    {
        "id": "ATOM_02",
        "category": "ATOMIC",
        "query": "modificar los parámetros internos",
        "expected_ops": {"MODIFY"},
        "expected_rels": set(),
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: MODIFY puro"
    },
    {
        "id": "ATOM_03",
        "category": "ATOMIC",
        "query": "eliminar registros obsoletos",
        "expected_ops": {"REMOVE"},
        "expected_rels": set(),
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: REMOVE puro"
    },
    {
        "id": "ATOM_04",
        "category": "ATOMIC",
        "query": "evaluar el rendimiento computacional",
        "expected_ops": {"EVALUATE"},
        "expected_rels": set(),
        "expected_props": {"COMPUTATIONAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: EVALUATE + COMPUTATIONAL"
    },
    {
        "id": "ATOM_05",
        "category": "ATOMIC",
        "query": "fusionar los vectores de representación",
        "expected_ops": {"COMBINE"},
        "expected_rels": set(),
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: COMBINE puro"
    },
    {
        "id": "ATOM_06",
        "category": "ATOMIC",
        "query": "particionar el espacio de memoria",
        "expected_ops": {"SEPARATE"},
        "expected_rels": set(),
        "expected_props": {"COMPUTATIONAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: SEPARATE + COMPUTATIONAL"
    },
    {
        "id": "ATOM_07",
        "category": "ATOMIC",
        "query": "enlazar nodos vecinos en la red",
        "expected_ops": {"LINK"},
        "expected_rels": set(),
        "expected_props": {"CONNECTIVE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: LINK + CONNECTIVE"
    },
    {
        "id": "ATOM_08",
        "category": "ATOMIC",
        "query": "persistir los cambios en disco",
        "expected_ops": {"PERSIST"},
        "expected_rels": set(),
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: PERSIST puro"
    },
    {
        "id": "ATOM_09",
        "category": "ATOMIC",
        "query": "extraer las memorias relevantes",
        "expected_ops": {"RETRIEVE"},
        "expected_rels": set(),
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: RETRIEVE puro"
    },
    {
        "id": "ATOM_10",
        "category": "ATOMIC",
        "query": "clasificar según la taxonomía dimensional",
        "expected_ops": {"CLASSIFY"},
        "expected_rels": set(),
        "expected_props": {"DIMENSIONAL", "HIERARCHICAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "Atómica: CLASSIFY + DIMENSIONAL + HIERARCHICAL"
    },

    # ── CAT-2: COMPOSICIONES CONOCIDAS (8 casos) ─────────────────────────────
    {
        "id": "KNOWN_01",
        "category": "KNOWN_COMPOSITION",
        "query": "evaluar antes de modificar los pesos",
        "expected_ops": {"EVALUATE", "MODIFY"},
        "expected_rels": {"BEFORE"},
        "expected_props": {"METRIC"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "EVALUATE ⊕ BEFORE ⊕ MODIFY ⊕ METRIC"
    },
    {
        "id": "KNOWN_02",
        "category": "KNOWN_COMPOSITION",
        "query": "transformar señales para persistir en largo plazo",
        "expected_ops": {"TRANSFORM", "PERSIST"},
        "expected_rels": {"PURPOSE_OF"},
        "expected_props": set(),
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "TRANSFORM ⊕ PURPOSE_OF ⊕ PERSIST"
    },
    {
        "id": "KNOWN_03",
        "category": "KNOWN_COMPOSITION",
        "query": "clasificar jerárquicamente y vincular con conceptos activos",
        "expected_ops": {"CLASSIFY", "LINK"},
        "expected_rels": set(),
        "expected_props": {"HIERARCHICAL", "LIFECYCLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "CLASSIFY ⊕ LINK ⊕ HIERARCHICAL"
    },
    {
        "id": "KNOWN_04",
        "category": "KNOWN_COMPOSITION",
        "query": "desactivar rutinas temporales durante el ciclo de letargo",
        "expected_ops": {"DEACTIVATE"},
        "expected_rels": set(),
        "expected_props": {"TEMPORAL", "LIFECYCLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "DEACTIVATE ⊕ TEMPORAL ⊕ LIFECYCLE"
    },
    {
        "id": "KNOWN_05",
        "category": "KNOWN_COMPOSITION",
        "query": "combinar estimaciones estocásticas para calcular la varianza",
        "expected_ops": {"COMBINE", "EVALUATE"},
        "expected_rels": {"PURPOSE_OF"},
        "expected_props": {"STOCHASTIC"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "COMBINE ⊕ EVALUATE ⊕ STOCHASTIC"
    },
    {
        "id": "KNOWN_06",
        "category": "KNOWN_COMPOSITION",
        "query": "separar clusters antes de generar nuevos enlaces",
        "expected_ops": {"SEPARATE", "CREATE", "LINK"},
        "expected_rels": {"BEFORE"},
        "expected_props": {"CONNECTIVE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "SEPARATE ⊕ BEFORE ⊕ (CREATE ⊕ LINK)"
    },
    {
        "id": "KNOWN_07",
        "category": "KNOWN_COMPOSITION",
        "query": "registrar eventos en la bitácora cronológica después de evaluar",
        "expected_ops": {"STORE", "EVALUATE"},
        "expected_rels": {"AFTER"},
        "expected_props": {"CHRONICLE", "TEMPORAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "STORE ⊕ AFTER ⊕ EVALUATE ⊕ CHRONICLE"
    },
    {
        "id": "KNOWN_08",
        "category": "KNOWN_COMPOSITION",
        "query": "activar mecanismos neurales que causan plasticidad sináptica",
        "expected_ops": {"ACTIVATE"},
        "expected_rels": {"CAUSES"},
        "expected_props": {"COGNITIVE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "ACTIVATE ⊕ CAUSES ⊕ COGNITIVE"
    },

    # ── CAT-3: COMPOSICIONES RETENIDAS NO VISTAS (HELD-OUT) (10 casos) ────────
    # Combinaciones ortogonales de primitivas que nunca fueron usadas en tests ni en DEV
    {
        "id": "HELDOUT_01",
        "category": "HELDOUT_COMPOSITION",
        "query": "particionar hardware estocástico después de registrar el hito cronológico",
        "expected_ops": {"SEPARATE", "STORE"},
        "expected_rels": {"AFTER"},
        "expected_props": {"COMPUTATIONAL", "STOCHASTIC", "CHRONICLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "SEPARATE(COMPUTATIONAL ∧ STOCHASTIC) AFTER STORE(CHRONICLE)"
    },
    {
        "id": "HELDOUT_02",
        "category": "HELDOUT_COMPOSITION",
        "query": "desactivar la jerarquía dimensional antes de fusionar matrices",
        "expected_ops": {"DEACTIVATE", "COMBINE"},
        "expected_rels": {"BEFORE"},
        "expected_props": {"HIERARCHICAL", "DIMENSIONAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "DEACTIVATE(HIERARCHICAL ∧ DIMENSIONAL) BEFORE COMBINE"
    },
    {
        "id": "HELDOUT_03",
        "category": "HELDOUT_COMPOSITION",
        "query": "eliminar enlaces estocásticos para prevenir interferencia sináptica",
        "expected_ops": {"REMOVE"},
        "expected_rels": {"BLOCKS", "PURPOSE_OF"},
        "expected_props": {"CONNECTIVE", "STOCHASTIC", "COGNITIVE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "REMOVE(CONNECTIVE ∧ STOCHASTIC) BLOCKS COGNITIVE"
    },
    {
        "id": "HELDOUT_04",
        "category": "HELDOUT_COMPOSITION",
        "query": "proyectar la bitácora temporal hacia unidades de cómputo virtual",
        "expected_ops": {"TRANSFORM"},
        "expected_rels": set(),
        "expected_props": {"CHRONICLE", "TEMPORAL", "COMPUTATIONAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "TRANSFORM(CHRONICLE ∧ TEMPORAL ∧ COMPUTATIONAL)"
    },
    {
        "id": "HELDOUT_05",
        "category": "HELDOUT_COMPOSITION",
        "query": "clasificar ponderaciones métricas junto con la activación de letargo",
        "expected_ops": {"CLASSIFY", "ACTIVATE"},
        "expected_rels": {"COORDINATES_WITH"},
        "expected_props": {"METRIC", "LIFECYCLE", "TEMPORAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "CLASSIFY(METRIC) COORDINATES_WITH ACTIVATE(LIFECYCLE)"
    },
    {
        "id": "HELDOUT_06",
        "category": "HELDOUT_COMPOSITION",
        "query": "recuperar esquemas jerárquicos que requieren calibración previa",
        "expected_ops": {"RETRIEVE", "MODIFY"},
        "expected_rels": {"REQUIRES", "BEFORE"},
        "expected_props": {"HIERARCHICAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "RETRIEVE(HIERARCHICAL) REQUIRES (MODIFY BEFORE)"
    },
    {
        "id": "HELDOUT_07",
        "category": "HELDOUT_COMPOSITION",
        "query": "construir topología cortical estocástica para persistir pesos",
        "expected_ops": {"CREATE", "PERSIST"},
        "expected_rels": {"PURPOSE_OF"},
        "expected_props": {"COGNITIVE", "CONNECTIVE", "STOCHASTIC", "METRIC"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "CREATE(COGNITIVE ∧ CONNECTIVE ∧ STOCHASTIC) PURPOSE_OF PERSIST(METRIC)"
    },
    {
        "id": "HELDOUT_08",
        "category": "HELDOUT_COMPOSITION",
        "query": "medir la degradación de recursos antes de purgar registros caducos",
        "expected_ops": {"EVALUATE", "REMOVE"},
        "expected_rels": {"BEFORE"},
        "expected_props": {"COMPUTATIONAL", "LIFECYCLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "EVALUATE(COMPUTATIONAL) BEFORE REMOVE(LIFECYCLE)"
    },
    {
        "id": "HELDOUT_09",
        "category": "HELDOUT_COMPOSITION",
        "query": "entrelazar memorias dimensionales con procesos computacionales",
        "expected_ops": {"LINK"},
        "expected_rels": set(),
        "expected_props": {"DIMENSIONAL", "COMPUTATIONAL", "CONNECTIVE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "LINK(DIMENSIONAL ∧ COMPUTATIONAL ∧ CONNECTIVE)"
    },
    {
        "id": "HELDOUT_10",
        "category": "HELDOUT_COMPOSITION",
        "query": "sintetizar múltiples hitos históricos en una sola representación cronológica",
        "expected_ops": {"CREATE", "COMBINE"},
        "expected_rels": set(),
        "expected_props": {"CHRONICLE", "TEMPORAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "CREATE ⊕ COMBINE ⊕ CHRONICLE ⊕ TEMPORAL"
    },

    # ── CAT-4: COMPOSICIONES ABIERTAS MULTICLAUSALES (8 casos) ───────────────
    {
        "id": "OPEN_01",
        "category": "OPEN_COMPOSITION",
        "query": "proceso que exige evaluar y calibrar la red sináptica antes de consolidar el cambio",
        "expected_ops": {"EVALUATE", "MODIFY", "PERSIST"},
        "expected_rels": {"REQUIRES", "BEFORE"},
        "expected_props": {"COGNITIVE", "CONNECTIVE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "REQUIRES (EVALUATE ∧ MODIFY) BEFORE PERSIST"
    },
    {
        "id": "OPEN_02",
        "category": "OPEN_COMPOSITION",
        "query": "organizar la taxonomía jerárquica para permitir que el módulo recupere hitos históricos",
        "expected_ops": {"CLASSIFY", "RETRIEVE"},
        "expected_rels": {"ENABLES", "PURPOSE_OF"},
        "expected_props": {"HIERARCHICAL", "CHRONICLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "CLASSIFY(HIERARCHICAL) ENABLES RETRIEVE(CHRONICLE)"
    },
    {
        "id": "OPEN_03",
        "category": "OPEN_COMPOSITION",
        "query": "segmentar núcleos de procesamiento y reajustar coeficientes tras la desactivación",
        "expected_ops": {"SEPARATE", "MODIFY", "DEACTIVATE"},
        "expected_rels": {"AFTER"},
        "expected_props": {"COMPUTATIONAL", "METRIC", "LIFECYCLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "SEPARATE ⊕ MODIFY AFTER DEACTIVATE"
    },
    {
        "id": "OPEN_04",
        "category": "OPEN_COMPOSITION",
        "query": "producir un mapa dimensional que previene el desbordamiento de memoria computacional",
        "expected_ops": {"CREATE", "TRANSFORM"},
        "expected_rels": {"BLOCKS"},
        "expected_props": {"DIMENSIONAL", "COMPUTATIONAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "CREATE ⊕ TRANSFORM BLOCKS OVERFLOW"
    },
    {
        "id": "OPEN_05",
        "category": "OPEN_COMPOSITION",
        "query": "conectar unidades neuronales en paralelo y registrar su trayectoria cronológica",
        "expected_ops": {"LINK", "STORE"},
        "expected_rels": {"COORDINATES_WITH"},
        "expected_props": {"COGNITIVE", "CHRONICLE", "TEMPORAL"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "LINK ⊕ STORE COORDINATED"
    },
    {
        "id": "OPEN_06",
        "category": "OPEN_COMPOSITION",
        "query": "inspeccionar y depurar enlaces obsoletos para restaurar la topología del grafo",
        "expected_ops": {"EVALUATE", "REMOVE"},
        "expected_rels": {"PURPOSE_OF"},
        "expected_props": {"CONNECTIVE", "LIFECYCLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "EVALUATE ⊕ REMOVE PURPOSE_OF RESTORE TOPOLOGY"
    },
    {
        "id": "OPEN_07",
        "category": "OPEN_COMPOSITION",
        "query": "proyectar señales aleatorias sobre el espacio de estados y fijar los pesos",
        "expected_ops": {"TRANSFORM", "PERSIST"},
        "expected_rels": set(),
        "expected_props": {"STOCHASTIC", "METRIC"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "TRANSFORM(STOCHASTIC) ⊕ PERSIST(METRIC)"
    },
    {
        "id": "OPEN_08",
        "category": "OPEN_COMPOSITION",
        "query": "dividir recursos computacionales cuando se requiere suspender las tareas automáticas",
        "expected_ops": {"SEPARATE", "DEACTIVATE"},
        "expected_rels": {"REQUIRES"},
        "expected_props": {"COMPUTATIONAL", "LIFECYCLE"},
        "expected_polarity": 1,
        "should_be_valid": True,
        "description": "SEPARATE REQUIRES DEACTIVATE"
    },

    # ── CAT-5: NEGATIVAS ESTRUCTURALES DURAS / CONTRADICCIONES (8 casos) ──────
    # Deben producir polaridad negativa, flag de inconsistencia o abstención.
    {
        "id": "NEG_01",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "no se debe modificar el estado sin previa verificación",
        "expected_polarity": -1,
        "expected_ops": {"MODIFY", "EVALUATE"},
        "expected_rels": {"BEFORE", "REQUIRES"},
        "should_be_valid": True,  # Válido como negación/prohibición deóntica
        "description": "Prohibición deóntica (POLARITY=-1)"
    },
    {
        "id": "NEG_02",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "evitar la eliminación de memorias durante la vigilia",
        "expected_polarity": -1,
        "expected_ops": {"REMOVE"},
        "expected_props": {"TEMPORAL", "LIFECYCLE"},
        "should_be_valid": True,  # Válido como evitación de acción
        "description": "Evitación explícita (POLARITY=-1)"
    },
    {
        "id": "NEG_03",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "prohibir la persistencia de datos estocásticos no validados",
        "expected_polarity": -1,
        "expected_ops": {"PERSIST"},
        "expected_props": {"STOCHASTIC"},
        "should_be_valid": True,
        "description": "Prohibición de persistencia (POLARITY=-1)"
    },
    {
        "id": "NEG_04",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "bloquear la creación de nuevos enlaces entre módulos desconectados",
        "expected_ops": {"CREATE", "LINK"},
        "expected_rels": {"BLOCKS"},
        "expected_props": {"CONNECTIVE"},
        "expected_polarity": 1,  # BLOCKS es una relación antagonista
        "should_be_valid": True,
        "description": "Relación antagonista BLOCKS sobre CREATE⊕LINK"
    },
    {
        "id": "NEG_05",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "palabras sueltas manzana azul cielo corriendo velozmente",
        "expected_ops": set(),
        "expected_rels": set(),
        "expected_props": set(),
        "should_be_valid": False,  # Debe ABSTENERSE (0 operaciones detectadas)
        "description": "Ruido no proposicional -> ABSTENCIÓN REQUERIDA"
    },
    {
        "id": "NEG_06",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "sin registrar ni guardar información alguna",
        "expected_polarity": -1,
        "expected_ops": {"STORE"},
        "should_be_valid": True,
        "description": "Negación total de almacenamiento"
    },
    {
        "id": "NEG_07",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "objeto abstracto sin acción verbo ni función clara",
        "expected_ops": set(),
        "should_be_valid": False,  # Debe ABSTENERSE
        "description": "Query no accional -> ABSTENCIÓN REQUERIDA"
    },
    {
        "id": "NEG_08",
        "category": "STRUCTURAL_NEGATIVE",
        "query": "impedir que se activen rutinas de letargo",
        "expected_polarity": -1,
        "expected_ops": {"ACTIVATE"},
        "expected_props": {"LIFECYCLE", "TEMPORAL"},
        "should_be_valid": True,
        "description": "Inhibición de activación"
    },
]


def evaluar_benchmark_sintetico():
    print("=============================================================================")
    print("EXP-N2: BENCHMARK SINTÉTICO DE COMPOSICIÓN RETENIDA (44 CASOS)")
    print("=============================================================================")

    results = []
    category_stats = defaultdict(lambda: {"total": 0, "pass": 0, "ops_ok": 0, "rels_ok": 0, "props_ok": 0, "pol_ok": 0})

    for cs in SYNTHETIC_BENCHMARK:
        cid = cs["id"]
        cat = cs["category"]
        q = cs["query"]

        sf = parsear_query(q)
        hs = generar_hipotesis(sf)

        category_stats[cat]["total"] += 1

        # Criterios de evaluación
        exp_ops = cs.get("expected_ops", set())
        exp_rels = cs.get("expected_rels", set())
        exp_props = cs.get("expected_props", set())
        exp_pol = cs.get("expected_polarity", 1)
        should_be_valid = cs.get("should_be_valid", True)

        ops_match = sf.operations.issuperset(exp_ops) if exp_ops else (len(sf.operations) == 0 if not should_be_valid else True)
        rels_match = sf.relations.issuperset(exp_rels) if exp_rels else True
        props_match = sf.properties.issuperset(exp_props) if exp_props else True
        pol_match = (sf.polarity == exp_pol)

        # Si el caso requería abstención
        if not should_be_valid:
            is_abstain = len(sf.operations) == 0 and len(hs) == 0
            case_passed = is_abstain
        else:
            has_hyp = len(hs) > 0
            case_passed = ops_match and rels_match and props_match and pol_match and has_hyp

        if ops_match: category_stats[cat]["ops_ok"] += 1
        if rels_match: category_stats[cat]["rels_ok"] += 1
        if props_match: category_stats[cat]["props_ok"] += 1
        if pol_match: category_stats[cat]["pol_ok"] += 1
        if case_passed: category_stats[cat]["pass"] += 1

        status_str = "✅ PASS" if case_passed else "❌ FAIL"
        print(f"[{cid:10s}] {cat:20s} {status_str} — {cs['description']}")
        if not case_passed:
            print(f"   DETALLE: Ops={sorted(sf.operations)} (exp={sorted(exp_ops)}) | "
                  f"Rels={sorted(sf.relations)} (exp={sorted(exp_rels)}) | "
                  f"Props={sorted(sf.properties)} (exp={sorted(exp_props)}) | "
                  f"Pol={sf.polarity} (exp={exp_pol}) | Hypotheses={len(hs)}")

        results.append({
            "id": cid,
            "category": cat,
            "query": q,
            "description": cs["description"],
            "passed": case_passed,
            "structural_form": sf.to_dict(),
            "n_hypotheses": len(hs),
            "hypotheses_names": [h.name for h in hs],
            "ops_match": ops_match,
            "rels_match": rels_match,
            "props_match": props_match,
            "pol_match": pol_match,
        })

    # Resumen formal
    print("\n=============================================================================")
    print("RESUMEN DE RESULTADOS POR CATEGORÍA SINTÉTICA")
    print("=============================================================================")
    total_all = len(SYNTHETIC_BENCHMARK)
    pass_all = sum(1 for r in results if r["passed"])

    summary_by_cat = {}
    for cat, st in category_stats.items():
        pct = st["pass"] / st["total"] * 100
        summary_by_cat[cat] = {
            "total": st["total"],
            "passed": st["pass"],
            "accuracy_pct": round(pct, 1),
            "ops_accuracy_pct": round(st["ops_ok"] / st["total"] * 100, 1),
            "rels_accuracy_pct": round(st["rels_ok"] / st["total"] * 100, 1),
            "props_accuracy_pct": round(st["props_ok"] / st["total"] * 100, 1),
            "polarity_accuracy_pct": round(st["pol_ok"] / st["total"] * 100, 1),
        }
        print(f"• {cat:22s}: {st['pass']:2d}/{st['total']:2d} ({pct:5.1f}%) | "
              f"Ops={st['ops_ok']}/{st['total']} Rels={st['rels_ok']}/{st['total']} "
              f"Props={st['props_ok']}/{st['total']} Pol={st['pol_ok']}/{st['total']}")

    print("─────────────────────────────────────────────────────────────────────────────")
    print(f"GLOBAL SYNTHETIC SCORE (GSS): {pass_all}/{total_all} ({pass_all/total_all*100:.1f}%)")
    print(f"• Atomic Primitive Accuracy (APA):           {summary_by_cat['ATOMIC']['accuracy_pct']}%")
    print(f"• Known Composition Accuracy:                {summary_by_cat['KNOWN_COMPOSITION']['accuracy_pct']}%")
    print(f"• Held-out Generalization Accuracy (CGA):    {summary_by_cat['HELDOUT_COMPOSITION']['accuracy_pct']}%")
    print(f"• Open Multiclause Composition Accuracy:     {summary_by_cat['OPEN_COMPOSITION']['accuracy_pct']}%")
    print(f"• Structural Negative Rejection Rate (NRR):  {summary_by_cat['STRUCTURAL_NEGATIVE']['accuracy_pct']}%")
    print("=============================================================================")

    # Guardar resultados
    os.makedirs("docs", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N2: Synthetic Held-out Composition Benchmark",
        "total_cases": total_all,
        "total_passed": pass_all,
        "global_synthetic_score_pct": round(pass_all / total_all * 100, 1),
        "summary_by_category": summary_by_cat,
        "case_details": results
    }
    with open(OUTPUT_BENCHMARK_RESULTS, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Resultados guardados en: {OUTPUT_BENCHMARK_RESULTS}")


if __name__ == "__main__":
    evaluar_benchmark_sintetico()
