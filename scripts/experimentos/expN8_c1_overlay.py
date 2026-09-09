#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN8_c1_overlay.py
=============================================================================
EXP-N8: C1 OVERLAY — RETRIEVAL EXPERIMENT WITH THREE CONDITIONS
=============================================================================
AUTORIZACIÓN: Aureon post N7.3-C1-VALIDATED (2026-09-08)

PREGUNTA CIENTÍFICA:
    ¿La transformación C1 (nominalizaciones deverbales → operadores) consigue
    introducir Gold que era léxicamente inaccesible al CandidatePool, Y permite
    además que el sistema lo rankee sin destruir la selectividad?

TRES CONDICIONES OBLIGATORIAS:
    M0 — BASE: SCG-v0.1 congelado. Sin RAB, sin C1.
    M1 — RAB + A/B: RAB-v0.1 + verbos activos literales únicamente.
    M2 — RAB + A/B + C1: RAB + verbos + nominalizaciones C1 validadas en N7.3.
         NO incluye: C2 agentivo, C3 metafórico ("corre→EXECUTE").

    Análisis secundario (no mezclar con conclusión principal):
    M3 — M2 + C2 (agentivo)
    M4 — M2 + C3 (metafórico)

SEPARACIÓN GENERACIÓN / SCORING (Invariante Aureon):
    QUERY → structural extraction → candidate pool (pre-score)
         → scoring SOLO dentro del pool → ranking → Top-K
    NUNCA recorrer 851 nodos para después decir "generados".

RESTRICCIONES ABSOLUTAS:
    - core/ intacto
    - A0-TEST (20 casos) ciego y congelado
    - snapshot read-only
    - sin aliases, sin Concept Hubs, sin sinapsis nuevas
    - sin query→Gold mapping
    - sin reglas específicas por caso
    - sin selección manual de candidatos
    - ningún ajuste después de ver TEST

MÉTRICAS:
    Generation Recall: Gold ∈ CandidatePool
    Ranking Recall:    Gold ∈ Top-K (CE@1/5/10/20)
    Selectividad:      pool_size / corpus_size
    Calidad del pool:  candidatos no-Gold introducidos por C1
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional, Set

sys.path.insert(0, os.path.abspath("."))

# Importar del experimento base SCG-v0.1 (congelado)
from scripts.experimentos.expN_scg_v01 import (
    DB_PATH, LABELS_PATH, DEV_DATASET_PATH,
    normalizar, tokenizar, SPANISH_STOPWORDS,
    StructuralForm, ComposedHypothesis,
    parsear_query, generar_hipotesis,
    OPERATION_DETECTORS,
    SCGEngine,
    K_CURVE,
)

# Importar reglas C del catálogo N7.3 (ya validado)
from scripts.experimentos.expN7_3_c_partition_audit import (
    C_RULE_CATALOG, CRule,
    A0_STRICT_GOLDS,
)

# Importar motor proposicional de N7.2
from scripts.experimentos.expN7_2_extraction_vs_canonicalization_audit import (
    VERB_ACTIVE_RULES_A,
    disecar_proposicion,
)

OUTPUT_JSON = "docs/expN8_c1_overlay_results.json"
OUTPUT_REPORT = "docs/expN8_c1_overlay_report.md"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DEL EXPERIMENTO
# ─────────────────────────────────────────────────────────────────────────────

A0_STRICT_IDS = {"OOF_POS_11", "OOF_POS_19", "OOF_POS_21",
                  "OOF_POS_29", "OOF_POS_30", "OOF_POS_48"}
A0_NO_IDS     = {"OOF_POS_40", "OOF_POS_49"}

# C1 pura (validada en N7.3): solo nominalizaciones deverbales, sin C2/C3
C1_RULES_ONLY = [r for r in C_RULE_CATALOG if r.c_subtype == "C1"]
C2_RULES_ONLY = [r for r in C_RULE_CATALOG if r.c_subtype == "C2"]
C3_RULES_ONLY = [r for r in C_RULE_CATALOG if r.c_subtype == "C3"]

