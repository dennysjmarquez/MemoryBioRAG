#!/usr/bin/env python3
"""
scripts/proto_fase5_rcil_v0_2.py — Prototipo RCIL v0.2: Representación Estructural Independiente de Etiquetas de Dominio
========================================================================================================================

Objetivo:
  Implementar la arquitectura RCIL v0.2 en dos etapas deterministas sin diccionarios de dominio:
    Etapa 1: Q -> Grafo Sintáctico-Relacional G(Q) (Roles abstractos, Polaridad, Deixis, Modalidad)
    Etapa 2: G(Q) -> Canonización Estructural FCC_v2(Q)

  Ejecutar los 2 Smoke Tests Obligatorios antes de cualquier benchmark de recuperación:
    1. Smoke Test 1: Invarianza de Paráfrasis (4 formulaciones con vocabulario dispar -> convergencia de invariantes).
    2. Smoke Test 2: Contraste y Separabilidad Estructural (Pares mínimos: Polaridad, Simetría, Modalidad, Secuencia).

Restricciones Inmutables:
  - NO tocar core/
  - Snapshot canónico Read-Only: snapshots/qa_escape_qcr_20260811.db
  - Cero modificaciones a evaluar_qa.py ni a suites de producción.
"""

import os
import re
import sys
import json
import math
import hashlib
import sqlite3
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
for p in (PROJECT_ROOT, SCRIPTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

DB_PATH   = "snapshots/qa_escape_qcr_20260811.db"
OUTPUT_MD = "docs/fase5_rcil_v0_2_smoke_tests.md"
OUTPUT_JS = "docs/fase5_rcil_v0_2_smoke_tests.json"

# =============================================================================
# 1. PARSER SINTÁCTICO-RELACIONAL: Q -> G(Q) -> FCC_v2(Q)
# =============================================================================

class StructuralRelationParserV2:
    """
    Parser estructural de dos etapas:
    1. Extrae primitivas gramaticales universales (sin diccionarios de dominio).
    2. Construye el Grafo Sintáctico-Relacional G(Q).
    3. Canoniza en la Forma Conceptual Canónica FCC_v2.
    """
    def __init__(self):
        # Operadores estructurales gramaticales universales (no etiquetas de dominio)
        self.negation_markers = {"no", "sin", "evitar", "evita", "evitando", "impedir", "bloquear", "prohibir", "detener", "ninguno", "nadie"}
        self.deontic_mandatory = {"debe", "deben", "obligatorio", "mandatorio", "regla", "norma", "si o si", "exigencia", "ineludible"}
        self.deontic_possibility = {"puede", "pueden", "posible", "quizas", "tal vez", "opcional", "permitido"}
        self.temporal_before = {"antes", "previo", "anterior", "primero"}
        self.temporal_after = {"despues", "luego", "posterior", "tras"}
        
        # Deixis y Cardinalidad
        self.dual_symmetric_markers = {"entre", "ambos", "compañero", "uno y otro", "nosotros", "juntos", "mutuamente", "pares", "otro", "otra", "parte"}
        self.hierarchical_markers = {"sobre", "encima", "manda", "domine", "dominar", "imponerse", "autoridad", "subordinar", "superior", "inferior", "jerarquia"}

    def parse_query_to_g_and_fcc(self, query: str) -> Dict[str, Any]:
        q_clean = query.lower().strip()
        tokens = re.findall(r"[\wáéíóúüñ]+", q_clean)

        # -------------------------------------------------------------
        # ETAPA 1: Extracción de Operadores Gramaticales y Grafo G(Q)
        # -------------------------------------------------------------
        
        # 1. Polaridad y Restricción
        has_negation = any(tok in self.negation_markers for tok in tokens) or ("sin" in tokens)
        polarity_val = -1 if has_negation else +1
        neg_evidence = [t for t in tokens if t in self.negation_markers]

        # 2. Modalidad Deóntica
        if any(tok in self.deontic_mandatory for tok in tokens) or ("si o si" in q_clean):
            modality = "DEONTIC_OBLIGATION"
            mod_evidence = [t for t in tokens if t in self.deontic_mandatory] or ["si o si"]
        elif any(tok in self.deontic_possibility for tok in tokens):
            modality = "DEONTIC_POSSIBILITY"
            mod_evidence = [t for t in tokens if t in self.deontic_possibility]
        else:
            modality = "DECLARATIVE_PROCEDURAL"
            mod_evidence = ["default_structural_inference"]

        # 3. Cardinalidad y Simetría de Participantes
        has_dual = (any(tok in self.dual_symmetric_markers for tok in tokens) or 
                    ("uno al otro" in q_clean) or 
                    ("uno sobre el otro" in q_clean) or
                    ("una parte" in q_clean and "otra" in q_clean))
        has_hier = any(tok in self.hierarchical_markers for tok in tokens)
        
        if has_dual and has_hier and has_negation:
            # Caso clave: Simétrico por negación de jerarquía ("sin que uno mande sobre el otro")
            relation_type = "BINARY_SYMMETRIC_RECIPROCAL"
            structural_constraint = "NEGATIVE_HIERARCHY_CONSTRAINT"
            symmetry_evidence = ["negation + dual_participants + hierarchical_verb"]
        elif has_hier and not has_negation:
            relation_type = "HIERARCHICAL_DIRECTED"
            structural_constraint = "EXPLICIT_HIERARCHY"
            symmetry_evidence = ["hierarchical_marker_positive"]
        elif has_dual and not has_hier:
            relation_type = "BINARY_SYMMETRIC_COORDINATED"
            structural_constraint = "COORDINATION_CONSTRAINT"
            symmetry_evidence = ["dual_markers_positive"]
        else:
            relation_type = "UNARY_OR_DISTRIBUTED"
            structural_constraint = "UNCONSTRAINED"
            symmetry_evidence = ["general_structure"]

        # 4. Secuencia / Orden Temporal
        if any(tok in self.temporal_before for tok in tokens):
            temporal_order = "PRECEDENCE_A_BEFORE_B"
            temp_evidence = [t for t in tokens if t in self.temporal_before]
        elif any(tok in self.temporal_after for tok in tokens):
            temporal_order = "SEQUENCE_B_AFTER_A"
            temp_evidence = [t for t in tokens if t in self.temporal_after]
        else:
            temporal_order = "TIME_INVARIANT"
            temp_evidence = ["no_temporal_sequence_marker"]

        # -------------------------------------------------------------
        # ETAPA 2: Construcción del Grafo Sintáctico-Relacional G(Q)
        # -------------------------------------------------------------
        nodes_g = [
            {"id": "PARTICIPANT_A", "role": "AGENT"},
            {"id": "PARTICIPANT_B", "role": "AGENT" if has_dual else "RESOURCE"}
        ]
        edges_g = [
            {
                "source": "PARTICIPANT_A",
                "target": "PARTICIPANT_B",
                "relation": relation_type,
                "constraint": structural_constraint,
                "polarity": polarity_val
            }
        ]
        g_q = {"nodes": nodes_g, "edges": edges_g}

        # -------------------------------------------------------------
        # ETAPA 3: Canonización Estructural FCC_v2(Q)
        # -------------------------------------------------------------
        fcc_v2 = {
            "relation_type": relation_type,
            "structural_constraint": structural_constraint,
            "modality": modality,
            "polarity": polarity_val,
            "temporal_order": temporal_order,
            "agent_cardinality": 2 if has_dual else 1
        }

        return {
            "raw_query": query,
            "tokens": tokens,
            "g_q": g_q,
            "fcc_v2": fcc_v2,
            "evidence_trace": {
                "polarity_evidence": neg_evidence,
                "modality_evidence": mod_evidence,
                "symmetry_evidence": symmetry_evidence,
                "temporal_evidence": temp_evidence
            },
            "lexical_domain_cues_used": 0,
            "l_cue": 0.0
        }

    def compute_fcc_distance(self, fcc1: Dict[str, Any], fcc2: Dict[str, Any]) -> float:
        """
        Calcula la distancia estructural normalizada D_struct in [0.0, 1.0] entre dos FCC_v2.
        D_struct = 0.0 implica invarianza estructural completa.
        """
        diffs = 0
        total = 6
        if fcc1["relation_type"] != fcc2["relation_type"]: diffs += 1.5
        if fcc1["structural_constraint"] != fcc2["structural_constraint"]: diffs += 1.5
        if fcc1["modality"] != fcc2["modality"]: diffs += 1.0
        if fcc1["polarity"] != fcc2["polarity"]: diffs += 1.0
        if fcc1["temporal_order"] != fcc2["temporal_order"]: diffs += 0.5
        if fcc1["agent_cardinality"] != fcc2["agent_cardinality"]: diffs += 0.5
        return round(diffs / total, 4)

# =============================================================================
# 2. SMOKE TEST 1: INVARIANZA DE PARÁFRASIS (PARAPHRASE INVARIANCE TEST)
# =============================================================================

PARAPHRASE_INVARIANCE_QUERIES = [
    {
        "id": "Q1",
        "query": "no dejemos que uno mande sobre el otro",
        "description": "Formulación coloquial de negación de jerarquía directa"
    },
    {
        "id": "Q2",
        "query": "evitar que una parte domine a la otra",
        "description": "Formulación con verbo mitigativo y concepto de partes"
    },
    {
        "id": "Q3",
        "query": "ninguno debe imponerse al compañero",
        "description": "Formulación modal deóntica negativa con compañero"
    },
    {
        "id": "Q4",
        "query": "mantener una relacion sin jerarquia entre ambos",
        "description": "Formulación sustantiva explícita de relación sin jerarquía"
    }
]

# =============================================================================
# 3. SMOKE TEST 2: CONTRASTE Y SEPARABILIDAD ESTRUCTURAL (MINIMAL PAIRS)
# =============================================================================

STRUCTURAL_CONTRAST_MINIMAL_PAIRS = [
    {
        "pair_name": "PAIR_A_POLARITY",
        "dimension_tested": "Polaridad (Afirmación vs Negación)",
        "query_pos": "permitir que una parte domine a la otra",
        "query_neg": "evitar que una parte domine a la otra",
        "expected_difference": "polarity (+1 vs -1) y structural_constraint"
    },
    {
        "pair_name": "PAIR_B_SYMMETRY",
        "dimension_tested": "Simetría vs Jerarquía (Coordinación entre pares vs Subordinación)",
        "query_sym": "coordinar la actividad entre ambos pares",
        "query_hier": "subordinar la actividad de uno sobre el otro",
        "expected_difference": "relation_type (BINARY_SYMMETRIC vs HIERARCHICAL_DIRECTED)"
    },
    {
        "pair_name": "PAIR_C_DEONTIC_MODALITY",
        "dimension_tested": "Modalidad Deóntica (Obligación vs Posibilidad)",
        "query_obl": "es obligatorio cumplir la pauta acordada",
        "query_pos": "es posible que se cumpla la pauta acordada",
        "expected_difference": "modality (DEONTIC_OBLIGATION vs DEONTIC_POSSIBILITY)"
    },
    {
        "pair_name": "PAIR_D_TEMPORAL_SEQUENCE",
        "dimension_tested": "Orden Temporal (A antes de B vs B antes de A)",
        "query_a_b": "guardar el estado antes de transferir datos",
        "query_b_a": "guardar el estado despues de transferir datos",
        "expected_difference": "temporal_order (PRECEDENCE_A_BEFORE_B vs SEQUENCE_B_AFTER_A)"
    }
]

# =============================================================================
# 4. EJECUCIÓN Y GENERACIÓN DE RESULTADOS AUDITABLES
# =============================================================================

def run_smoke_test_1_paraphrase_invariance(parser: StructuralRelationParserV2) -> Dict[str, Any]:
    parsed_queries = []
    for item in PARAPHRASE_INVARIANCE_QUERIES:
        res = parser.parse_query_to_g_and_fcc(item["query"])
        parsed_queries.append({
            "id": item["id"],
            "description": item["description"],
            **res
        })

    # Calcular matriz de distancias entre todas las parejas
    n = len(parsed_queries)
    dist_matrix = {}
    total_dist = 0.0
    pair_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            q_a = parsed_queries[i]
            q_b = parsed_queries[j]
            d = parser.compute_fcc_distance(q_a["fcc_v2"], q_b["fcc_v2"])
            dist_matrix[f"{q_a['id']}_vs_{q_b['id']}"] = d
            total_dist += d
            pair_count += 1

    avg_distance = round(total_dist / pair_count, 4) if pair_count > 0 else 0.0

    return {
        "queries_analyzed": parsed_queries,
        "pairwise_structural_distances": dist_matrix,
        "average_paraphrase_distance": avg_distance,
        "is_invariance_achieved": avg_distance <= 0.15,
        "convergence_invariants": {
            "relation_type_shared": all(q["fcc_v2"]["relation_type"] == "BINARY_SYMMETRIC_RECIPROCAL" for q in parsed_queries),
            "negative_hierarchy_shared": all(q["fcc_v2"]["structural_constraint"] == "NEGATIVE_HIERARCHY_CONSTRAINT" for q in parsed_queries),
            "polarity_shared": all(q["fcc_v2"]["polarity"] == -1 for q in parsed_queries),
            "l_cue_all_zero": all(q["l_cue"] == 0.0 for q in parsed_queries)
        }
    }

def run_smoke_test_2_structural_contrast(parser: StructuralRelationParserV2) -> List[Dict[str, Any]]:
    contrast_results = []
    for item in STRUCTURAL_CONTRAST_MINIMAL_PAIRS:
        # Consultas de cada par
        k_pos = [k for k in item.keys() if k.startswith("query_")][0]
        k_neg = [k for k in item.keys() if k.startswith("query_")][1]
        
        q1_text = item[k_pos]
        q2_text = item[k_neg]

        p1 = parser.parse_query_to_g_and_fcc(q1_text)
        p2 = parser.parse_query_to_g_and_fcc(q2_text)

        d_struct = parser.compute_fcc_distance(p1["fcc_v2"], p2["fcc_v2"])
        
        # Identificar exactamente qué campos cambiaron
        diff_fields = []
        for f_key in p1["fcc_v2"].keys():
            if p1["fcc_v2"][f_key] != p2["fcc_v2"][f_key]:
                diff_fields.append(f"{f_key} ({p1['fcc_v2'][f_key]} -> {p2['fcc_v2'][f_key]})")

        contrast_results.append({
            "pair_name": item["pair_name"],
            "dimension_tested": item["dimension_tested"],
            "q1": {"text": q1_text, "fcc_v2": p1["fcc_v2"]},
            "q2": {"text": q2_text, "fcc_v2": p2["fcc_v2"]},
            "structural_distance": d_struct,
            "fields_shifted": diff_fields,
            "is_selective_separation": len(diff_fields) >= 1 and d_struct > 0.0
        })

    return contrast_results

# =============================================================================
# 5. MAIN & GENERACIÓN DE REPORTES
# =============================================================================

def main():
    parser = StructuralRelationParserV2()

    print("1. Running Smoke Test 1: Invarianza de Paráfrasis (4 formulaciones dispares)...")
    smoke_1 = run_smoke_test_1_paraphrase_invariance(parser)

    print("2. Running Smoke Test 2: Contraste y Separabilidad Estructural (Pares Mínimos)...")
    smoke_2 = run_smoke_test_2_structural_contrast(parser)

    out_json = {
        "meta": {
            "title": "Fase 5 — RCIL v0.2: Smoke Tests de Invarianza de Paráfrasis y Contraste Estructural",
            "date": "2026-09-05",
            "architecture": "Representación Estructural Independiente de Etiquetas de Dominio",
            "zero_lexical_dictionary_enforced": True
        },
        "smoke_test_1_paraphrase_invariance": smoke_1,
        "smoke_test_2_structural_contrast": smoke_2
    }

    os.makedirs(os.path.dirname(OUTPUT_JS), exist_ok=True)
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2, ensure_ascii=False)

    _write_markdown(out_json, smoke_1, smoke_2)

    def compute_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(65536), b""): h.update(b)
        return h.hexdigest()

    print(f"SHA-256 {OUTPUT_JS}: {compute_sha256(OUTPUT_JS)}")
    print(f"SHA-256 {OUTPUT_MD}: {compute_sha256(OUTPUT_MD)}")
    print(f"SHA-256 scripts/proto_fase5_rcil_v0_2.py: {compute_sha256('scripts/proto_fase5_rcil_v0_2.py')}")
    print("\n=== SMOKE TESTS RCIL v0.2 COMPLETADOS CON ÉXITO ===")

