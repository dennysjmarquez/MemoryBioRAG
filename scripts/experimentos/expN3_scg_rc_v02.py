#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN3_scg_rc_v02.py
=============================================================================
SCG-RC v0.2 — RELATIONAL COMPOSITION CONSTRAINT GENERATOR
=============================================================================
PROPÓSITO CIENTÍFICO (Protocolo Aureon):
    Evolucionar de conjuntos planos de características (OP ∧ PROP ∧ ROLE) a
    FIRMAS RELACIONALES ESTRUCTURADAS:
        OP(OBJECT(X), CONSTRAINT(Y), TARGET(Z), RELATION(OP2, W))

    Pipeline de 2 Etapas:
    1. Parsing Estructural Canónico → Grafo de Composición Relacional.
    2. Construcción de Firmas Relacionales Tipadas (Relational Signatures).
    3. Filtro de Incompatibilidad Estructural Dura (Rechazo Tajante, no score -0.X).
    4. Generación Discreta de CandidatePool (reducción drástica de pool).
    5. Scoring Estructural Intra-Pool (sin alterar scoring base).

RESTRICCIONES METODOLÓGICAS OBLIGATORIAS:
    1. Cero modificaciones en core/.
    2. A0-TEST (20 casos) permanece 100% ciego e intocable.
    3. Evaluación exclusiva sobre los 8 casos A0-DEV.
    4. Cero aliases, Concept Hubs, sinónimos directos o reglas ad-hoc de los Gold.
    5. El Gold solo se usa para calcular Node-CE@K, NUNCA en la generación.
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

# Rutas congeladas
DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
DEV_DATASET_PATH = "docs/expM_dev_dataset_8cases.json"
OUTPUT_PATH = "docs/expN3_scg_rc_v02_results.json"

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
# 1. GRAMÁTICA Y VOCABULARIO FUNCIONAL CANÓNICO (DERIVACIÓN GENERAL)
# ─────────────────────────────────────────────────────────────────────────────

OPERATOR_DEFS: Dict[str, Dict[str, Any]] = {
    "CREATE": {
        "stems": ["crear", "generar", "producir", "sintetizar", "construir", "formular", "emitir"],
        "required_db_action": {"accion_rutina_automatica", "accion_persistencia_computacion"},
        "incompatible_dims": set()
    },
    "MODIFY": {
        "stems": ["calibrar", "ajustar", "modificar", "actualizar", "corregir", "reajustar", "reparar"],
        "required_db_action": {"accion_evaluar", "accion_cognitiva"},
        "incompatible_dims": set()
    },
    "REMOVE": {
        "stems": ["eliminar", "borrar", "suprimir", "purgar", "depurar", "podar", "limpiar", "descartar"],
        "required_db_action": {"accion_rutina_automatica", "accion_persistencia_computacion"},
        "incompatible_dims": set()
    },
    "EVALUATE": {
        "stems": ["evaluar", "medir", "calcular", "comparar", "analizar", "verificar", "inspeccionar", "diagnosticar"],
        "required_db_action": {"accion_evaluar", "accion_cognitiva"},
        "incompatible_dims": set()
    },
    "COMBINE": {
        "stems": ["combinar", "fusionar", "unir", "integrar", "componer", "agregar", "mezclar"],
        "required_db_action": {"accion_cognitiva", "accion_persistencia_computacion"},
        "incompatible_dims": set()
    },
    "SEPARATE": {
        "stems": ["particionar", "separar", "dividir", "segmentar", "partir", "aislar", "desacoplar"],
        "required_db_action": {"accion_persistencia_computacion"},
        "incompatible_dims": {"identidad_individual", "dominio_espiritual"}  # Restricción dura
    },
    "LINK": {
        "stems": ["vincular", "conectar", "enlazar", "entrelazar", "relacionar", "asociar"],
        "required_db_action": {"accion_cognitiva", "accion_comunicacion"},
        "incompatible_dims": set()
    },
    "STORE": {
        "stems": ["guardar", "persistir", "almacenar", "conservar", "registrar", "archivar"],
        "required_db_action": {"accion_persistencia_computacion", "intencion_documentar"},
        "incompatible_dims": set()
    },
    "RETRIEVE": {
        "stems": ["recuperar", "buscar", "obtener", "extraer", "consultar", "acceder"],
        "required_db_action": {"accion_cognitiva"},
        "incompatible_dims": set()
    },
    "CLASSIFY": {
        "stems": ["clasificar", "categorizar", "ordenar", "organizar", "jerarquizar", "estructurar"],
        "required_db_action": {"accion_evaluar"},
        "incompatible_dims": set()
    },
    "ACTIVATE": {
        "stems": ["activar", "iniciar", "disparar", "lanzar", "encender", "despertar"],
        "required_db_action": {"accion_rutina_automatica"},
        "incompatible_dims": set()
    },
    "DEACTIVATE": {
        "stems": ["desactivar", "pausar", "suspender", "dormir", "detener", "apagar", "letargo"],
        "required_db_action": {"accion_rutina_automatica"},
        "incompatible_dims": set()
    },
    "TRANSFORM": {
        "stems": ["transformar", "proyectar", "mapear", "convertir", "traducir", "normalizar", "codificar"],
        "required_db_action": {"accion_cognitiva"},
        "incompatible_dims": set()
    },
    "PERSIST": {
        "stems": ["consolidar", "confirmar", "fijar", "solidificar", "persistir", "comprometer"],
        "required_db_action": {"accion_persistencia_computacion"},
        "incompatible_dims": set()
    }
}