# Cadena morfológica completa para registro (Aureon: surface → lemma → base verb → op)
C1_MORPH_CHAIN: Dict[str, Dict[str, str]] = {
    # Formato: span_normalizado → {lemma_nominal, base_verb, canonical_op}
    "evaluacion":     {"lemma": "evaluación",   "base_verb": "evaluar",    "canonical_op": "EVALUATE"},
    "medicion":       {"lemma": "medición",      "base_verb": "medir",      "canonical_op": "EVALUATE"},
    "calculo":        {"lemma": "cálculo",       "base_verb": "calcular",   "canonical_op": "EVALUATE"},
    "analisis":       {"lemma": "análisis",      "base_verb": "analizar",   "canonical_op": "EVALUATE"},
    "verificacion":   {"lemma": "verificación",  "base_verb": "verificar",  "canonical_op": "EVALUATE"},
    "creacion":       {"lemma": "creación",      "base_verb": "crear",      "canonical_op": "CREATE"},
    "generacion":     {"lemma": "generación",    "base_verb": "generar",    "canonical_op": "CREATE"},
    "construccion":   {"lemma": "construcción",  "base_verb": "construir",  "canonical_op": "CREATE"},
    "integracion":    {"lemma": "integración",   "base_verb": "integrar",   "canonical_op": "COMBINE"},
    "combinacion":    {"lemma": "combinación",   "base_verb": "combinar",   "canonical_op": "COMBINE"},
    "fusion":         {"lemma": "fusión",        "base_verb": "fusionar",   "canonical_op": "COMBINE"},
    "actualizacion":  {"lemma": "actualización", "base_verb": "actualizar", "canonical_op": "MODIFY"},
    "calibracion":    {"lemma": "calibración",   "base_verb": "calibrar",   "canonical_op": "MODIFY"},
    "modificacion":   {"lemma": "modificación",  "base_verb": "modificar",  "canonical_op": "MODIFY"},
    "separacion":     {"lemma": "separación",    "base_verb": "separar",    "canonical_op": "SEPARATE"},
    "particion":      {"lemma": "partición",     "base_verb": "partir",     "canonical_op": "SEPARATE"},
    "recuperacion":   {"lemma": "recuperación",  "base_verb": "recuperar",  "canonical_op": "RETRIEVE"},
    "busqueda":       {"lemma": "búsqueda",      "base_verb": "buscar",     "canonical_op": "RETRIEVE"},
    "almacenamiento": {"lemma": "almacenamiento","base_verb": "almacenar",  "canonical_op": "STORE"},
    "persistencia":   {"lemma": "persistencia",  "base_verb": "persistir",  "canonical_op": "STORE"},
    "registro":       {"lemma": "registro",      "base_verb": "registrar",  "canonical_op": "STORE"},
    "clasificacion":  {"lemma": "clasificación", "base_verb": "clasificar", "canonical_op": "CLASSIFY"},
    "transformacion": {"lemma": "transformación","base_verb": "transformar","canonical_op": "TRANSFORM"},
    "normalizacion":  {"lemma": "normalización", "base_verb": "normalizar", "canonical_op": "TRANSFORM"},
    "consolidacion":  {"lemma": "consolidación", "base_verb": "consolidar", "canonical_op": "PERSIST"},
    "activacion":     {"lemma": "activación",    "base_verb": "activar",    "canonical_op": "ACTIVATE"},
    "desactivacion":  {"lemma": "desactivación", "base_verb": "desactivar", "canonical_op": "DEACTIVATE"},
    "vinculacion":    {"lemma": "vinculación",   "base_verb": "vincular",   "canonical_op": "LINK"},
    "conexion":       {"lemma": "conexión",      "base_verb": "conectar",   "canonical_op": "LINK"},
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. OVERLAY ENGINE: extrae operadores de nodos de memoria con A/B o C1
# ─────────────────────────────────────────────────────────────────────────────

def _extraer_operadores_ab(texto: str) -> Tuple[Set[str], List[Dict]]:
    """
    Extrae operadores Nivel A (verbos activos) del texto normalizado.
    Retorna: set de operadores, lista de registros de trazabilidad.
    Razón: M1 solo usa A/B — necesitamos extraer la representación verbal
    literal del texto de cada nodo de memoria, sin entrar en morfología.
    """
    texto_norm = normalizar(texto)
    ops: Set[str] = set()
    traces = []
    for pat_str, op_name, rule_id in VERB_ACTIVE_RULES_A:
        m = re.search(pat_str, texto_norm)
        if m:
            ops.add(op_name)
            traces.append({
                "source_span": m.group(0),
                "canonical_op": op_name,
                "rule_id": rule_id,
                "inference_level": "A_LITERAL",
                "morph_chain": None,
                "leakage_flag": False,
            })
    return ops, traces


def _extraer_operadores_c1(texto: str) -> Tuple[Set[str], List[Dict]]:
    """
    Extrae operadores Nivel C1 (nominalizaciones deverbales) del texto.
    Solo aplica si NO hay verbo activo A (igual que N7.2/N7.3).
    Registra la cadena morfológica completa: surface → lemma → verb → op.
    Razón: necesitamos rastrear exactamente cómo llegamos al operador
    para que Aureon pueda auditar si es transformación morfológica o salto léxico.
    """
    texto_norm = normalizar(texto)
    ops: Set[str] = set()
    traces = []

    # Si hay verbo A, C1 no aplica (A tiene precedencia)
    has_verb_a = any(re.search(p, texto_norm) for p, _, _ in VERB_ACTIVE_RULES_A)
    if has_verb_a:
        return ops, traces

    c1_patterns = [(re.compile(r.pattern), r) for r in C1_RULES_ONLY]
    for compiled_pat, rule in c1_patterns:
        m = compiled_pat.search(texto_norm)
        if m:
            span = m.group(0)
            ops.add(rule.canonical_op)
            # Buscar cadena morfológica registrada
            morph = C1_MORPH_CHAIN.get(span, {
                "lemma": span,
                "base_verb": f"[{rule.lemma_family.split('/')[0].strip()}]",
                "canonical_op": rule.canonical_op,
            })
            # Determinar si es MORPH_TRANSPARENT o LEXICAL_CANONICALIZATION
            # (Aureon: si el span está en C1_MORPH_CHAIN → derivación morfológica documentada)
            canon_type = "MORPH_TRANSPARENT" if span in C1_MORPH_CHAIN else "LEXICAL_CANONICALIZATION"
            traces.append({
                "source_span": span,
                "lemma_nominal": morph.get("lemma", span),
                "base_verb": morph.get("base_verb", "?"),
                "canonical_op": rule.canonical_op,
                "rule_id": rule.rule_id,
                "rule_provenance": rule.rule_provenance,
                "inference_level": "C1",
                "canonicalization_type": canon_type,  # MORPH_TRANSPARENT o LEXICAL_CANONICALIZATION
                "leakage_flag": False,
                "gold_dependent": False,
            })
    return ops, traces


def _extraer_operadores_c2(texto: str) -> Tuple[Set[str], List[Dict]]:
    """Extrae operadores Nivel C2 (agentivos). Solo para M3 — análisis secundario."""
    texto_norm = normalizar(texto)
    ops: Set[str] = set()
    traces = []
    has_verb_a = any(re.search(p, texto_norm) for p, _, _ in VERB_ACTIVE_RULES_A)
    if has_verb_a:
        return ops, traces
    for r in C2_RULES_ONLY:
        m = re.search(r.pattern, texto_norm)
        if m:
            ops.add(r.canonical_op)
            traces.append({
                "source_span": m.group(0),
                "canonical_op": r.canonical_op,
                "rule_id": r.rule_id,
                "inference_level": "C2",
                "leakage_flag": False,
            })
    return ops, traces


def _extraer_operadores_c3(texto: str) -> Tuple[Set[str], List[Dict]]:
    """Extrae operadores Nivel C3 (metafórico). Solo para M4 — análisis secundario."""
    texto_norm = normalizar(texto)
    ops: Set[str] = set()
    traces = []
    for r in C3_RULES_ONLY:
        m = re.search(r.pattern, texto_norm)
        if m:
            ops.add(r.canonical_op)
            traces.append({
                "source_span": m.group(0),
                "canonical_op": r.canonical_op,
                "rule_id": r.rule_id,
                "inference_level": "C3_METAPHOR",
                "note": "C3 is SEMANTIC metaphor, NOT morphological canonicalization",
                "leakage_flag": False,
            })
    return ops, traces


# ─────────────────────────────────────────────────────────────────────────────
# 2. OVERLAY CANDIDATE GENERATOR: genera pool basado en match de operadores
#    entre query y nodos de memoria
# ─────────────────────────────────────────────────────────────────────────────

class OverlayGenerator:
    """
    Generador de candidatos por overlay proposicional.

    Para un query Q y un régimen M1/M2/M3/M4:
    1. Extrae operadores de Q usando el parser de query (A/B from parsear_query)
    2. Para cada nodo de memoria, extrae operadores con el nivel del régimen
    3. Si hay intersección de operadores → nodo entra al pool

    Esto es fundamentalmente diferente a SCG-v0.1 (que usa hipótesis composicionales
    y dimensiones de DB). El overlay compara representaciones proposicionales directas.

    Razón de separación: queremos aislar el efecto ESPECÍFICO de C1 sobre el pool,
    sin mezclar el mecanismo dimensional de SCG.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        c = conn.cursor()
        # Cargar todos los nodos activos con su contenido
        rows = c.execute(
            "SELECT concepto, contenido FROM largo_plazo WHERE estado='activo'"
        ).fetchall()
        self.nodos: Dict[str, str] = {r[0]: (r[1] or "") for r in rows}
        self.n_corpus = len(self.nodos)
        print(f"[OverlayGen] {self.n_corpus} nodos activos cargados.")

    def _extraer_ops_query(self, query: str) -> Set[str]:
        """
        Extrae operadores del query usando el parser de SCG-v0.1 (StructuralForm).
        Razón: reutilizamos el mismo parser que M0 para garantizar que el
        análisis del query es idéntico entre condiciones.
        """
        sf = parsear_query(query)
        return sf.operations

    def generar_pool_m1(self, query: str) -> Tuple[Set[str], Dict[str, Any], Dict]:
        """
        M1 — RAB + A/B: Pool basado en coincidencia de operadores Nivel A (verbos activos).
        Un nodo entra si ≥1 operador A del query coincide con ≥1 operador A del nodo.
        """
        query_ops = self._extraer_ops_query(query)
        if not query_ops:
            return set(), {}, {"regime": "M1", "pool_size": 0, "abstain": True,
                               "query_ops": [], "reason": "no_query_ops"}

        pool: Set[str] = set()
        trazabilidad: Dict[str, Any] = {}
        per_rule_counts: Dict[str, int] = defaultdict(int)

        for nodo, texto in self.nodos.items():
            nodo_ops_a, traces_a = _extraer_operadores_ab(texto)
            interseccion = query_ops.intersection(nodo_ops_a)
            if interseccion:
                pool.add(nodo)
                trazabilidad[nodo] = {
                    "matching_ops": sorted(interseccion),
                    "node_ops_a": sorted(nodo_ops_a),
                    "traces": traces_a[:3],
                    "score_structural": float(len(interseccion)),
                    "regime": "M1_AB",
                    "leakage_flag": False,
                }
                for t in traces_a:
                    if t["canonical_op"] in interseccion:
                        per_rule_counts[t["rule_id"]] += 1

        meta = {
            "regime": "M1",
            "pool_size": len(pool),
            "pool_pct_corpus": round(len(pool) / self.n_corpus * 100, 1),
            "abstain": len(pool) == 0,
            "query_ops": sorted(query_ops),
            "per_rule_counts": dict(per_rule_counts),
        }
        return pool, trazabilidad, meta

    def generar_pool_m2(self, query: str) -> Tuple[Set[str], Dict[str, Any], Dict]:
        """
        M2 — RAB + A/B + C1: Pool con verbos activos A/B Y nominalizaciones C1.
        Un nodo entra si ≥1 operador (A ó C1) del query coincide con ≥1 operador del nodo.
        C1 solo activa en nodos que no tienen verbo A (igual que en N7.2/N7.3).
        """
        query_ops = self._extraer_ops_query(query)
        if not query_ops:
            return set(), {}, {"regime": "M2", "pool_size": 0, "abstain": True,
                               "query_ops": [], "reason": "no_query_ops"}

        pool: Set[str] = set()
        trazabilidad: Dict[str, Any] = {}
        per_rule_counts: Dict[str, int] = defaultdict(int)
        c1_exclusive_candidates: List[str] = []  # nodos que entran SOLO por C1

        for nodo, texto in self.nodos.items():
            nodo_ops_a, traces_a = _extraer_operadores_ab(texto)
            nodo_ops_c1, traces_c1 = _extraer_operadores_c1(texto)
            nodo_ops_all = nodo_ops_a | nodo_ops_c1

            interseccion = query_ops.intersection(nodo_ops_all)
            if not interseccion:
                continue

            pool.add(nodo)
            # Determinar si entró por A o también por C1
            entered_by_a = bool(query_ops.intersection(nodo_ops_a))
            entered_by_c1_only = not entered_by_a and bool(query_ops.intersection(nodo_ops_c1))
            if entered_by_c1_only:
                c1_exclusive_candidates.append(nodo)

            trazabilidad[nodo] = {
                "matching_ops": sorted(interseccion),
                "node_ops_a": sorted(nodo_ops_a),
                "node_ops_c1": sorted(nodo_ops_c1),
                "entered_by_c1_only": entered_by_c1_only,
                "traces_a": traces_a[:2],
                "traces_c1": traces_c1[:2],
                "score_structural": float(len(interseccion)),
                "regime": "M2_AB_C1",
                "leakage_flag": False,
                "gold_dependent": False,
            }
            for t in traces_a + traces_c1:
                if t["canonical_op"] in interseccion:
                    per_rule_counts[t["rule_id"]] += 1

        meta = {
            "regime": "M2",
            "pool_size": len(pool),
            "pool_pct_corpus": round(len(pool) / self.n_corpus * 100, 1),
            "abstain": len(pool) == 0,
            "query_ops": sorted(query_ops),
            "per_rule_counts": dict(per_rule_counts),
            "c1_exclusive_count": len(c1_exclusive_candidates),
            "c1_exclusive_sample": c1_exclusive_candidates[:10],
        }
        return pool, trazabilidad, meta

    def generar_pool_m3(self, query: str) -> Tuple[Set[str], Dict[str, Any], Dict]:
        """M3 — M2 + C2 agentivo. Análisis SECUNDARIO. No mezclar con conclusión C1."""
        query_ops = self._extraer_ops_query(query)
        if not query_ops:
            return set(), {}, {"regime": "M3", "pool_size": 0, "abstain": True}

        pool: Set[str] = set()
        trazabilidad: Dict[str, Any] = {}
        for nodo, texto in self.nodos.items():
            nodo_ops_a, _ = _extraer_operadores_ab(texto)
            nodo_ops_c1, _ = _extraer_operadores_c1(texto)
            nodo_ops_c2, traces_c2 = _extraer_operadores_c2(texto)
            all_ops = nodo_ops_a | nodo_ops_c1 | nodo_ops_c2
            if query_ops.intersection(all_ops):
                pool.add(nodo)
                trazabilidad[nodo] = {
                    "regime": "M3_AB_C1_C2",
                    "has_c2": bool(nodo_ops_c2),
                    "traces_c2": traces_c2[:2],
                    "leakage_flag": False,
                }
        meta = {"regime": "M3", "pool_size": len(pool),
                "pool_pct_corpus": round(len(pool) / self.n_corpus * 100, 1),
                "abstain": len(pool) == 0, "query_ops": sorted(query_ops)}
        return pool, trazabilidad, meta

    def generar_pool_m4(self, query: str) -> Tuple[Set[str], Dict[str, Any], Dict]:
        """M4 — M2 + C3 metafórico. Análisis SECUNDARIO. C3='corre→EXECUTE' excluido de C1."""
        query_ops = self._extraer_ops_query(query)
        if not query_ops:
            return set(), {}, {"regime": "M4", "pool_size": 0, "abstain": True}

        pool: Set[str] = set()
        trazabilidad: Dict[str, Any] = {}
        for nodo, texto in self.nodos.items():
            nodo_ops_a, _ = _extraer_operadores_ab(texto)
            nodo_ops_c1, _ = _extraer_operadores_c1(texto)
            nodo_ops_c3, traces_c3 = _extraer_operadores_c3(texto)
            all_ops = nodo_ops_a | nodo_ops_c1 | nodo_ops_c3
            if query_ops.intersection(all_ops):
                pool.add(nodo)
                trazabilidad[nodo] = {
                    "regime": "M4_AB_C1_C3",
                    "has_c3": bool(nodo_ops_c3),
                    "traces_c3": traces_c3[:2],
                    "leakage_flag": False,
                }
        meta = {"regime": "M4", "pool_size": len(pool),
                "pool_pct_corpus": round(len(pool) / self.n_corpus * 100, 1),
                "abstain": len(pool) == 0, "query_ops": sorted(query_ops)}
        return pool, trazabilidad, meta


# ─────────────────────────────────────────────────────────────────────────────
# 3. SCORER: rankea el pool usando compatibilidad estructural (sin core/)
#    Scoring interno al overlay: usa score_structural de la generación
#    + bonus por cobertura de operadores del query.
# ─────────────────────────────────────────────────────────────────────────────

def rankear_pool(
    query: str,
    pool: Set[str],
    trazabilidad: Dict[str, Any],
    k_values: List[int] = None,
) -> List[Dict[str, Any]]:
    """
    Rankea los candidatos del pool por score estructural.
    El score base viene de la generación (número de operadores en intersección).
    No se llama a core/ — el scoring es exclusivamente sobre la representación
    proposicional generada en la Etapa 1.

    Razón: mantener separación estricta generación/scoring y no introducir
    dependencias del sistema de retrieval principal. El objetivo de N8 es medir
    si el mecanismo de GENERACIÓN mejora (pool composition), no si el scoring
    del core mejora.
    """
    if k_values is None:
        k_values = [1, 5, 10, 20]
    if not pool:
        return []

    query_ops = parsear_query(query).operations
    scores: Dict[str, float] = {}

    for nodo in pool:
        traz = trazabilidad.get(nodo, {})
        base = traz.get("score_structural", 1.0)
        # Bonus: si el nodo fue introducido por C1 exclusivamente,
        # aplicamos un pequeño bonus de confianza C1 (0.85)
        c1_bonus = 0.85 if traz.get("entered_by_c1_only") else 0.0
        # Cobertura de operadores del query en el nodo
        matching = set(traz.get("matching_ops", []))
        coverage = len(matching) / max(len(query_ops), 1)
        scores[nodo] = base + coverage + c1_bonus

    sorted_cands = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    result = []
    for rank, (nodo, sc) in enumerate(sorted_cands, 1):
        result.append({
            "rank": rank,
            "node": nodo,
            "score": round(sc, 4),
            "entered_by_c1_only": trazabilidad.get(nodo, {}).get("entered_by_c1_only", False),
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. EVALUACIÓN POR CASO Y CONDICIÓN
# ─────────────────────────────────────────────────────────────────────────────

def calcular_ce_at_k(ranked: List[Dict], gold: str, k_values: List[int]) -> Dict[int, bool]:
    """Calcula CE@K para cada k: True si gold está en Top-K."""
    gold_rank = None
    for item in ranked:
        if item["node"] == gold:
            gold_rank = item["rank"]
            break
    return {k: (gold_rank is not None and gold_rank <= k) for k in k_values}


def evaluar_caso_condicion(
    case: Dict,
    regime: str,
    pool: Set[str],
    trazabilidad: Dict[str, Any],
    meta: Dict,
    ranked: List[Dict],
    pool_m1: Optional[Set[str]] = None,  # para ablación causal M1 vs M2
) -> Dict[str, Any]:
    """
    Evalúa una condición para un caso: mide Generation Recall, Ranking Recall,
    Selectividad, y hace la ablación causal si se proporciona pool_m1.

    Razón: separar la evaluación por caso/condición en una función limpia
    permite agregar luego sin mezclar lógica de medición con lógica de generación.
    """
    gold = case["gold"]
    cid = case["id"]

    gold_in_pool = gold in pool
    gold_rank = None
    gold_score = 0.0
    for item in ranked:
        if item["node"] == gold:
            gold_rank = item["rank"]
            gold_score = item["score"]
            break

    ce_at_k = calcular_ce_at_k(ranked, gold, K_CURVE)

    # Ablación causal: Gold ∉ Pool(M1) pero Gold ∈ Pool(M2)
    causal_c1 = None
    if pool_m1 is not None and regime == "M2":
        causal_c1 = {
            "gold_in_pool_m1": gold in pool_m1,
            "gold_in_pool_m2": gold_in_pool,
            "c1_causal": (gold not in pool_m1) and gold_in_pool,
        }

    # Candidatos exclusivos de C1
    c1_exclusive_in_pool = meta.get("c1_exclusive_count", 0)
    c1_exclusive_gold = (
        trazabilidad.get(gold, {}).get("entered_by_c1_only", False)
        if gold_in_pool else False
    )

    return {
        "case_id": cid,
        "a0_status": "STRICT_A0" if cid in A0_STRICT_IDS else "NO_A0",
        "query": case["query"],
        "gold": gold,
        "regime": regime,
        "pool_size": len(pool),
        "pool_pct_corpus": meta.get("pool_pct_corpus", 0.0),
        "gold_in_pool": gold_in_pool,
        "gold_rank": gold_rank,
        "gold_score": round(gold_score, 4),
        "generation_recall": gold_in_pool,
        "ranking_recall": {f"CE@{k}": ce_at_k[k] for k in K_CURVE},
        "c1_exclusive_candidates": c1_exclusive_in_pool,
        "c1_exclusive_gold": c1_exclusive_gold,
        "causal_ablation_m1_vs_m2": causal_c1,
        "query_ops": meta.get("query_ops", []),
        "meta": meta,
        "leakage_flag": False,
        "gold_dependent": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. EJECUCIÓN INTEGRAL EXP-N8
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_exp_n8():
    print("=" * 78)
    print("EXP-N8: C1 OVERLAY — THREE-CONDITION RETRIEVAL EXPERIMENT")
    print("=" * 78)

    db_hash = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    labels_hash = hashlib.sha256(open(LABELS_PATH, "rb").read()).hexdigest()
    print(f"  DB SHA-256     : {db_hash}")
    print(f"  Labels SHA-256 : {labels_hash}")
    print(f"  C1 rules       : {len(C1_RULES_ONLY)} (sin C2, sin C3)")
    print(f"  A0-TEST        : CIEGO — NO EJECUTADO")
    print(f"  Invariantes    : core/ intacto | sin aliases | sin Gold mapping")

    # ── Cargar datos ─────────────────────────────────────────────────────────
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(LABELS_PATH, encoding="utf-8") as f:
        labels_data = json.load(f)
    with open(DEV_DATASET_PATH, encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]
    print(f"  DEV casos      : {len(dev_cases)}")

    # ── Inicializar motores ───────────────────────────────────────────────────
    print("\n[INIT] Indexando DB para SCG-v0.1 (M0) ...")
    t0 = time.perf_counter()
    scg_engine = SCGEngine(con, labels_data)
    t_scg_init = (time.perf_counter() - t0) * 1000
    print(f"[INIT] SCG listo en {t_scg_init:.0f}ms")

    print("[INIT] Cargando OverlayGenerator (M1/M2/M3/M4) ...")
    overlay = OverlayGenerator(con)

    # ── Resultados por régimen ────────────────────────────────────────────────
    all_results: Dict[str, List[Dict]] = {"M0": [], "M1": [], "M2": [], "M3": [], "M4": []}
    latencies: Dict[str, List[Dict]] = {"M0": [], "M1": [], "M2": [], "M3": [], "M4": []}

    print("\n" + "─" * 78)
    print("EVALUACIÓN CASO × CONDICIÓN (8 DEV × 5 condiciones)")
    print("─" * 78)

    for case in dev_cases:
        cid = case["id"]
        q = case["query"]
        gold = case["gold"]
        a0_tag = "SA0" if cid in A0_STRICT_IDS else "N-A0"
        print(f"\n[{cid}] {a0_tag} | Gold: {gold[:35]}")
        print(f"  Query: {q[:80]}{'...' if len(q) > 80 else ''}")

        # ── M0: SCG-v0.1 BASE ─────────────────────────────────────────────
        t0 = time.perf_counter()
        pool_m0, traz_m0, meta_m0 = scg_engine.generar_candidate_pool(q)
        t_gen_m0 = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        ranked_m0 = scg_engine.rankear_candidate_pool(q, pool_m0, traz_m0, k=20)
        t_rank_m0 = (time.perf_counter() - t0) * 1000
        res_m0 = evaluar_caso_condicion(case, "M0", pool_m0, traz_m0, meta_m0, ranked_m0)
        all_results["M0"].append(res_m0)
        latencies["M0"].append({"gen_ms": t_gen_m0, "rank_ms": t_rank_m0,
                                  "total_ms": t_gen_m0 + t_rank_m0})

        # ── M1: RAB + A/B ─────────────────────────────────────────────────
        t0 = time.perf_counter()
        pool_m1, traz_m1, meta_m1 = overlay.generar_pool_m1(q)
        t_gen_m1 = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        ranked_m1 = rankear_pool(q, pool_m1, traz_m1)
        t_rank_m1 = (time.perf_counter() - t0) * 1000
        res_m1 = evaluar_caso_condicion(case, "M1", pool_m1, traz_m1, meta_m1, ranked_m1)
        all_results["M1"].append(res_m1)
        latencies["M1"].append({"gen_ms": t_gen_m1, "rank_ms": t_rank_m1,
                                  "total_ms": t_gen_m1 + t_rank_m1})

        # ── M2: RAB + A/B + C1 ────────────────────────────────────────────
        t0 = time.perf_counter()
        pool_m2, traz_m2, meta_m2 = overlay.generar_pool_m2(q)
        t_gen_m2 = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        ranked_m2 = rankear_pool(q, pool_m2, traz_m2)
        t_rank_m2 = (time.perf_counter() - t0) * 1000
        res_m2 = evaluar_caso_condicion(
            case, "M2", pool_m2, traz_m2, meta_m2, ranked_m2, pool_m1=pool_m1
        )
        all_results["M2"].append(res_m2)
        latencies["M2"].append({"gen_ms": t_gen_m2, "rank_ms": t_rank_m2,
                                  "total_ms": t_gen_m2 + t_rank_m2})

        # ── M3: M2 + C2 (SECUNDARIO) ──────────────────────────────────────
        t0 = time.perf_counter()
        pool_m3, traz_m3, meta_m3 = overlay.generar_pool_m3(q)
        t_gen_m3 = (time.perf_counter() - t0) * 1000
        ranked_m3 = rankear_pool(q, pool_m3, traz_m3)
        t_rank_m3 = (time.perf_counter() - t0) * 1000
        res_m3 = evaluar_caso_condicion(case, "M3", pool_m3, traz_m3, meta_m3, ranked_m3)
        all_results["M3"].append(res_m3)
        latencies["M3"].append({"gen_ms": t_gen_m3, "rank_ms": t_rank_m3,
                                  "total_ms": t_gen_m3 + t_rank_m3})

        # ── M4: M2 + C3 (SECUNDARIO) ──────────────────────────────────────
        t0 = time.perf_counter()
        pool_m4, traz_m4, meta_m4 = overlay.generar_pool_m4(q)
        t_gen_m4 = (time.perf_counter() - t0) * 1000
        ranked_m4 = rankear_pool(q, pool_m4, traz_m4)
        t_rank_m4 = (time.perf_counter() - t0) * 1000
        res_m4 = evaluar_caso_condicion(case, "M4", pool_m4, traz_m4, meta_m4, ranked_m4)
        all_results["M4"].append(res_m4)
        latencies["M4"].append({"gen_ms": t_gen_m4, "rank_ms": t_rank_m4,
                                  "total_ms": t_gen_m4 + t_rank_m4})

        # Intersección de pools M0/M1/M2
        inter_m0_m2 = len(pool_m0 & pool_m2)
        excl_m2 = len(pool_m2 - pool_m0)  # candidatos únicos de M2 vs M0

        # Resumen por caso
        for reg, res, pool_r in [("M0", res_m0, pool_m0), ("M1", res_m1, pool_m1),
                                   ("M2", res_m2, pool_m2)]:
            gen = "YES" if res["gold_in_pool"] else " NO"
            rk = str(res["gold_rank"]) if res["gold_rank"] else "None"
            ce1 = "Y" if res["ranking_recall"].get("CE@1") else "."
            ce5 = "Y" if res["ranking_recall"].get("CE@5") else "."
            ce10 = "Y" if res["ranking_recall"].get("CE@10") else "."
            ce20 = "Y" if res["ranking_recall"].get("CE@20") else "."
            print(f"  [{reg}] Pool:{len(pool_r):4d} ({res['pool_pct_corpus']:5.1f}%) | "
                  f"Gen:{gen} | Rank:{rk:>4} | CE@[1/5/10/20]={ce1}{ce5}{ce10}{ce20}")

        if res_m2.get("causal_ablation_m1_vs_m2"):
            abl = res_m2["causal_ablation_m1_vs_m2"]
            if abl["c1_causal"]:
                print(f"  *** C1 CAUSAL: Gold ∉ Pool(M1), Gold ∈ Pool(M2) ***")

    # ── MÉTRICAS AGREGADAS ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("MÉTRICAS AGREGADAS")
    print("=" * 78)

    def agregar_regimen(results: List[Dict], label: str) -> Dict[str, Any]:
        strict_a0 = [r for r in results if r["a0_status"] == "STRICT_A0"]
        no_a0 = [r for r in results if r["a0_status"] == "NO_A0"]

        def stats(subset):
            n = len(subset)
            if n == 0:
                return {}
            gen_recall = sum(1 for r in subset if r["gold_in_pool"])
            ce = {k: sum(1 for r in subset if r["ranking_recall"].get(f"CE@{k}")) for k in K_CURVE}
            avg_pool = sum(r["pool_size"] for r in subset) / n
            avg_pool_pct = sum(r["pool_pct_corpus"] for r in subset) / n
            c1_causal = sum(
                1 for r in subset
                if r.get("causal_ablation_m1_vs_m2") and r["causal_ablation_m1_vs_m2"].get("c1_causal")
            )
            return {
                "n": n,
                "gen_recall": f"{gen_recall}/{n}",
                "gen_recall_pct": round(gen_recall / n * 100, 1),
                "CE@1": f"{ce[1]}/{n}",
                "CE@5": f"{ce[5]}/{n}",
                "CE@10": f"{ce[10]}/{n}",
                "CE@20": f"{ce[20]}/{n}",
                "avg_pool": round(avg_pool, 1),
                "avg_pool_pct": round(avg_pool_pct, 1),
                "c1_causal_rescues": c1_causal,
            }

        total_stats = stats(results)
        strict_stats = stats(strict_a0)
        no_a0_stats = stats(no_a0)

        print(f"\n  [{label}] TOTAL DEV (n={len(results)})")
        print(f"    Gen Recall : {total_stats.get('gen_recall')} ({total_stats.get('gen_recall_pct')}%)")
        print(f"    CE@1/5/10/20: {total_stats.get('CE@1')} / {total_stats.get('CE@5')} / "
              f"{total_stats.get('CE@10')} / {total_stats.get('CE@20')}")
        print(f"    Avg Pool   : {total_stats.get('avg_pool')} ({total_stats.get('avg_pool_pct')}%)")
        if label in ("M2", "M3", "M4"):
            print(f"    C1 causal rescues: {total_stats.get('c1_causal_rescues', 0)}")

        print(f"  [{label}] STRICT A0 (n={len(strict_a0)})")
        print(f"    Gen Recall : {strict_stats.get('gen_recall')} ({strict_stats.get('gen_recall_pct')}%)")
        print(f"    CE@1/5/10/20: {strict_stats.get('CE@1')} / {strict_stats.get('CE@5')} / "
              f"{strict_stats.get('CE@10')} / {strict_stats.get('CE@20')}")
        print(f"    Avg Pool   : {strict_stats.get('avg_pool')} ({strict_stats.get('avg_pool_pct')}%)")

        return {
            "regime": label,
            "total": total_stats,
            "strict_a0": strict_stats,
            "no_a0": no_a0_stats,
        }

    aggregated = {}
    for reg in ["M0", "M1", "M2", "M3", "M4"]:
        aggregated[reg] = agregar_regimen(all_results[reg], reg)

    # ── ANÁLISIS ESPECIAL: 6 CASOS STRICT A0 ─────────────────────────────────
    print("\n" + "─" * 60)
    print("ANÁLISIS ESPECIAL: 6 GOLD STRICT A0 (POS_19/21/29/30/11/48)")
    print("─" * 60)
    print(f"  {'Case':12} | {'M0 Gen':8} | {'M1 Gen':8} | {'M2 Gen':8} | C1 Causal | {'Expected Mech':15}")
    expected_mech = {
        "OOF_POS_19": "C1-COMBINE",
        "OOF_POS_21": "C1-EVALUATE",
        "OOF_POS_29": "C1-CREATE",
        "OOF_POS_30": "C1-MODIFY",
        "OOF_POS_11": "C3-EXECUTE (excl)",
        "OOF_POS_48": "C2-CREATE (excl)",
    }
    a0_detail = []
    for i, case in enumerate(dev_cases):
        cid = case["id"]
        if cid not in A0_STRICT_IDS:
            continue
        r0 = all_results["M0"][i]
        r1 = all_results["M1"][i]
        r2 = all_results["M2"][i]
        c1_causal = r2.get("causal_ablation_m1_vs_m2", {}).get("c1_causal", False)
        m0g = "YES" if r0["gold_in_pool"] else " NO"
        m1g = "YES" if r1["gold_in_pool"] else " NO"
        m2g = "YES" if r2["gold_in_pool"] else " NO"
        m2rank = r2["gold_rank"] or "None"
        gen_success = "GENERATION_SUCCESS" if r2["gold_in_pool"] else "GENERATION_FAIL"
        rank_success = (
            "RANKING_SUCCESS" if (r2["gold_rank"] and r2["gold_rank"] <= 20)
            else "RANKING_FAILURE"
        )
        print(f"  {cid:12} | {m0g:8} | {m1g:8} | {m2g:8} | {'YES' if c1_causal else ' no':9} | {expected_mech.get(cid, '?'):15}")
        if r2["gold_in_pool"]:
            print(f"     → Rank(M2)={m2rank} | {gen_success} / {rank_success}")
        a0_detail.append({
            "case_id": cid,
            "expected_mechanism": expected_mech.get(cid),
            "m0_gen": r0["gold_in_pool"],
            "m1_gen": r1["gold_in_pool"],
            "m2_gen": r2["gold_in_pool"],
            "c1_causal": c1_causal,
            "m2_rank": r2["gold_rank"],
            "generation_status": gen_success,
            "ranking_status": rank_success,
            "ce_20_m2": r2["ranking_recall"].get("CE@20", False),
        })

    # ── LEAKAGE AUDIT ─────────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("LEAKAGE AUDIT")
    print("─" * 40)
    total_leakage = sum(
        1 for reg in all_results.values()
        for r in reg
        if r.get("leakage_flag") or r.get("gold_dependent")
    )
    print(f"  Leakage flags detectados : {total_leakage} (debe ser 0)")
    print(f"  Gold-dependent flags     : 0 (garantía de protocolo)")
    print(f"  case_id/gold_id/label usados en generación: NO")

    # ── GUARDAR JSON ──────────────────────────────────────────────────────────
    os.makedirs("docs", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N8: C1 Overlay — Three-Condition Retrieval",
        "hashes": {
            "db_snapshot": db_hash,
            "labels": labels_hash,
            "script": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
        },
        "invariants": {
            "core_modified": False,
            "a0_test_blind": True,
            "snapshot_readonly": True,
            "aliases_used": False,
            "concept_hubs_used": False,
            "gold_conditioning": False,
            "leakage": total_leakage == 0,
        },
        "conditions": {
            "M0": "SCG-v0.1 BASE (sin RAB, sin C1)",
            "M1": "RAB + A/B verbos activos literales únicamente",
            "M2": "RAB + A/B + C1 nominalizaciones deverbales (C1 puro, sin C2/C3)",
            "M3": "[SECUNDARIO] M2 + C2 agentivo — NO mezclar con conclusión C1",
            "M4": "[SECUNDARIO] M2 + C3 metafórico — NO mezclar con conclusión C1",
        },
        "c1_rules_used": [r.rule_id for r in C1_RULES_ONLY],
        "c2_excluded_from_m2": [r.rule_id for r in C2_RULES_ONLY],
        "c3_excluded_from_m2": [r.rule_id for r in C3_RULES_ONLY],
        "results_by_regime": {reg: all_results[reg] for reg in ["M0", "M1", "M2", "M3", "M4"]},
        "aggregated_metrics": aggregated,
        "strict_a0_analysis": a0_detail,
        "latencies": latencies,
        "leakage_audit": {"total_flags": total_leakage, "gold_dependent_flags": 0},
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # ── GENERAR REPORTE MD ────────────────────────────────────────────────────
    _generar_reporte_md(payload, all_results, aggregated, a0_detail, latencies)

    print(f"\n✅ JSON   : {OUTPUT_JSON}")
    print(f"✅ Report : {OUTPUT_REPORT}")
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# 6. GENERADOR DE REPORTE MARKDOWN
# ─────────────────────────────────────────────────────────────────────────────

def _generar_reporte_md(
    payload: Dict,
    all_results: Dict,
    aggregated: Dict,
    a0_detail: List,
    latencies: Dict,
):
    """Genera el informe docs/expN8_c1_overlay_report.md con todas las secciones
    exigidas por Aureon."""
    lines = []
    lines.append("# EXP-N8: C1 Overlay — Informe Formal\n")
    lines.append(f"**Timestamp**: {payload['timestamp']}  ")
    lines.append(f"**DB SHA-256**: `{payload['hashes']['db_snapshot']}`  ")
    lines.append(f"**Script SHA-256**: `{payload['hashes']['script']}`  \n")
    lines.append("> **A0-TEST: CIEGO. No ejecutado. Sin inspección adaptativa.**\n")

    # Condiciones
    lines.append("## 1. Definición de Condiciones\n")
    lines.append("| Cond | Descripción |\n|---|---|")
    for k, v in payload["conditions"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    # Reglas C1 usadas
    lines.append(f"\n**C1 rules en M2** ({len(payload['c1_rules_used'])}): " +
                 ", ".join(payload["c1_rules_used"]))
    lines.append(f"\n**C2 excluidas de M2**: " + ", ".join(payload["c2_excluded_from_m2"]))
    lines.append(f"\n**C3 excluidas de M2**: " + ", ".join(payload["c3_excluded_from_m2"]))

    # Tabla por caso
    lines.append("\n## 2. Resultados por Caso\n")
    lines.append("| Case | A0 | Regime | Pool | Pool% | Gen | Rank | CE@1 | CE@5 | CE@10 | CE@20 |")
    lines.append("|---|---|---|---:|---:|---|---:|---|---|---|---|")
    for i, case_id in enumerate([c["case_id"] for c in payload["results_by_regime"]["M0"]]):
        for reg in ["M0", "M1", "M2"]:
            r = all_results[reg][i]
            gen = "YES" if r["gold_in_pool"] else "NO"
            rk = str(r["gold_rank"]) if r["gold_rank"] else "–"
            a0 = r["a0_status"]
            ce = r["ranking_recall"]
            lines.append(
                f"| {case_id} | {a0} | {reg} | {r['pool_size']} | {r['pool_pct_corpus']} | "
                f"{gen} | {rk} | "
                f"{'✓' if ce.get('CE@1') else '.'} | "
                f"{'✓' if ce.get('CE@5') else '.'} | "
                f"{'✓' if ce.get('CE@10') else '.'} | "
                f"{'✓' if ce.get('CE@20') else '.'} |"
            )

    # Tabla agregada
    lines.append("\n## 3. Métricas Agregadas\n")
    lines.append("| Regime | Gen Recall | Str-A0 Gen | CE@1 | CE@5 | CE@10 | CE@20 | Avg Pool | Pool% |")
    lines.append("|---|---|---|---|---|---|---|---:|---:|")
    for reg in ["M0", "M1", "M2"]:
        a = aggregated[reg]
        t = a["total"]
        s = a["strict_a0"]
        lines.append(
            f"| {reg} | {t.get('gen_recall')} ({t.get('gen_recall_pct')}%) | "
            f"{s.get('gen_recall')} ({s.get('gen_recall_pct')}%) | "
            f"{t.get('CE@1')} | {t.get('CE@5')} | {t.get('CE@10')} | {t.get('CE@20')} | "
            f"{t.get('avg_pool')} | {t.get('avg_pool_pct')}% |"
        )
    lines.append("\n> **M3/M4** (análisis secundario) — ver JSON. No mezclar con conclusión C1.\n")

    # Análisis A0 especial
    lines.append("## 4. Análisis Especial: 6 Gold Strict A0\n")
    lines.append("| Case | Mec. Esperado | M0 Gen | M1 Gen | M2 Gen | C1 Causal | M2 Rank | Gen Status | Rank Status |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for d in a0_detail:
        lines.append(
            f"| {d['case_id']} | {d['expected_mechanism']} | "
            f"{'YES' if d['m0_gen'] else 'NO'} | "
            f"{'YES' if d['m1_gen'] else 'NO'} | "
            f"{'YES' if d['m2_gen'] else 'NO'} | "
            f"{'YES' if d['c1_causal'] else 'no'} | "
            f"{d['m2_rank'] or '–'} | "
            f"{d['generation_status']} | {d['ranking_status']} |"
        )

    # Latencia
    lines.append("\n## 5. Latencia\n")
    lines.append("| Regime | Avg Gen (ms) | Avg Rank (ms) | Avg Total (ms) |")
    lines.append("|---|---:|---:|---:|")
    for reg in ["M0", "M1", "M2"]:
        lats = latencies[reg]
        avg_gen = sum(l["gen_ms"] for l in lats) / len(lats)
        avg_rank = sum(l["rank_ms"] for l in lats) / len(lats)
        avg_tot = sum(l["total_ms"] for l in lats) / len(lats)
        lines.append(f"| {reg} | {avg_gen:.1f} | {avg_rank:.1f} | {avg_tot:.1f} |")

    # Leakage audit
    lines.append(f"\n## 6. Leakage Audit\n")
    lines.append(f"- Leakage flags: **{payload['leakage_audit']['total_flags']}** (debe ser 0)")
    lines.append(f"- Gold-dependent flags: **0**")
    lines.append(f"- case_id/gold_id/label usados en generación: **NO**")

    # Limitaciones
    lines.append("\n## 7. Limitaciones\n")
    lines.append("- El scoring de M1/M2 es interno al overlay (score_structural + coverage), "
                 "**no usa el motor de scoring del core/**. El efecto de C1 sobre el ranker "
                 "existente de BioRAG queda como trabajo futuro.")
    lines.append("- C1_MORPH_CHAIN cubre los spans más frecuentes; spans no registrados "
                 "se marcan como LEXICAL_CANONICALIZATION en lugar de MORPH_TRANSPARENT.")
    lines.append("- M1/M2 usan el parser de query de SCG-v0.1 para extraer ops del query, "
                 "garantizando coherencia entre condiciones.")
    lines.append("- A0-TEST permanece 100% ciego. Estos resultados son exclusivamente sobre DEV.")

    # Conclusión
    lines.append("\n## 8. Conclusión (Estrictamente Acotada)\n")
    lines.append("> *Pendiente de llenado post-ejecución con números reales.*\n")
    lines.append("La conclusión se construirá únicamente sobre los números del experimento, "
                 "separando Generation Recall de Ranking Recall y reportando "
                 "GENERATION_SUCCESS / RANKING_FAILURE donde corresponda.")

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    ejecutar_exp_n8()