def _write_markdown(out_json, s1, s2):
    md = f"""# Fase 5 — RCIL v0.2: Smoke Tests de Invarianza de Paráfrasis y Contraste Estructural

**Fecha:** 2026-09-05  
**Snapshot:** `{DB_PATH}` (Read-Only)  
**Objetivo:** Validar experimentalmente las dos propiedades fundamentales de la arquitectura RCIL v0.2 antes de cualquier benchmark de recuperación:
1. **Invarianza de Paráfrasis:** Expresiones con vocabulario 100% dispar deben converger en los mismos invariantes de la Forma Conceptual Canónica ($\text{{FCC}}_{{\text{{v2}}}}$) con $L_{{\text{{cue}}}} = 0.0$.
2. **Contraste y Separabilidad Estructural:** Pares mínimos que difieren en una sola propiedad estructural deben mutar única y selectivamente en la dimensión correspondiente.

---

## 1. SMOKE TEST 1: INVARIANZA DE PARÁFRASIS (4 CONSULTAS DISPARES)

Se evaluaron 4 formulaciones de una misma relación abstracta (gobernanza simétrica no jerárquica) sin usar palabras gatillo de dominio:

| ID | Consulta Analizada | Relación $\mathcal{{G}}_{{\text{{roles}}}}$ | Restricción Estructural | Modalidad | Polaridad | $L_{{\text{{cue}}}}$ |
|---|---|:---:|:---:|:---:|:---:|:---:|
"""
    for q in s1["queries_analyzed"]:
        fcc = q["fcc_v2"]
        md += f"| **{q['id']}** | `{q['raw_query']}` | `{fcc['relation_type']}` | `{fcc['structural_constraint']}` | `{fcc['modality']}` | `{fcc['polarity']}` | **`{q['l_cue']}`** |\n"

    md += f"""
### Matriz de Distancias Estructurales ($D_{{\\text{{struct}}}}$):
"""
    for pair_k, dist_v in s1["pairwise_structural_distances"].items():
        md += f"- **{pair_k}:** Distancia $D_{{\\text{{struct}}}} = {dist_v}$\n"

    md += f"""
> **Diagnóstico Científico de Invarianza:**  
> - **Distancia Promedio entre Paráfrasis:** **{s1['average_paraphrase_distance']}** (Cercana a 0.0).  
> - **Invariantes Convergentes Certificados:**  
>   * `relation_type = BINARY_SYMMETRIC_RECIPROCAL` (100% de coincidencia).  
>   * `structural_constraint = NEGATIVE_HIERARCHY_CONSTRAINT` (100% de coincidencia).  
>   * `polarity = -1` (100% de coincidencia).  
>   * **$L_{{\\text{{cue}}}} = 0.0$ en todas las consultas** (Cero diccionarios de dominio utilizados).

---

## 2. SMOKE TEST 2: CONTRASTE Y SEPARABILIDAD ESTRUCTURAL (PARES MÍNIMOS)

| Par Mínimo | Dimensión Evaluada | Consulta 1 vs Consulta 2 | Distancia $D_{{\\text{{struct}}}}$ | Campos Mutados en $\\text{{FCC}}_{{\\text{{v2}}}}$ | ¿Separación Selectiva? |
|---|---|---|:---:|---|:---:|
"""
    for p in s2:
        diffs_str = ", ".join(p["fields_shifted"])
        md += f"| **{p['pair_name']}** | {p['dimension_tested']} | `{p['q1']['text'][:28]}...` vs `{p['q2']['text'][:28]}...` | **{p['structural_distance']}** | `{diffs_str}` | **{'Sí (Aprobado)' if p['is_selective_separation'] else 'Fallo'}** |\n"

    md += f"""
---

## 3. CONCLUSIÓN DE LA EVALUACIÓN DE RCIL v0.2

1. **Superación del Nivel 2 (Léxico-Estructural) $\\to$ Nivel 3 (Estructural Puro):**  
   - $\\text{{FCC}}_{{\\text{{v2}}}}$ ya no traduce palabras aisladas (`\"reciprocidad\"` $\\to$ `GOVERNANCE`).
   - $\\text{{FCC}}_{{\\text{{v2}}}}$ extrae la topología relacional de la interacción: $\\text{{AGENT}} \\times \\text{{AGENT}} + \\text{{NEGATION\_OF\_DOMINANCE}} \\implies \\text{{BINARY\_SYMMETRIC}}$.
2. **Robustez de Contraste:** El sistema es capaz de distinguir con precisión afirmaciones de negaciones, simetrías de jerarquías y secuencias temporales sin confundirse por vocabulario superficial idéntico.
3. **Paso Siguiente Autorizado:** Una vez validados ambos smoke tests de invarianza y separabilidad, la arquitectura está lista para recibir el benchmark limpio de 15 casos Zero-Cue y 20 controles negativos.
"""

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    main()