ROLE_DOMAIN_DEFS: Dict[str, Dict[str, Any]] = {
    "COMPUTATIONAL": {
        "stems": ["computo", "computacional", "hardware", "nucleo", "nucleos", "virtual", "virtuales",
                  "gigas", "memoria", "procesador", "recurso", "recursos", "servidor", "docker"],
        "required_db_dims": {"identidad_fisica_hardware", "accion_persistencia_computacion"},
        "incompatible_dims": {"dominio_espiritual", "afecto"}
    },
    "COGNITIVE": {
        "stems": ["cognitivo", "neural", "neuronal", "sinaptico", "sinapticos", "cortical", "corteza",
                  "hiperdimensional", "hipervector", "athena", "cerebro", "introspeccion"],
        "required_db_dims": {"accion_cognitiva", "identidad_artificial"},
        "incompatible_dims": set()
    },
    "METRIC": {
        "stems": ["coeficiente", "coeficientes", "multiplicativo", "multiplicativos", "peso", "pesos",
                  "ponderacion", "score", "relevancia", "bm25", "umbral", "escala"],
        "required_db_dims": {"accion_evaluar", "cualidad_abstracta_conceptual"},
        "incompatible_dims": set()
    },
    "CONNECTIVE": {
        "stems": ["enlace", "enlaces", "topologia", "grafo", "malla", "red", "transversal", "transversales",
                  "conexion", "conexiones", "entrelazado", "entrelazados", "puente"],
        "required_db_dims": {"accion_cognitiva", "accion_persistencia_computacion"},
        "incompatible_dims": set()
    },
    "STOCHASTIC": {
        "stems": ["estocastico", "estocasticos", "estocastica", "estocasticas", "aleatorio", "probabilistico"],
        "required_db_dims": {"accion_rutina_automatica", "accion_cognitiva"},
        "incompatible_dims": set()
    },
    "CHRONICLE": {
        "stems": ["cronologico", "cronologica", "hito", "hitos", "historial", "bitacora", "trayectoria", "registro"],
        "required_db_dims": {"coordenada_cronologia_absoluta", "intencion_documentar"},
        "incompatible_dims": set()
    },
    "LIFECYCLE": {
        "stems": ["activo", "activos", "dormido", "dormidos", "caduco", "caducos", "vigilia", "letargo", "ciclo"],
        "required_db_dims": {"accion_rutina_automatica"},
        "incompatible_dims": set()
    },
    "DIMENSIONAL": {
        "stems": ["dimensional", "dimensiones", "eje", "ejes", "multidimensional", "espacio"],
        "required_db_dims": {"accion_evaluar", "cualidad_abstracta_conceptual"},
        "incompatible_dims": set()
    },
    "HIERARCHICAL": {
        "stems": ["jerarquico", "jerarquica", "taxonomia", "nivel", "capa", "arbol"],
        "required_db_dims": {"accion_evaluar"},
        "incompatible_dims": set()
    }
}

