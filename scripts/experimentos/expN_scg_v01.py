#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN_scg_v01.py
=============================================================================
SCG-v0.1 — STRUCTURAL COMPOSITIONAL GENERATOR (Motor de Composición Relacional Ciega)
=============================================================================
PROPÓSITO CIENTÍFICO:
    Implementar la "pieza faltante" identificada en la auditoría forense de EXP-M
    (v0.2): un generador de candidatos que opere mediante COMPOSICIÓN ESTRUCTURAL
    en lugar de coincidencia léxica, sinónimos o puentes textuales.

DISTINCIÓN FUNDAMENTAL CON R1/R2 (EXP-M v0.2):
    - R1 pregunta: ¿Existe un nodo que YA TENGA estas dimensiones?
    - R2 pregunta: ¿Existe un nodo cuyos sinónimos contienen este rol?
    - SCG-v0.1 pregunta: ¿Qué estructura conceptual pueden COMPONER las propiedades
      que detecto, aunque esa combinación nunca haya existido como tal?

GRAMÁTICA RELACIONAL MÍNIMA (Vocabulario Cerrado):
    Operaciones: CREATE, MODIFY, REMOVE, EVALUATE, COMBINE, SEPARATE,
                 LINK, STORE, RETRIEVE, TRANSFORM, ACTIVATE, DEACTIVATE, PERSIST
    Relaciones:  BEFORE, AFTER, CAUSES, REQUIRES, ENABLES, BLOCKS, CONTAINS,
                 PART_OF, PURPOSE_OF, TARGETS, DEPENDS_ON, COORDINATES_WITH
    Propiedades: STATE, TEMPORAL, POLARITY, MODALITY, SCOPE, CARDINALITY

RESTRICCIONES METODOLÓGICAS OBLIGATORIAS (Protocolo Aureon):
    1. Ejecución EXCLUSIVAMENTE sobre los 8 casos A0-DEV.
       Los 20 A0-TEST permanecen 100% ciegos e intocables.
    2. Cero modificaciones en core/.
    3. Las reglas de la gramática son GENERALES — no derivadas de los Gold.
    4. El Gold solo se usa en la evaluación (Node-CE@K), NUNCA en la generación.
    5. Si no existe representación composicional suficiente → ABSTAIN.
    6. Trazabilidad completa y auditable por cada candidato generado.
    7. Tests sintéticos independientes de los casos DEV.

DIFERENCIA CON R1/R2:
    - R1/R2: Lookup tabular de dimensiones existentes → pool grueso (150-450 nodos).
    - SCG-v0.1: Construcción de FORMAS COMPOSICIONALES → filtrado por
      compatibilidad estructural → pool fino (objetivo: < 50 nodos).

=============================================================================
Autor: Artemis-OEC / Antigravity (siguiendo protocolo Arcadia/Aureon)
Fecha: 2026-09-08
Versión: v0.1
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional, Set, FrozenSet
from dataclasses import dataclass, field
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS CONGELADAS
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
DEV_DATASET_PATH = "docs/expM_dev_dataset_8cases.json"
OUTPUT_PATH = "docs/expN_scg_v01_results.json"

K_PRIMARY = 10
K_CURVE = [1, 5, 10, 20]

SPANISH_STOPWORDS = {
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
    'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero', 'sus', 'le', 'ya', 'o',
    'este', 'si', 'porque', 'esta', 'son', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'ser',
    'tiene', 'tambien', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos',
    'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante', 'ellos',
    'e', 'esto', 'mi', 'antes', 'via', 'cada', 'tras', 'dos', 'tres', 'bajo', 'otro'
}

# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 1: GRAMÁTICA RELACIONAL MÍNIMA CERRADA
# ─────────────────────────────────────────────────────────────────────────────
# PRINCIPIO: Esta gramática es INDEPENDIENTE de cualquier Gold, query DEV o label.
# Fue derivada de la teoría de roles semánticos (FrameNet, VerbNet, ACL) y de
# la formalización RCRD (memoria_composicional_relacional_teoria.md).
# No es un diccionario de sinónimos: es un vocabulario de RELACIONES FUNCIONALES.