RELATION_DEFS: Dict[str, Dict[str, Any]] = {
    "BEFORE": {"triggers": ["antes", "previo", "previa", "anterior", "primero"]},
    "AFTER": {"triggers": ["despues", "posterior", "luego", "tras", "siguiente"]},
    "CAUSES": {"triggers": ["causa", "provoca", "genera", "origina", "produce", "desencadena"]},
    "REQUIRES": {"triggers": ["requiere", "necesita", "obligatorio", "debe", "exige", "imprescindible"]},
    "ENABLES": {"triggers": ["permite", "habilita", "facilita", "posibilita"]},
    "BLOCKS": {"triggers": ["impide", "bloquea", "previene", "evita", "prohibe", "inhibe"]},
    "PURPOSE_OF": {"triggers": ["para", "con_el_fin", "objetivo", "proposito", "destinado", "finalidad"]},
    "COORDINATES_WITH": {"triggers": ["junto", "coordinacion", "sincronizacion", "paralelamente", "conjuntamente"]}
}


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def tokenizar(texto: str) -> Set[str]:
    norm = normalizar(texto.replace('_', ' ').replace('-', ' ').replace('/', ' '))
    tokens = re.findall(r'[a-z0-9]{2,}', norm)
    return {t for t in tokens if t not in SPANISH_STOPWORDS}


# ─────────────────────────────────────────────────────────────────────────────
# 2. REPRESENTACIÓN DE FIRMAS RELACIONALES TIPADAS (SCG-RC)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RoleBinding:
    """Argumento tipado de una operación relacional."""
    role_type: str  # "OBJECT", "TARGET", "CONSTRAINT", "CONDITION"
    domain: str     # "COMPUTATIONAL", "COGNITIVE", "METRIC", etc.
    modifiers: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_type": self.role_type,
            "domain": self.domain,
            "modifiers": sorted(self.modifiers)
        }


@dataclass
class RelationalSignature:
    """
    Firma Relacional Completa: Estructura relacional tipada de la query.
    Representa OP_HEAD(ROLE_1(X), ROLE_2(Y)) [RELATION -> OP_TAIL(ROLE_3(Z))]
    """
    head_op: str
    roles: List[RoleBinding] = field(default_factory=list)
    relation: Optional[str] = None
    tail_op: Optional[str] = None
    polarity: int = 1
    modality: str = "DECLARATIVE"
    confidence: float = 0.0
    derivation_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "head_op": self.head_op,
            "roles": [r.to_dict() for r in self.roles],
            "relation": self.relation,
            "tail_op": self.tail_op,
            "polarity": self.polarity,
            "modality": self.modality,
            "confidence": round(self.confidence, 3),
            "trace": self.derivation_trace
        }


# ─────────────────────────────────────────────────────────────────────────────
# 3. PARSER RELACIONAL Y CONSTRUCTOR DE FIRMAS
# ─────────────────────────────────────────────────────────────────────────────

def extraer_firma_relacional(query: str) -> Optional[RelationalSignature]:
    """
    Parsea una query en una Firma Relacional Tipada (RelationalSignature).
    Asegura cero dependencias léxicas ad-hoc: opera sobre la gramática canónica.
    """
    tokens = tokenizar(query)
    texto_norm = normalizar(query)

    # 1. Detectar operaciones canónicas presentes (evitando colisiones morfológicas cortas)
    detected_ops = []
    for op_name, op_cfg in OPERATOR_DEFS.items():
        for stem in op_cfg["stems"]:
            stem_n = normalizar(stem)
            prefix_len = min(len(stem_n), 5)
            if any(t == stem_n or (len(t) >= 5 and (t.startswith(stem_n[:prefix_len]) or stem_n.startswith(t[:prefix_len]))) for t in tokens):
                detected_ops.append(op_name)
                break

    if not detected_ops:
        return None  # Abstención justificada: query no accional

    head_op = detected_ops[0]
    tail_op = detected_ops[1] if len(detected_ops) > 1 else None

    # 2. Detectar dominios de rol
    roles = []
    for role_name, role_cfg in ROLE_DOMAIN_DEFS.items():
        matched_stems = set()
        for stem in role_cfg["stems"]:
            stem_n = normalizar(stem)
            prefix_len = min(len(stem_n), 5)
            for t in tokens:
                if t == stem_n or (len(t) >= 5 and (t.startswith(stem_n[:prefix_len]) or stem_n.startswith(t[:prefix_len]))):
                    matched_stems.add(t)
        if matched_stems:
            role_type = "OBJECT" if len(roles) == 0 else "TARGET"
            roles.append(RoleBinding(role_type=role_type, domain=role_name, modifiers=matched_stems))

    # 3. Detectar relación entre operaciones
    rel_detected = None
    for rel_name, rel_cfg in RELATION_DEFS.items():
        for trig in rel_cfg["triggers"]:
            if trig in tokens or trig in texto_norm:
                rel_detected = rel_name
                break
        if rel_detected:
            break

    # 4. Detectar polaridad y modalidad
    polarity = -1 if any(t in tokens for t in ['no', 'sin', 'nunca', 'evitar', 'impedir', 'prohibir']) else 1
    modality = "MANDATORY" if any(t in tokens for t in ['requiere', 'necesita', 'obligatorio', 'debe', 'exige']) else "DECLARATIVE"

    sig = RelationalSignature(
        head_op=head_op,
        roles=roles,
        relation=rel_detected,
        tail_op=tail_op,
        polarity=polarity,
        modality=modality,
        confidence=min(1.0, (len(detected_ops) * 0.4 + len(roles) * 0.3 + (0.3 if rel_detected else 0.0))),
        derivation_trace=[
            f"HEAD_OP={head_op}",
            f"ROLES={[r.domain for r in roles]}",
            f"RELATION={rel_detected}",
            f"TAIL_OP={tail_op}",
            f"POLARITY={polarity}"
        ]
    )
    return sig


# ─────────────────────────────────────────────────────────────────────────────
# 4. MOTOR SCG-RC v0.2: FILTRO DE RECHAZO DURO Y GENERADOR DE CANDIDATOS
# ─────────────────────────────────────────────────────────────────────────────