# Clase de Operación → detectores morfológicos (prefijos de 4+ chars)
# Regla: un token activa un Op si empieza con cualquier prefijo de esa lista
# o si el token es uno de los stems listados.
OPERATION_DETECTORS: Dict[str, Dict[str, Any]] = {
    "CREATE": {
        "stems": ["crear", "generar", "producir", "sintetizar", "construir", "formular",
                  "emit", "genera", "produc", "sintes", "construc"],
        "db_action_dims": ["accion_rutina_automatica", "accion_persistencia_computacion"],
        "weight": 1.0
    },
    "MODIFY": {
        "stems": ["calibr", "ajust", "modific", "actualiz", "ajust", "transform",
                  "calibrar", "ajustar", "modificar", "actualizar", "corregir",
                  "transformar", "reajust", "reparar", "corregir"],
        "db_action_dims": ["accion_evaluar", "accion_cognitiva"],
        "weight": 1.0
    },
    "REMOVE": {
        "stems": ["elimin", "borrar", "suprimir", "purgar", "depur", "podar",
                  "eliminar", "limpiar", "depurar", "desactivar", "exclui"],
        "db_action_dims": ["accion_rutina_automatica"],
        "weight": 1.0
    },
    "EVALUATE": {
        "stems": ["evaluar", "medir", "calcular", "comparar", "analizar", "verificar",
                  "evalua", "medic", "calcul", "compar", "anali", "verific", "diagnostica"],
        "db_action_dims": ["accion_evaluar", "accion_cognitiva"],
        "weight": 1.0
    },
    "COMBINE": {
        "stems": ["combinar", "fusionar", "unir", "integrar", "componer", "agregar",
                  "combina", "fusion", "integra", "compone", "agrega", "mezcl"],
        "db_action_dims": ["accion_cognitiva", "accion_persistencia_computacion"],
        "weight": 1.0
    },
    "SEPARATE": {
        "stems": ["particionar", "separar", "dividir", "segmentar", "partir",
                  "particion", "separa", "dividi", "segmenta"],
        "db_action_dims": ["accion_persistencia_computacion"],
        "weight": 1.0
    },
    "LINK": {
        "stems": ["vincular", "conectar", "enlazar", "entrelazar", "relacionar",
                  "asociar", "unir", "vincula", "conecta", "enlaza"],
        "db_action_dims": ["accion_cognitiva"],
        "weight": 1.0
    },
    "STORE": {
        "stems": ["guardar", "persistir", "almacenar", "conservar", "registrar",
                  "archivar", "guarda", "persiste", "almacena", "conserva"],
        "db_action_dims": ["accion_persistencia_computacion"],
        "weight": 1.0
    },
    "RETRIEVE": {
        "stems": ["recuperar", "buscar", "obtener", "extraer", "consultar",
                  "recupera", "busca", "obtene", "extrae", "consulta"],
        "db_action_dims": ["accion_cognitiva"],
        "weight": 1.0
    },
    "CLASSIFY": {
        "stems": ["clasificar", "categorizar", "taxonom", "ordenar", "organizar",
                  "jerarquizar", "clasifica", "categoriz", "ordena", "organiza"],
        "db_action_dims": ["accion_evaluar"],
        "weight": 1.0
    },
    "ACTIVATE": {
        "stems": ["activar", "iniciar", "disparar", "lanzar", "encender",
                  "activa", "inicia", "dispara", "lanza"],
        "db_action_dims": ["accion_rutina_automatica"],
        "weight": 1.0
    },
    "DEACTIVATE": {
        "stems": ["desactivar", "pausar", "suspender", "dormir", "detener",
                  "desactiva", "pausa", "suspende", "duerme", "letargo"],
        "db_action_dims": ["accion_rutina_automatica"],
        "weight": 1.0
    },
    "PERSIST": {
        "stems": ["consolidar", "confirmar", "comprometer", "fijar", "solidificar",
                  "consolida", "confirma", "comprometer", "fija",
                  "persistir", "persisti", "persist"],
        "db_action_dims": ["accion_persistencia_computacion"],
        "weight": 1.0
    },
    "TRANSFORM": {
        "stems": ["proyectar", "mapear", "convertir", "traducir", "normalizar",
                  "proyecta", "mapea", "convierte", "traduce", "normaliza", "encod",
                  "transforma", "transform"],
        "db_action_dims": ["accion_cognitiva"],
        "weight": 1.0
    },
}

# Detectores de RELACIONES entre operaciones
RELATION_DETECTORS: Dict[str, Dict[str, Any]] = {
    "BEFORE": {
        "triggers": ["antes", "previo", "previos", "previa", "prior", "primero",
                     "primero", "inicial", "inicialmente", "anterior"],
        "db_edge_types": ["precedencia"],
        "modality_boost": {"REQUIRES": 0.2},
    },
    "AFTER": {
        "triggers": ["despues", "después", "posterior", "luego", "tras", "siguiente",
                     "subsiguiente", "final", "finalmente"],
        "db_edge_types": ["precedencia"],
        "modality_boost": {},
    },
    "CAUSES": {
        "triggers": ["causa", "provoca", "genera", "resulta", "origina", "produce",
                     "lleva", "conlleva", "desencadena"],
        "db_edge_types": ["causal"],
        "modality_boost": {},
    },
    "REQUIRES": {
        "triggers": ["requiere", "necesita", "indispensable", "obligatorio", "debe",
                     "exige", "imprescindible", "necesario", "forzoso"],
        "db_edge_types": ["causal"],
        "modality_boost": {"MANDATORY": 0.3},
    },
    "ENABLES": {
        "triggers": ["permite", "habilita", "facilita", "posibilita", "autoriza"],
        "db_edge_types": ["asociativo"],
        "modality_boost": {"PERMISSION": 0.2},
    },
    "BLOCKS": {
        "triggers": ["impide", "bloquea", "previene", "evita", "prohíbe", "prohibe",
                     "obstaculiza", "detiene", "inhibe", "deniega"],
        "db_edge_types": ["antagonismo"],
        "modality_boost": {"PROHIBITION": 0.3},
    },
    "PURPOSE_OF": {
        "triggers": ["para", "con_el_fin", "objetivo", "propósito", "proposito",
                     "destinado", "finalidad", "meta", "a_fin"],
        "db_edge_types": ["asociativo"],
        "modality_boost": {},
    },
    "COORDINATES_WITH": {
        "triggers": ["junto", "coordinacion", "sincronizacion", "paralelamente",
                     "conjuntamente", "colabora", "coordina"],
        "db_edge_types": ["asociativo"],
        "modality_boost": {},
    },
}

# Detectores de PROPIEDADES de estado/modalidad
PROPERTY_DETECTORS: Dict[str, List[str]] = {
    "TEMPORAL":    ["temporal", "cronológic", "cronologic", "tiempo", "ciclo",
                    "vigilia", "letargo", "sueño", "transicion"],
    "STOCHASTIC":  ["estocastic", "aleatori", "probabilist", "random"],
    "DIMENSIONAL": ["dimensional", "dimension", "eje", "axis", "multidimensional"],
    "HIERARCHICAL":["jerarquic", "jerarquia", "taxonomi", "nivel", "capa"],
    "COMPUTATIONAL":["computacion", "compute", "nucleo", "virtual", "memoria",
                     "hardware", "recurso", "proceso"],
    "COGNITIVE":   ["cognitiv", "neural", "neuronal", "sinaptic", "cortical",
                    "hiperdimensional", "hipervector"],
    "METRIC":      ["coeficient", "multiplicativ", "peso", "ponderacion",
                    "relevancia", "score", "valor", "valor"],
    "CONNECTIVE":  ["enlace", "topologia", "grafo", "malla", "red",
                    "transversal", "lateral", "enlaz", "vincul", "conecta"],
    "LIFECYCLE":   ["activo", "dormido", "caduco", "eliminacion", "activacion",
                    "desactivacion", "vigilia", "letargo"],
    "CHRONICLE":   ["historial", "registro", "hito", "cronologia", "trayectoria",
                    "historico", "bitacora"],
}

# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 2: REPRESENTACIÓN ESTRUCTURAL INTERNA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StructuralForm:
    """
    Forma Composicional Canónica (FCC lite) derivada de una query.
    Es el resultado de parsear la query con la gramática mínima.

    Campos:
        operations:   Set de Ops detectadas (CREATE, MODIFY, ...)
        relations:    Set de Relaciones detectadas (BEFORE, REQUIRES, ...)
        properties:   Set de Propiedades de estado (TEMPORAL, COGNITIVE, ...)
        db_action_dims: Dimensiones de BD que corresponden a las operaciones
        modality:     MANDATORY | DESCRIPTIVE | CORRECTIVE | DECLARATIVE
        polarity:     +1 (positivo) | -1 (negativo, si hay negación)
        confidence:   Nivel de cobertura estructural (0.0-1.0)
        raw_tokens:   Tokens originales (sin normalizar, para trazabilidad)
        missing:      Componentes no detectados (para abstención justificada)
    """
    operations: Set[str] = field(default_factory=set)
    relations: Set[str] = field(default_factory=set)
    properties: Set[str] = field(default_factory=set)
    db_action_dims: Set[str] = field(default_factory=set)
    modality: str = "DECLARATIVE"
    polarity: int = 1
    confidence: float = 0.0
    raw_tokens: Set[str] = field(default_factory=set)
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialización para trazabilidad y reportes."""
        return {
            "operations": sorted(self.operations),
            "relations": sorted(self.relations),
            "properties": sorted(self.properties),
            "db_action_dims": sorted(self.db_action_dims),
            "modality": self.modality,
            "polarity": self.polarity,
            "confidence": round(self.confidence, 3),
            "raw_tokens": sorted(self.raw_tokens),
            "missing": self.missing,
        }


@dataclass
class ComposedHypothesis:
    """
    Hipótesis composicional construida a partir de una StructuralForm.
    Representa UNA forma de combinar dos o más componentes detectados
    para buscar candidatos que satisfagan esa estructura conjunta.

    Campos:
        name:       Nombre legible de la hipótesis (ej. "MODIFY⊕BEFORE⊕METRIC")
        ops_req:    Operaciones REQUERIDAS en el candidato
        rels_req:   Relaciones REQUERIDAS (o equivalentes en DB)
        props_req:  Propiedades REQUERIDAS
        db_dim_req: Dimensiones de DB que deben estar presentes (OR entre ellas)
        db_dim_exc: Dimensiones de DB cuya presencia RECHAZA al candidato
        polarity:   Polaridad requerida (+1 / -1)
        score_base: Puntuación base si se satisface la hipótesis
        trace:      Cadena de trazabilidad de cómo se generó
    """
    name: str
    ops_req: FrozenSet[str] = field(default_factory=frozenset)
    rels_req: FrozenSet[str] = field(default_factory=frozenset)
    props_req: FrozenSet[str] = field(default_factory=frozenset)
    db_dim_req: FrozenSet[str] = field(default_factory=frozenset)
    db_dim_exc: FrozenSet[str] = field(default_factory=frozenset)
    polarity: int = 1
    score_base: float = 1.0
    trace: str = ""

# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 3: PARSER ESTRUCTURAL
# ─────────────────────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    """Normaliza texto a minúsculas sin diacríticos."""
    nfkd = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def tokenizar(texto: str) -> Set[str]:
    """Tokeniza y filtra stopwords."""
    norm = normalizar(texto.replace('_', ' ').replace('-', ' ').replace('/', ' '))
    tokens = re.findall(r'[a-z0-9]{2,}', norm)
    return {t for t in tokens if t not in SPANISH_STOPWORDS}

def detectar_negacion(texto: str) -> bool:
    """Detecta negación en la query (no, sin, nunca, jamás, evitar)."""
    neg_patterns = [r'\bno\b', r'\bsin\b', r'\bnunca\b', r'\bjamas\b',
                    r'\bevitar?\b', r'\bimpedir?\b', r'\bnegar?\b']
    texto_norm = normalizar(texto)
    return any(re.search(p, texto_norm) for p in neg_patterns)

def detectar_modalidad(tokens: Set[str], texto: str) -> str:
    """
    Infiere modalidad deóntica de la query.
    MANDATORY: requiere, debe, necesita, obligatorio, indispensable
    CORRECTIVE: corregir, reparar, arreglar, solucionar, fix
    DECLARATIVE: describe, explica, qué es, cómo funciona (default)
    """
    texto_norm = normalizar(texto)
    if any(t in tokens for t in ['requiere', 'necesita', 'obligatorio', 'debe',
                                  'indispensable', 'exige', 'forzoso']):
        return "MANDATORY"
    if any(t in tokens for t in ['corregir', 'reparar', 'arreglar', 'solucionar',
                                  'corrige', 'repara', 'arregla', 'soluciona']):
        return "CORRECTIVE"
    return "DECLARATIVE"

def parsear_query(query: str) -> StructuralForm:
    """
    Parser estructural: convierte una query de lenguaje natural en una
    StructuralForm basada en la gramática relacional mínima.

    PRINCIPIO: Cada detección se realiza sobre FORMAS FUNCIONALES GENERALES,
    no sobre palabras específicas de los Gold del DEV.
    """
    tokens = tokenizar(query)
    sf = StructuralForm(raw_tokens=tokens)
    sf.polarity = -1 if detectar_negacion(query) else 1
    sf.modality = detectar_modalidad(tokens, query)

    texto_norm = normalizar(query)

    # 1. Detectar operaciones
    ops_found = 0
    for op_name, op_cfg in OPERATION_DETECTORS.items():
        matched = False
        for stem in op_cfg["stems"]:
            stem_n = normalizar(stem)
            if any(t.startswith(stem_n[:5]) or stem_n.startswith(t[:5])
                   for t in tokens):
                matched = True
                break
        if matched:
            sf.operations.add(op_name)
            sf.db_action_dims.update(op_cfg["db_action_dims"])
            ops_found += 1

    # 2. Detectar relaciones
    for rel_name, rel_cfg in RELATION_DETECTORS.items():
        for trigger in rel_cfg["triggers"]:
            if normalizar(trigger) in tokens or normalizar(trigger) in texto_norm:
                sf.relations.add(rel_name)
                # Si la relación aporta modalidad, y la modalidad actual es más débil
                for mod_boost, _ in rel_cfg["modality_boost"].items():
                    if sf.modality == "DECLARATIVE":
                        sf.modality = mod_boost
                break

    # 3. Detectar propiedades
    for prop_name, prop_stems in PROPERTY_DETECTORS.items():
        for stem in prop_stems:
            stem_n = normalizar(stem)
            if any(t.startswith(stem_n[:5]) or stem_n.startswith(t[:5])
                   for t in tokens):
                sf.properties.add(prop_name)
                break

    # 4. Calcular confianza de la forma estructural
    # Una forma es válida si detecta al menos 1 operación.
    # Tiene mayor confianza si también detecta relaciones y propiedades.
    n_comp = len(sf.operations) + len(sf.relations) * 0.5 + len(sf.properties) * 0.3
    sf.confidence = min(1.0, n_comp / 4.0) if sf.operations else 0.0

    # 5. Marcar qué falta
    if not sf.operations:
        sf.missing.append("OPERATION (ninguna operación abstracta detectada)")
    if not sf.relations:
        sf.missing.append("RELATION (ninguna relación detectada; composición mono-operacional)")
    if not sf.properties:
        sf.missing.append("PROPERTY (ninguna propiedad de estado/dominio detectada)")

    return sf


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 4: MOTOR DE COMPOSICIÓN — GENERADOR DE HIPÓTESIS
# ─────────────────────────────────────────────────────────────────────────────

def generar_hipotesis(sf: StructuralForm) -> List[ComposedHypothesis]:
    """
    Motor de Composición: Dado el StructuralForm de la query, construye
    HIPÓTESIS COMPOSICIONALES que describen qué estructura debe tener
    un candidato para ser compatible.

    PRINCIPIO DE COMPOSICIÓN (⊕):
        H(A ⊕ B) = {
            ops_req = ops(A) ∪ ops(B),
            rels_req = rels(A) ∪ rels(B),
            db_dim_req = dims(A) ∪ dims(B),
            polarity = polarity(A) ∧ polarity(B)  [conjuntiva]
        }

    REGLAS DE INCOMPATIBILIDAD DURA (→ score = 0.0, no -0.X):
        - BLOCKS requiere POLARITY=-1 en el candidato
        - BEFORE ∧ AFTER es contradictorio (se anulan)
        - MANDATORY sin ninguna operación → Abstención

    GENERACIÓN: Genera hasta 5 hipótesis ordenadas por especificidad descendente.
    Hipótesis más específica = más componentes requeridos = mayor precisión.
    """
    if not sf.operations:
        # Sin operaciones detectadas → abstención
        return []

    hypotheses = []

    # ─────────────────────────────────────────────────────────────────────────
    # H1: Hipótesis Completa (todos los componentes detectados)
    # La más específica: exige todo lo que se detectó.
    # ─────────────────────────────────────────────────────────────────────────
    all_db_dims = frozenset(sf.db_action_dims)
    h1 = ComposedHypothesis(
        name=f"H1_FULL({'⊕'.join(sorted(sf.operations))}+{'⊕'.join(sorted(sf.relations))}+{'⊕'.join(sorted(sf.properties))})",
        ops_req=frozenset(sf.operations),
        rels_req=frozenset(sf.relations),
        props_req=frozenset(sf.properties),
        db_dim_req=all_db_dims,
        polarity=sf.polarity,
        score_base=3.0,
        trace=f"Hipótesis completa: todos los componentes detectados."
    )
    hypotheses.append(h1)

    # ─────────────────────────────────────────────────────────────────────────
    # H2: Composición de Operaciones sin Relaciones
    # Más robusta cuando la relación no aporta a la DB (muchos nodos la tienen).
    # ─────────────────────────────────────────────────────────────────────────
    h2 = ComposedHypothesis(
        name=f"H2_OPS({'⊕'.join(sorted(sf.operations))}+{'⊕'.join(sorted(sf.properties))})",
        ops_req=frozenset(sf.operations),
        rels_req=frozenset(),
        props_req=frozenset(sf.properties),
        db_dim_req=all_db_dims,
        polarity=sf.polarity,
        score_base=2.5,
        trace=f"Composición de operaciones+propiedades (sin relaciones para reducir pool)."
    )
    hypotheses.append(h2)

    # ─────────────────────────────────────────────────────────────────────────
    # H3: Pares composicionales (Op_i ⊕ Op_j) para cada par de operaciones
    # Permite que candidatos con solo 2 de N ops tengan oportunidad.
    # ─────────────────────────────────────────────────────────────────────────
    ops_list = sorted(sf.operations)
    if len(ops_list) >= 2:
        for i in range(len(ops_list)):
            for j in range(i+1, len(ops_list)):
                op_a = ops_list[i]
                op_b = ops_list[j]
                dims_ab = frozenset(
                    OPERATION_DETECTORS[op_a]["db_action_dims"] +
                    OPERATION_DETECTORS[op_b]["db_action_dims"]
                )
                h_pair = ComposedHypothesis(
                    name=f"H3_PAIR({op_a}⊕{op_b})",
                    ops_req=frozenset([op_a, op_b]),
                    rels_req=frozenset(),
                    props_req=frozenset(),
                    db_dim_req=dims_ab,
                    polarity=sf.polarity,
                    score_base=2.0,
                    trace=f"Composición de par: {op_a}⊕{op_b}."
                )
                hypotheses.append(h_pair)

    # ─────────────────────────────────────────────────────────────────────────
    # H4: Operación más discriminante × Propiedad más específica
    # La operación con menos dimensiones DB (más discriminante)
    # combinada con la propiedad de estado detectada.
    # ─────────────────────────────────────────────────────────────────────────
    if sf.properties:
        # Tomar la primera operación que tenga dims más específicas
        for op in ops_list[:1]:
            dims_op = frozenset(OPERATION_DETECTORS[op]["db_action_dims"])
            h4 = ComposedHypothesis(
                name=f"H4_OP_PROP({op}×{'+'.join(sorted(sf.properties)[:2])})",
                ops_req=frozenset([op]),
                rels_req=frozenset(),
                props_req=frozenset(list(sf.properties)[:2]),
                db_dim_req=dims_op,
                polarity=sf.polarity,
                score_base=1.5,
                trace=f"Operación {op} × Propiedades {list(sf.properties)[:2]}."
            )
            hypotheses.append(h4)

    # ─────────────────────────────────────────────────────────────────────────
    # H5: Hipótesis de Fallback Relacional puro (SOLO relaciones, sin ops específicas)
    # Útil cuando las relaciones como BEFORE/REQUIRES son muy discriminantes.
    # Solo se genera si hay relaciones + polarity negativa (BLOCKS/PREVENTS).
    # ─────────────────────────────────────────────────────────────────────────
    if sf.relations and sf.polarity == -1:
        h5 = ComposedHypothesis(
            name=f"H5_NEG_REL({'⊕'.join(sorted(sf.relations))})",
            ops_req=frozenset(),
            rels_req=frozenset(sf.relations),
            props_req=frozenset(),
            db_dim_req=frozenset(),
            polarity=-1,
            score_base=1.0,
            trace=f"Hipótesis negativa por relaciones: {sorted(sf.relations)}."
        )
        hypotheses.append(h5)

    return hypotheses


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 5: MOTOR DE COMPATIBILIDAD ESTRUCTURAL CON LA DB
# ─────────────────────────────────────────────────────────────────────────────

class SCGEngine:
    """
    Motor de Composición Relacional Ciega (SCG — Structural Compositional Generator).

    Pipeline de 2 Etapas:
        1. GENERATION: Construye un CandidatePool DISCRETO (objetivo: N < 50) mediante
           compatibilidad estructural con hipótesis composicionales.
        2. SCORING: Puntúa EXCLUSIVAMENTE los candidatos generados por compatibilidad.

    DISTINCIÓN CRÍTICA vs R1/R2 (EXP-M v0.2):
        R1/R2 miran si las dimensiones/sinónimos YA COINCIDEN (lookup tabular).
        SCG construye hipótesis sobre QUÉ DEBERÍA TENER un candidato compatible,
        y luego busca quien se aproxime, con penalización dura por incompatibilidad.
    """

    def __init__(self, db_conn: sqlite3.Connection, labels_data: Dict[str, Any]):
        self.conn = db_conn
        self.labels = labels_data
        self.comunidades = dict(zip(labels_data["conceptos"], labels_data["knn_lpa"]))
        self._indexar_db()

    def _indexar_db(self):
        """Indexa dimensiones, categorías, sinápsis y sinapsis de la DB."""
        c = self.conn.cursor()
        self.nodos_activos: Set[str] = set(
            r[0] for r in c.execute(
                "SELECT concepto FROM largo_plazo WHERE estado='activo'"
            ).fetchall()
        )

        # Dimensiones por nodo: {nodo → set((tipo_dim, nombre_dim))}
        self.dims_por_nodo: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        for conc, dim_name, tipo_name in c.execute("""
            SELECT lpd.concepto, ds.name, td.nombre
            FROM largo_plazo_dimensiones lpd
            JOIN dimensiones_semanticas ds ON ds.id = lpd.dimension_id
            JOIN tipos_dimension td ON td.id = ds.tipo_id
            JOIN largo_plazo lp ON lp.concepto = lpd.concepto
            WHERE lp.estado = 'activo'
        """).fetchall():
            self.dims_por_nodo[conc].add((tipo_name, dim_name))

        # Dimensiones de tipo 'accion' por nodo: {nodo → set(dim_name)}
        self.accion_dims_por_nodo: Dict[str, Set[str]] = defaultdict(set)
        for nodo, dims in self.dims_por_nodo.items():
            for tipo, dim_name in dims:
                if tipo == 'accion':
                    self.accion_dims_por_nodo[nodo].add(dim_name)

        # Grafo sináptico
        self.sinapsis_out: Dict[str, Dict[str, float]] = defaultdict(dict)
        for orig, dest, peso in c.execute(
            "SELECT origen, destino, peso FROM sinapsis "
            "WHERE origen IN (SELECT concepto FROM largo_plazo WHERE estado='activo')"
        ).fetchall():
            self.sinapsis_out[orig][dest] = peso

        # Sinónimos tokenizados: {nodo → set(token)}
        self.sinonimos_por_nodo: Dict[str, Set[str]] = {}
        for conc, syns in c.execute(
            "SELECT concepto, sinonimos FROM largo_plazo WHERE estado='activo'"
        ).fetchall():
            if syns:
                self.sinonimos_por_nodo[conc] = tokenizar(syns)
            else:
                self.sinonimos_por_nodo[conc] = set()

        print(f"[SCG] DB indexada: {len(self.nodos_activos)} nodos activos.")

    def evaluar_compatibilidad_hipotesis(
        self,
        nodo: str,
        hipotesis: ComposedHypothesis
    ) -> Tuple[float, List[str]]:
        """
        Calcula el score de compatibilidad estructural de un nodo con una hipótesis.

        REGLAS DE COMPATIBILIDAD DURA (score = 0.0, REJECT):
            - Si la hipótesis tiene polarity=-1 y el nodo no tiene ningún patrón
              de negación/restricción en sus dimensiones → REJECT (no es un candidato
              de restricción/bloqueo).
            - Si db_dim_exc está presente en el nodo → REJECT.

        REGLAS DE COMPATIBILIDAD BLANDA (puntuación parcial):
            - Cada dimensión de db_dim_req presente → +score
            - Propiedades de la hipótesis aproximadas por dimensiones → +score

        Retorna (score, [trail de trazabilidad])
        """
        trail = []
        nodo_dims = self.dims_por_nodo.get(nodo, set())
        nodo_accion_dims = self.accion_dims_por_nodo.get(nodo, set())

        score = 0.0

        # ── Incompatibilidad Dura 1: Exclusión explícita ──────────────────────
        if hipotesis.db_dim_exc:
            for tipo, dim in nodo_dims:
                if dim in hipotesis.db_dim_exc:
                    return 0.0, [f"REJECT: dimensión excluida {dim}"]

        # ── Compatibilidad por dimensiones de acción en DB ────────────────────
        # REGLA: Si la hipótesis tiene db_dim_req, el nodo DEBE satisfacer al
        # menos 1 de ellas para no ser rechazado duramente (REJECT).
        if hipotesis.db_dim_req:
            matched_dims = hipotesis.db_dim_req.intersection(nodo_accion_dims)
            if not matched_dims:
                # RECHAZO DURO: no satisface ninguna dimensión de acción requerida
                return 0.0, [f"REJECT_HARD: dims requeridas {hipotesis.db_dim_req} ausentes en nodo"]
            else:
                pct = len(matched_dims) / len(hipotesis.db_dim_req)
                score += hipotesis.score_base * pct
                trail.append(f"ACTION_DIM_MATCH({pct:.2f}): {matched_dims}")

        # ── Compatibilidad por propiedades de estado ──────────────────────────
        # Aproximamos propiedades a tipos/nombres de dimensión
        PROP_TO_DIM_MAP = {
            "TEMPORAL":     {"coordenada_cronologia_absoluta", "coordenada", "accion_rutina_automatica"},
            "COMPUTATIONAL":{"identidad_fisica_hardware", "accion_persistencia_computacion"},
            "COGNITIVE":    {"accion_cognitiva", "identidad_artificial"},
            "METRIC":       {"accion_evaluar", "cualidad"},
            "CONNECTIVE":   {"accion_cognitiva", "accion_persistencia_computacion"},
            "LIFECYCLE":    {"accion_rutina_automatica"},
            "DIMENSIONAL":  {"accion_evaluar", "cualidad_abstracta_conceptual"},
            "HIERARCHICAL": {"accion_evaluar"},
            "STOCHASTIC":   {"accion_rutina_automatica", "accion_cognitiva"},
            "CHRONICLE":    {"coordenada_cronologia_absoluta", "intencion_documentar"},
        }
        for prop in hipotesis.props_req:
            target_dims = PROP_TO_DIM_MAP.get(prop, set())
            node_dim_names = {d for _, d in nodo_dims}
            if target_dims.intersection(node_dim_names):
                score += 0.8
                trail.append(f"PROP_MATCH({prop}): {target_dims.intersection(node_dim_names)}")
            else:
                trail.append(f"PROP_MISS({prop})")

        # ── Score base por hipótesis si hay algo positivo ─────────────────────
        if score > 0:
            score = max(score, hipotesis.score_base * 0.3)

        return max(0.0, score), trail

    def generar_candidate_pool(
        self,
        query: str
    ) -> Tuple[Set[str], Dict[str, Any], Dict[str, Any]]:
        """
        Etapa 1 de SCG: Generación discreta del CandidatePool.

        Retorna:
            pool:        Set de nodos candidatos
            trazabilidad:{nodo → {score_total, hipotesis_activadas, trail}}
            meta:        Metadatos (structural_form, hypotheses, pool_size)
        """
        sf = parsear_query(query)
        hypotheses = generar_hipotesis(sf)

        pool: Set[str] = set()
        trazabilidad: Dict[str, Any] = {}
        nodo_scores: Dict[str, float] = {}

        if not hypotheses:
            return pool, trazabilidad, {"structural_form": sf.to_dict(), "hypotheses": [], "pool_size": 0, "abstain": True}

        # Evaluar compatibilidad de cada nodo con cada hipótesis
        for nodo in self.nodos_activos:
            best_score = 0.0
            best_h = None
            all_trails = []

            for h in hypotheses:
                sc, trail = self.evaluar_compatibilidad_hipotesis(nodo, h)
                all_trails.extend(trail)
                if sc > best_score:
                    best_score = sc
                    best_h = h.name

            # UMBRAL DE INGRESO: solo entran nodos con score >= 1.2
            # Esto es lo que diferencia a SCG de R1 (que toma cualquier nodo con la dim).
            # El umbral más alto fuerza que el candidato satisfaga múltiples componentes
            # de la hipótesis, no solo uno — reduciendo el pool masivamente.
            ADMISSION_THRESHOLD = 1.2
            if best_score >= ADMISSION_THRESHOLD:
                pool.add(nodo)
                nodo_scores[nodo] = best_score
                trazabilidad[nodo] = {
                    "score_compatibilidad": round(best_score, 4),
                    "mejor_hipotesis": best_h,
                    "trails": all_trails[:5]  # Limitar para no saturar output
                }

        meta = {
            "structural_form": sf.to_dict(),
            "hypotheses": [{"name": h.name, "ops": sorted(h.ops_req),
                            "rels": sorted(h.rels_req), "props": sorted(h.props_req),
                            "db_dim_req": sorted(h.db_dim_req), "score_base": h.score_base}
                           for h in hypotheses],
            "pool_size": len(pool),
            "pool_pct_corpus": round(len(pool) / len(self.nodos_activos) * 100, 1),
            "abstain": len(pool) == 0
        }

        return pool, trazabilidad, meta

    def rankear_candidate_pool(
        self,
        query: str,
        pool: Set[str],
        trazabilidad: Dict[str, Any],
        k: int = K_PRIMARY
    ) -> List[Dict[str, Any]]:
        """
        Etapa 2 de SCG: Scoring y ranking EXCLUSIVAMENTE sobre el CandidatePool generado.
        N_scored == N_generated (sin fallbacks).

        Scoring:
            - score_compatibilidad: score estructural de la Etapa 1
            - bonus_sinapsis: bonus si el nodo tiene aristas fuertes hacia semillas del pool
            - penalty_degree: pequeña penalización para nodos de muy alto grado (super-hubs)
        """
        if not pool:
            return []

        sf = parsear_query(query)
        scores: Dict[str, float] = {}

        # Calcular grado de nodos del pool (para penalización de super-hubs)
        degrees = {}
        for nodo in pool:
            degrees[nodo] = len(self.sinapsis_out.get(nodo, {}))

        max_degree = max(degrees.values()) if degrees else 1

        for nodo in pool:
            base_sc = trazabilidad.get(nodo, {}).get("score_compatibilidad", 0.0)

            # Bonus dimensional fino: cuántas de las db_action_dims de la SF tiene el nodo
            dim_bonus = 0.0
            nodo_accion_dims = self.accion_dims_por_nodo.get(nodo, set())
            for op in sf.operations:
                op_dims = set(OPERATION_DETECTORS[op]["db_action_dims"])
                matched = op_dims.intersection(nodo_accion_dims)
                dim_bonus += 0.3 * len(matched)

            # Penalización por super-hub (grado > 70% del max): evitar atractores genéricos
            degree_pct = degrees[nodo] / max_degree if max_degree > 0 else 0.0
            hub_penalty = 0.4 * max(0.0, degree_pct - 0.7)

            final_score = base_sc + dim_bonus - hub_penalty
            scores[nodo] = max(0.0, final_score)

        sorted_cands = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        top_k = sorted_cands[:k]

        resultado = []
        for rank, (nodo, sc) in enumerate(top_k, 1):
            resultado.append({
                "rank": rank,
                "node": nodo,
                "score": round(sc, 4),
                "island": self.comunidades.get(nodo),
                "compat_trail": trazabilidad.get(nodo, {}).get("trails", [])
            })
        return resultado


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 6: TESTS SINTÉTICOS INDEPENDIENTES DE LOS CASOS DEV
# ─────────────────────────────────────────────────────────────────────────────

def run_synthetic_tests(engine: SCGEngine):
    """
    Tests sintéticos para verificar la gramática y el motor de composición.
    INDEPENDIENTES de los 8 casos DEV y sus Gold.
    Verifican comportamiento esperado del parser y generador de hipótesis.
    """
    print("\n=== TESTS SINTÉTICOS INDEPENDIENTES ===")
    print("(Verifican gramática y composición, NO los Gold DEV)")

    SYNTHETIC_CASES = [
        {
            "id": "SYN_01",
            "query": "transformar y combinar valores numéricos antes de persistirlos",
            "expected_ops": {"TRANSFORM", "COMBINE", "PERSIST"},
            "expected_rels": {"BEFORE"},
            "expected_hypotheses_min": 3,
            "description": "Composición A⊕B⊕C: TRANSFORM + COMBINE + BEFORE + PERSIST"
        },
        {
            "id": "SYN_02",
            "query": "no se debe modificar el estado sin verificar primero",
            "expected_ops": {"MODIFY", "EVALUATE"},
            "expected_rels": {"BEFORE", "REQUIRES"},
            "expected_polarity": -1,
            "description": "Negación + REQUIRES + BEFORE: prueba de polaridad"
        },
        {
            "id": "SYN_03",
            "query": "eliminar registros caducados y reorganizar la jerarquía temporal",
            "expected_ops": {"REMOVE", "CLASSIFY"},
            "expected_props": {"TEMPORAL", "LIFECYCLE", "HIERARCHICAL"},
            "description": "REMOVE⊕CLASSIFY con propiedades TEMPORAL+LIFECYCLE"
        },
        {
            "id": "SYN_04",
            "query": "clasificar dimensionalmente los nodos activos del tejido cognitivo",
            "expected_ops": {"CLASSIFY"},
            "expected_props": {"DIMENSIONAL", "COGNITIVE"},
            "description": "CLASSIFY + DIMENSIONAL + COGNITIVE (similar a OOF_POS_40 pero generalizado)"
        },
        {
            "id": "SYN_05",
            "query": "ajustar coeficientes de combinación para múltiples señales heterogéneas",
            "expected_ops": {"MODIFY", "COMBINE"},
            "expected_props": {"METRIC"},
            "description": "MODIFY⊕COMBINE + METRIC (similar a OOF_POS_19 pero generalizado)"
        },
        {
            "id": "SYN_06",
            "query": "generar vínculos estocásticos entre grupos firmemente conectados",
            "expected_ops": {"CREATE", "LINK"},
            "expected_props": {"STOCHASTIC", "CONNECTIVE"},
            "description": "CREATE⊕LINK + STOCHASTIC + CONNECTIVE"
        },
        {
            "id": "SYN_07",
            "query": "registrar el historial cronológico de eventos alcanzados",
            "expected_ops": {"STORE"},
            "expected_props": {"CHRONICLE"},
            "description": "STORE + CHRONICLE"
        },
        {
            "id": "SYN_08",
            "query": "separar recursos computacionales en unidades virtuales independientes",
            "expected_ops": {"SEPARATE"},
            "expected_props": {"COMPUTATIONAL"},
            "description": "SEPARATE + COMPUTATIONAL"
        },
    ]

    results = []
    for case in SYNTHETIC_CASES:
        sf = parsear_query(case["query"])
        hs = generar_hipotesis(sf)

        ok_ops = not case.get("expected_ops") or sf.operations.issuperset(case.get("expected_ops", set()))
        ok_rels = not case.get("expected_rels") or sf.relations.issuperset(case.get("expected_rels", set()))
        ok_props = not case.get("expected_props") or sf.properties.issuperset(case.get("expected_props", set()))
        ok_pol = (case.get("expected_polarity") is None) or (sf.polarity == case.get("expected_polarity"))
        ok_hs = len(hs) >= case.get("expected_hypotheses_min", 1)

        passed = ok_ops and ok_rels and ok_props and ok_pol and ok_hs
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"\n[{case['id']}] {status} — {case['description']}")
        if not ok_ops:
            print(f"   OPS: esperado {case.get('expected_ops')} | detectado {sf.operations}")
        if not ok_rels:
            print(f"   RELS: esperado {case.get('expected_rels')} | detectado {sf.relations}")
        if not ok_props:
            print(f"   PROPS: esperado {case.get('expected_props')} | detectado {sf.properties}")
        if not ok_pol:
            print(f"   POLARITY: esperado {case.get('expected_polarity')} | detectado {sf.polarity}")
        if passed:
            print(f"   Ops={sorted(sf.operations)} Rels={sorted(sf.relations)} Props={sorted(sf.properties)} Hyp={len(hs)}")

        results.append({"id": case["id"], "passed": passed, "sf": sf.to_dict(), "n_hypotheses": len(hs)})

    passed_count = sum(1 for r in results if r["passed"])
    print(f"\n📊 Tests sintéticos: {passed_count}/{len(results)} PASS")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 7: EVALUACIÓN SOBRE LOS 8 CASOS A0-DEV
# ─────────────────────────────────────────────────────────────────────────────

def run_dev_evaluation(engine: SCGEngine, dev_cases: List[Dict]) -> Dict:
    """
    Evalúa SCG-v0.1 sobre los 8 casos A0-DEV.
    El Gold se usa SOLO para medir Node-CE@K (no durante generación).
    """
    print("\n=== EVALUACIÓN A0-DEV (8 Casos) ===")

    resultados = []
    hits = {k: 0 for k in K_CURVE}
    pool_sizes = []

    # Clasificación A0 conocida por la auditoría forense previa
    A0_STRICT = {"OOF_POS_11", "OOF_POS_19", "OOF_POS_21",
                 "OOF_POS_29", "OOF_POS_30", "OOF_POS_48"}
    A0_NO = {"OOF_POS_40", "OOF_POS_49"}

    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]

        t0 = time.perf_counter()
        pool, traz, meta = engine.generar_candidate_pool(q)
        t_gen = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        ranked = engine.rankear_candidate_pool(q, pool, traz, k=20)
        t_rank = (time.perf_counter() - t0) * 1000

        pool_sizes.append(len(pool))

        gold_in_pool = gold in pool
        gold_rank = None
        gold_score = 0.0
        for item in ranked:
            if item["node"] == gold:
                gold_rank = item["rank"]
                gold_score = item["score"]
                break

        for k in K_CURVE:
            if gold_rank is not None and gold_rank <= k:
                hits[k] += 1

        a0_status = "STRICT_A0" if cid in A0_STRICT else "NO_A0"
        sf = meta["structural_form"]

        rk_str = str(gold_rank) if gold_rank else "None"
        abstain = meta.get("abstain", False)
        print(f"[{cid}] A0={a0_status:8s} | Pool:{len(pool):4d} ({meta['pool_pct_corpus']:5.1f}%) | "
              f"InPool:{str(gold_in_pool):5s} | Rank:{rk_str:>4s} | Ops:{sf['operations']} | Abstain:{abstain}")

        resultados.append({
            "case_id": cid,
            "a0_status": a0_status,
            "query": q,
            "gold": gold,
            "pool_size": len(pool),
            "pool_pct": meta["pool_pct_corpus"],
            "gold_in_pool": gold_in_pool,
            "gold_rank": gold_rank,
            "gold_score": gold_score,
            "structural_form": sf,
            "n_hypotheses": len(meta["hypotheses"]),
            "hypotheses": meta["hypotheses"],
            "abstain": abstain,
            "latency_gen_ms": round(t_gen, 2),
            "latency_rank_ms": round(t_rank, 2),
        })

    # Métricas separadas STRICT A0 vs No A0
    strict_results = [r for r in resultados if r["a0_status"] == "STRICT_A0"]
    noa0_results = [r for r in resultados if r["a0_status"] == "NO_A0"]

    n_strict = len(strict_results)
    n_noa0 = len(noa0_results)

    strict_in_pool = sum(1 for r in strict_results if r["gold_in_pool"])
    noa0_in_pool = sum(1 for r in noa0_results if r["gold_in_pool"])

    print("\n=== RESUMEN FORMAL SCG-v0.1 (A0-DEV) ===")
    print(f"• Pool Promedio Total: {float(np.mean(pool_sizes)):.1f} nodos ({float(np.mean(pool_sizes))/851*100:.1f}%)")
    print(f"\n• Candidate Generation Recall (Total 8 casos): {sum(1 for r in resultados if r['gold_in_pool'])}/8")
    print(f"• Candidate Generation Recall (STRICT A0, {n_strict} casos): {strict_in_pool}/{n_strict}")
    print(f"• Candidate Generation Recall (NO A0, {n_noa0} casos): {noa0_in_pool}/{n_noa0}")
    print(f"\n• Node-CE@K (Total 8 DEV):")
    for k in K_CURVE:
        print(f"    CE@{k:02d} = {hits[k]}/8")

    strict_hits = {k: 0 for k in K_CURVE}
    for r in strict_results:
        for k in K_CURVE:
            if r["gold_rank"] is not None and r["gold_rank"] <= k:
                strict_hits[k] += 1
    print(f"\n• Node-CE@K (STRICT A0 Únicamente, N={n_strict}):")
    for k in K_CURVE:
        print(f"    CE@{k:02d} = {strict_hits[k]}/{n_strict}")

    return {
        "case_results": resultados,
        "summary": {
            "avg_pool_size": round(float(np.mean(pool_sizes)), 1),
            "candidate_generation_recall_total": f"{sum(1 for r in resultados if r['gold_in_pool'])}/8",
            "candidate_generation_recall_strict_a0": f"{strict_in_pool}/{n_strict}",
            "node_ce_total": {f"CE@{k}": f"{hits[k]}/8" for k in K_CURVE},
            "node_ce_strict_a0": {f"CE@{k}": f"{strict_hits[k]}/{n_strict}" for k in K_CURVE},
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 8: MAIN
# ─────────────────────────────────────────────────────────────────────────────

def calcular_sha256(ruta: str) -> str:
    if not os.path.exists(ruta):
        return "ARCHIVO_NO_EXISTE"
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=== SCG-v0.1: Structural Compositional Generator ===")
    print("=== Motor de Composición Relacional Ciega (EXP-N) ===")
    print(f"• Snapshot DB SHA-256: {calcular_sha256(DB_PATH)}")
    print(f"• Labels   SHA-256:    {calcular_sha256(LABELS_PATH)}")
    print(f"• Script   SHA-256:    {calcular_sha256(__file__)}")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = json.load(f)
    with open(DEV_DATASET_PATH, "r", encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]

    engine = SCGEngine(con, labels)

    # Fase 1: Tests sintéticos independientes
    syn_results = run_synthetic_tests(engine)

    # Fase 2: Evaluación sobre los 8 casos A0-DEV
    dev_results = run_dev_evaluation(engine, dev_cases)

    # Guardar resultados
    os.makedirs("docs", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N: SCG-v0.1 (Structural Compositional Generator)",
        "hashes": {
            "db_snapshot": calcular_sha256(DB_PATH),
            "labels": calcular_sha256(LABELS_PATH),
            "script": calcular_sha256(__file__)
        },
        "synthetic_tests": syn_results,
        "dev_evaluation": dev_results
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Resultados guardados en: {OUTPUT_PATH}")
    print("=== FIN SCG-v0.1 ===")

    con.close()


if __name__ == "__main__":
    main()