class SCGRCEngine:
    """
    Motor SCG-RC v0.2: Generador de candidatos con Restricciones Relacionales Duras.
    """

    def __init__(self, db_conn: sqlite3.Connection, labels_data: Dict[str, Any]):
        self.conn = db_conn
        self.labels = labels_data
        self.comunidades = dict(zip(labels_data["conceptos"], labels_data["knn_lpa"]))
        self._indexar_db()

    def _indexar_db(self):
        c = self.conn.cursor()
        self.nodos_activos = set(r[0] for r in c.execute("SELECT concepto FROM largo_plazo WHERE estado='activo'").fetchall())

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

        self.accion_dims: Dict[str, Set[str]] = defaultdict(set)
        self.all_dim_names: Dict[str, Set[str]] = defaultdict(set)
        for nodo, dims in self.dims_por_nodo.items():
            for tipo, dim in dims:
                self.all_dim_names[nodo].add(dim)
                if tipo == 'accion':
                    self.accion_dims[nodo].add(dim)

        self.sinapsis_out: Dict[str, Dict[str, float]] = defaultdict(dict)
        for orig, dest, peso in c.execute(
            "SELECT origen, destino, peso FROM sinapsis "
            "WHERE origen IN (SELECT concepto FROM largo_plazo WHERE estado='activo')"
        ).fetchall():
            self.sinapsis_out[orig][dest] = peso

        self.sinonimos: Dict[str, Set[str]] = {}
        for conc, syns in c.execute("SELECT concepto, sinonimos FROM largo_plazo WHERE estado='activo'").fetchall():
            self.sinonimos[conc] = tokenizar(syns) if syns else set()

        print(f"[SCG-RC] DB Indexada: {len(self.nodos_activos)} nodos activos.")

    def verificar_compatibilidad_dura(
        self,
        nodo: str,
        sig: RelationalSignature
    ) -> Tuple[bool, float, List[str]]:
        """
        Verifica compatibilidad dura (Hard Constraint) con la Firma Relacional.
        Retorna (is_admitted, structural_score, trails).
        RECHAZO DURO = is_admitted is False (score = 0.0).
        """
        nodo_dims = self.dims_por_nodo.get(nodo, set())
        nodo_accion = self.accion_dims.get(nodo, set())
        nodo_all_dims = self.all_dim_names.get(nodo, set())
        trails = []

        # ── REGLA DURA 1: Incompatibilidad Dimensional Explícita del Operador Head ──
        op_def = OPERATOR_DEFS.get(sig.head_op)
        if op_def and op_def["incompatible_dims"]:
            incomp_matched = op_def["incompatible_dims"].intersection(nodo_all_dims)
            if incomp_matched:
                return False, 0.0, [f"HARD_REJECT: Dimensión incompatible con {sig.head_op}: {incomp_matched}"]

        # ── REGLA DURA 2: Cobertura de Acción del Operador Head ─────────────────────
        if op_def and op_def["required_db_action"]:
            matched_act = op_def["required_db_action"].intersection(nodo_accion)
            if not matched_act:
                # Si no tiene acción head, verificar si satisface tail_op
                if sig.tail_op:
                    tail_def = OPERATOR_DEFS.get(sig.tail_op)
                    matched_tail = tail_def["required_db_action"].intersection(nodo_accion) if tail_def else set()
                    if not matched_tail:
                        return False, 0.0, [f"HARD_REJECT: Sin acción requerida para HEAD({sig.head_op}) ni TAIL({sig.tail_op})"]
                    trails.append(f"TAIL_ACTION_MATCH({sig.tail_op}): {matched_tail}")
                else:
                    return False, 0.0, [f"HARD_REJECT: Sin acción requerida para HEAD({sig.head_op}): {op_def['required_db_action']}"]
            else:
                trails.append(f"HEAD_ACTION_MATCH({sig.head_op}): {matched_act}")

        # ── REGLA DURA 3: Validación de Roles Tipados y Dominios ────────────────────
        # Si la query tiene roles (ej. COMPUTATIONAL, COGNITIVE), el candidato
        # DEBE satisfacer al menos uno de los dominios requeridos y NO tener dimensiones incompatibles
        score_roles = 0.0
        if sig.roles:
            role_matches = 0
            for r in sig.roles:
                r_def = ROLE_DOMAIN_DEFS.get(r.domain)
                if not r_def:
                    continue
                # Incompatibilidad dura de rol
                incomp_role = r_def["incompatible_dims"].intersection(nodo_all_dims)
                if incomp_role:
                    return False, 0.0, [f"HARD_REJECT: Dimensión incompatible con rol {r.domain}: {incomp_role}"]

                matched_r_dims = r_def["required_db_dims"].intersection(nodo_all_dims)
                if matched_r_dims:
                    role_matches += 1
                    score_roles += 1.5
                    trails.append(f"ROLE_MATCH({r.domain}): {matched_r_dims}")
                else:
                    trails.append(f"ROLE_MISS({r.domain})")

            if role_matches == 0:
                # RECHAZO DURO: No satisface ningún rol requerido por la firma
                return False, 0.0, [f"HARD_REJECT: No satisface ninguno de los roles tipados requeridos: {[r.domain for r in sig.roles]}"]

        # ── REGLA DURA 4: Restricción Antagonista / Polaridad ───────────────────────
        if sig.polarity == -1 or sig.relation == "BLOCKS":
            # Requiere que el nodo posea características de restricción o rutina de evaluación
            if "accion_evaluar" not in nodo_accion and "accion_rutina_automatica" not in nodo_accion:
                return False, 0.0, ["HARD_REJECT: Polaridad negativa / BLOCKS requiere capacidad de evaluación o control"]

        # ── PUNTUACIÓN ESTRUCTURAL DE ADMISIÓN (SOLO SI PASÓ TODAS LAS REGLAS DURAS) ─
        score_base = 2.0
        final_score = score_base + score_roles

        # Bonus si satisface tanto HEAD como TAIL
        if sig.tail_op:
            tail_def = OPERATOR_DEFS.get(sig.tail_op)
            if tail_def and tail_def["required_db_action"].intersection(nodo_accion):
                final_score += 1.0
                trails.append(f"COMPOSITIONAL_BONUS(HEAD+TAIL): {sig.head_op}⊕{sig.tail_op}")

        return True, final_score, trails

    def generar_candidate_pool(
        self,
        query: str
    ) -> Tuple[Set[str], Dict[str, Any], Dict[str, Any]]:
        """
        Etapa 1: Genera el CandidatePool DISCRETO mediante Restricciones Relacionales Duras.
        """
        sig = extraer_firma_relacional(query)
        if not sig:
            return set(), {}, {"signature": None, "pool_size": 0, "abstain": True}

        pool = set()
        trazabilidad = {}

        for nodo in self.nodos_activos:
            admitted, sc, trails = self.verificar_compatibilidad_dura(nodo, sig)
            if admitted:
                pool.add(nodo)
                trazabilidad[nodo] = {
                    "score_estructural": round(sc, 4),
                    "trails": trails
                }

        meta = {
            "signature": sig.to_dict(),
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
        Etapa 2: Scoring intra-pool basado en la precisión de alineación de la firma relacional.
        """
        if not pool:
            return []

        sig = extraer_firma_relacional(query)
        scores = {}

        for nodo in pool:
            base_sc = trazabilidad.get(nodo, {}).get("score_estructural", 0.0)

            # Bonus por número de roles satisfechos simultáneamente
            nodo_all_dims = self.all_dim_names.get(nodo, set())
            roles_covered = 0
            if sig and sig.roles:
                for r in sig.roles:
                    r_def = ROLE_DOMAIN_DEFS.get(r.domain)
                    if r_def and r_def["required_db_dims"].intersection(nodo_all_dims):
                        roles_covered += 1

            role_coverage_ratio = roles_covered / len(sig.roles) if (sig and sig.roles) else 0.0
            score_final = base_sc + 2.0 * role_coverage_ratio

            scores[nodo] = score_final

        sorted_cands = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        resultado = []
        for rank, (nodo, sc) in enumerate(sorted_cands[:k], 1):
            resultado.append({
                "rank": rank,
                "node": nodo,
                "score": round(sc, 4),
                "island": self.comunidades.get(nodo),
                "trails": trazabilidad.get(nodo, {}).get("trails", [])
            })
        return resultado


# ─────────────────────────────────────────────────────────────────────────────
# 5. EVALUACIÓN Y VALIDACIÓN EXPERIMENTAL
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_scg_rc_v02():
    print("=============================================================================")
    print("SCG-RC v0.2: RELATIONAL COMPOSITION CONSTRAINT GENERATOR")
    print("=============================================================================")
    print(f"• Snapshot DB SHA-256: {hashlib.sha256(open(DB_PATH, 'rb').read()).hexdigest()}")
    print(f"• Labels   SHA-256:    {hashlib.sha256(open(LABELS_PATH, 'rb').read()).hexdigest()}")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = json.load(f)
    with open(DEV_DATASET_PATH, "r", encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]

    engine = SCGRCEngine(con, labels)

    A0_STRICT = {"OOF_POS_11", "OOF_POS_19", "OOF_POS_21", "OOF_POS_29", "OOF_POS_30", "OOF_POS_48"}

    resultados = []
    pool_sizes = []
    hits = {k: 0 for k in K_CURVE}

    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]
        is_strict = cid in A0_STRICT

        t0 = time.perf_counter()
        pool, traz, meta = engine.generar_candidate_pool(q)
        t_gen = (time.perf_counter() - t0) * 1000

        ranked = engine.rankear_candidate_pool(q, pool, traz, k=20)

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

        sig = meta.get("signature")
        sig_str = f"{sig['head_op']}({[r['domain'] for r in sig['roles']]})" if sig else "NONE"
        rk_str = str(gold_rank) if gold_rank else "None"
        a0_str = "STRICT_A0" if is_strict else "NO_A0"

        print(f"[{cid}] A0={a0_str:9s} | Pool:{len(pool):4d} ({meta['pool_pct_corpus']:5.1f}%) | "
              f"InPool:{str(gold_in_pool):5s} | Rank:{rk_str:>4s} | Sig:{sig_str}")

        resultados.append({
            "case_id": cid,
            "is_strict_a0": is_strict,
            "query": q,
            "gold": gold,
            "pool_size": len(pool),
            "pool_pct": meta["pool_pct_corpus"],
            "gold_in_pool": gold_in_pool,
            "gold_rank": gold_rank,
            "gold_score": gold_score,
            "signature": sig,
            "latency_gen_ms": round(t_gen, 2),
            "top_candidates": ranked[:5]
        })

    strict_res = [r for r in resultados if r["is_strict_a0"]]
    noa0_res = [r for r in resultados if not r["is_strict_a0"]]

    strict_in_pool = sum(1 for r in strict_res if r["gold_in_pool"])
    noa0_in_pool = sum(1 for r in noa0_res if r["gold_in_pool"])

    strict_hits = {k: sum(1 for r in strict_res if r["gold_rank"] and r["gold_rank"] <= k) for k in K_CURVE}

    print("\n=============================================================================")
    print("RESUMEN FORMAL SCG-RC v0.2 (A0-DEV)")
    print("=============================================================================")
    print(f"• Pool Promedio Total: {float(np.mean(pool_sizes)):.1f} nodos ({float(np.mean(pool_sizes))/851*100:.1f}%)")
    print(f"• Candidate Generation Recall (Total 8 DEV):      {sum(1 for r in resultados if r['gold_in_pool'])}/8 ({sum(1 for r in resultados if r['gold_in_pool'])/8*100:.1f}%)")
    print(f"• Candidate Generation Recall (STRICT A0, N=6):   {strict_in_pool}/6 ({strict_in_pool/6*100:.1f}%)")
    print(f"• Candidate Generation Recall (NO A0, N=2):       {noa0_in_pool}/2 ({noa0_in_pool/2*100:.1f}%)")
    print(f"\n• Node-CE@K (Total 8 DEV):")
    for k in K_CURVE:
        print(f"    CE@{k:02d} = {hits[k]}/8")
    print(f"\n• Node-CE@K (STRICT A0 Únicamente, N=6):")
    for k in K_CURVE:
        print(f"    CE@{k:02d} = {strict_hits[k]}/6")

    # Guardar resultados
    os.makedirs("docs", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N3: SCG-RC v0.2 (Relational Composition Constraint Generator)",
        "hashes": {
            "db_snapshot": hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest(),
            "labels": hashlib.sha256(open(LABELS_PATH, "rb").read()).hexdigest(),
        },
        "summary": {
            "avg_pool_size": round(float(np.mean(pool_sizes)), 1),
            "avg_pool_pct": round(float(np.mean(pool_sizes)) / 851 * 100, 1),
            "candidate_generation_recall_total": f"{sum(1 for r in resultados if r['gold_in_pool'])}/8",
            "candidate_generation_recall_strict_a0": f"{strict_in_pool}/6",
            "node_ce_total": {f"CE@{k}": f"{hits[k]}/8" for k in K_CURVE},
            "node_ce_strict_a0": {f"CE@{k}": f"{strict_hits[k]}/6" for k in K_CURVE},
        },
        "case_details": resultados
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Resultados guardados en: {OUTPUT_PATH}")
    con.close()


if __name__ == "__main__":
    ejecutar_scg_rc_v02()
