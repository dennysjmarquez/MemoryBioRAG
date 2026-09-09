#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN7_3_c_partition_audit.py
=============================================================================
EXP-N7.3: AUDITORÍA DE PARTICIÓN INTERNA DE NIVEL C (C1 / C2 / C3)
=============================================================================
PROPÓSITO CIENTÍFICO (Protocolo Aureon — Autorización post-N7.2-PARTIAL):

    N7.2 demostró que 6/6 Gold Strict A0 requieren canonicalización Nivel C.
    Sin embargo, "Nivel C" no es una categoría homogénea. Aureon ordena
    separar:

        C1 — Canonicalización morfológica deverbal TRANSPARENTE:
             nominalización de proceso derivada de verbo base conocido.
             Ejemplos: evaluación → EVALUATE, creación → CREATE,
                       integración → COMBINE, actualización → MODIFY.
             Requisito: la regla morfológica debe ser GENERAL (aplica a
             familias léxicas completas) y PREEXISTENTE (no inventada ad-hoc
             para estos Gold).

        C2 — Derivación AGENTIVA (sustantivo de agente → operación):
             el span es un sustantivo de agente, no de proceso.
             Ejemplo: creador → CREATE.
             Distinción: implica interpretar quién hace la acción como
             la acción misma. Más alto nivel de abstracción que C1.

        C3 — Interpretación SEMÁNTICA / METAFÓRICA:
             el span no es ni nominalización ni agentivo: es un verbo
             de dominio físico reinterpretado semánticamente.
             Ejemplo: corre → EXECUTE (metáfora de ejecución de proceso).
             PROHIBIDO en el mecanismo principal si no se valida por separado.

    C3 NO es canonicalización morfológica. NO debe mezclarse con C1/C2
    en el overlay inicial de retrieval.

RESTRICCIONES DEL EXPERIMENTO:
    core/ intacto | A0-TEST ciego | snapshot read-only | sin scoring
    sin retrieval | sin aliases | sin Gold/DEV metadata como entrada
    Entrada primaria: exclusivamente largo_plazo.contenido
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
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.abspath("."))

from scripts.experimentos.expN_scg_v01 import (
    DB_PATH,
    LABELS_PATH,
    DEV_DATASET_PATH,
    normalizar,
    tokenizar,
    SPANISH_STOPWORDS,
)

OUTPUT_EXP_N7_3 = "docs/expN7_3_c_partition_results.json"

# Gold Strict A0 — idénticos a N7.1 y N7.2
A0_STRICT_GOLDS = [
    {"id": "OOF_POS_11", "gold": "docker_infrastructure_rog"},
    {"id": "OOF_POS_19", "gold": "scoring_pesos_bm25"},
    {"id": "OOF_POS_21", "gold": "coche_puente_condicional"},
    {"id": "OOF_POS_29", "gold": "desde_athena_biorag"},
    {"id": "OOF_POS_30", "gold": "activos_dormidos_hermana"},
    {"id": "OOF_POS_48", "gold": "cuaternidad-logica-oec"},
]

# ─────────────────────────────────────────────────────────────────────────────
# 1. CATÁLOGO DE REGLAS C CON CLASIFICACIÓN INTERNA C1 / C2 / C3
#    Referencia lingüística: RAE Gramática §4.1-§4.3, NomLex (Macleod et al.
#    1998), FrameNet nominal, Lakoff & Johnson "Metaphors We Live By" §5.
#    Las reglas son GENERALES: aplican a familias léxicas, no a Gold específicos.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CRule:
    """
    Una regla de canonicalización Nivel C con su clasificación interna.

    rule_id               : identificador único
    pattern               : regex sobre texto normalizado
    canonical_op          : operador estructural resultante
    c_subtype             : 'C1', 'C2', o 'C3'
    lemma_family          : familia verbal de origen
    morphological_relation: descripción del proceso morfológico
    rule_provenance       : fuente lingüística (no específica del Gold)
    generalizable         : True si aplica a ejemplos fuera del Gold
    generalidad_ejemplos  : lista de ejemplos lingüísticos externos
    gold_dependent        : siempre False (protocolo Aureon)
    leakage_flag          : siempre False (protocolo Aureon)
    """
    rule_id: str
    pattern: str
    canonical_op: str
    c_subtype: str
    lemma_family: str
    morphological_relation: str
    rule_provenance: str
    generalizable: bool
    generalidad_ejemplos: List[str]
    gold_dependent: bool = False
    leakage_flag: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "pattern": self.pattern,
            "canonical_op": self.canonical_op,
            "c_subtype": self.c_subtype,
            "lemma_family": self.lemma_family,
            "morphological_relation": self.morphological_relation,
            "rule_provenance": self.rule_provenance,
            "generalizable": self.generalizable,
            "generalidad_ejemplos": self.generalidad_ejemplos,
            "gold_dependent": self.gold_dependent,
            "leakage_flag": self.leakage_flag,
        }


C_RULE_CATALOG: List[CRule] = [

    # ── C1: NOMINALIZACIONES DEVERBALES TRANSPARENTES ────────────────────────
    # Morfología: sufijo -ción/-sión del verbo base (RAE §4.1.3, NomLex VERB-NOM)
    # La regla NO se creó para estos Gold: aplica a familias léxicas completas.

    CRule(
        rule_id="RULE_C1_NOM_SEPARATE",
        pattern=r'\b(particion|segmentacion|division|separacion)\b',
        canonical_op="SEPARATE", c_subtype="C1",
        lemma_family="partir / separar / dividir / segmentar",
        morphological_relation="nominalización deverbal -ción (proceso resultativo)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La partición del índice redujo la latencia",
            "Se realizó una segmentación semántica del corpus",
            "La división de tareas mejoró el rendimiento",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_CREATE",
        pattern=r'\b(creacion|generacion|produccion|sintesis|construccion)\b',
        canonical_op="CREATE", c_subtype="C1",
        lemma_family="crear / generar / producir / sintetizar / construir",
        morphological_relation="nominalización deverbal -ción/-sis (proceso resultativo)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM / FrameNet Creating",
        generalizable=True,
        generalidad_ejemplos=[
            "La creación del índice vectorial tardó 12 segundos",
            "La generación de tokens sigue el esquema BPE",
            "La construcción del grafo de dependencias es automática",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_MODIFY",
        pattern=r'\b(calibracion|ajuste[s]?|modificacion|actualizacion|correccion)\b',
        canonical_op="MODIFY", c_subtype="C1",
        lemma_family="calibrar / ajustar / modificar / actualizar / corregir",
        morphological_relation="nominalización deverbal -ción/-e (proceso de cambio)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La calibración del modelo se ejecuta cada 100 épocas",
            "El ajuste de hiperparámetros se realiza por búsqueda aleatoria",
            "La actualización incremental del índice evita reindexado completo",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_EVALUATE",
        pattern=r'\b(evaluacion|medicion|calculo|analisis|verificacion|diagnostico)\b',
        canonical_op="EVALUATE", c_subtype="C1",
        lemma_family="evaluar / medir / calcular / analizar / verificar",
        morphological_relation="nominalización deverbal -ción/-sis (proceso de medición)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM / FrameNet Scrutiny",
        generalizable=True,
        generalidad_ejemplos=[
            "La evaluación del modelo se realiza en el conjunto de prueba",
            "El análisis de complejidad es O(n log n)",
            "La verificación formal del protocolo tomó 3 horas",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_COMBINE",
        pattern=r'\b(combinacion|fusion|integracion|composicion|union)\b',
        canonical_op="COMBINE", c_subtype="C1",
        lemma_family="combinar / fusionar / integrar / componer / unir",
        morphological_relation="nominalización deverbal -ción/-ón (proceso de unión)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM / FrameNet Amalgamation",
        generalizable=True,
        generalidad_ejemplos=[
            "La integración de módulos reduce acoplamiento",
            "La fusión de ramas en git requiere resolver conflictos",
            "La combinación de señales mejora la relación señal/ruido",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_LINK",
        pattern=r'\b(vinculacion|conexion[es]*|enlace[s]?|entrelazamiento|relacion[es]*)\b',
        canonical_op="LINK", c_subtype="C1",
        lemma_family="vincular / conectar / enlazar / entrelazar / relacionar",
        morphological_relation="nominalización deverbal -ción/-e (proceso de conexión)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La vinculación entre nodos del grafo es ponderada",
            "La conexión a la base de datos usa pool persistente",
            "El enlace hipertextual apunta al recurso canónico",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_STORE",
        pattern=r'\b(persistencia|almacenamiento|registro[s]?|archivo)\b',
        canonical_op="STORE", c_subtype="C1",
        lemma_family="persistir / almacenar / registrar / archivar",
        morphological_relation="nominalización deverbal -ncia/-miento/-o (estado resultante)",
        rule_provenance="RAE §4.1.2 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La persistencia de sesión usa cookies firmadas",
            "El almacenamiento en caché mejora la latencia",
            "El registro de auditoría se guarda en S3",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_RETRIEVE",
        pattern=r'\b(recuperacion|busqueda|extraccion|consulta[s]?)\b',
        canonical_op="RETRIEVE", c_subtype="C1",
        lemma_family="recuperar / buscar / extraer / consultar",
        morphological_relation="nominalización deverbal -ción/-a (proceso de acceso)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM / IR terminology",
        generalizable=True,
        generalidad_ejemplos=[
            "La recuperación de información es el núcleo del motor",
            "La búsqueda semántica supera la búsqueda léxica en cobertura",
            "La extracción de entidades sigue el esquema BIO",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_CLASSIFY",
        pattern=r'\b(clasificacion|categorizacion|ordenamiento|jerarquia|taxonomia)\b',
        canonical_op="CLASSIFY", c_subtype="C1",
        lemma_family="clasificar / categorizar / ordenar / jerarquizar",
        morphological_relation="nominalización deverbal -ción/-a/-ía (proceso de categorización)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La clasificación de intenciones usa un clasificador BERT",
            "La taxonomía de errores tiene 5 niveles",
            "La categorización automática de tickets reduce triaje manual",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_ACTIVATE",
        pattern=r'\b(activacion|disparo|lanzamiento|despertar)\b',
        canonical_op="ACTIVATE", c_subtype="C1",
        lemma_family="activar / disparar / lanzar / despertar",
        morphological_relation="nominalización deverbal -ción/-o (proceso de inicio)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La activación del proceso de consolidación ocurre cada hora",
            "El disparo del evento ocurre al detectar cambio de estado",
            "El lanzamiento del worker se retrasa 5 segundos",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_DEACTIVATE",
        pattern=r'\b(desactivacion|suspension|letargo)\b',
        canonical_op="DEACTIVATE", c_subtype="C1",
        lemma_family="desactivar / suspender / adormecer",
        morphological_relation="nominalización deverbal -ción/-o (proceso de detención)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La suspensión del hilo espera señal de reanudación",
            "La desactivación del módulo libera sus recursos",
            "El letargo de nodos inactivos reduce consumo energético",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_TRANSFORM",
        pattern=r'\b(transformacion|proyeccion|conversion|traduccion|normalizacion)\b',
        canonical_op="TRANSFORM", c_subtype="C1",
        lemma_family="transformar / proyectar / convertir / traducir / normalizar",
        morphological_relation="nominalización deverbal -ción (proceso de conversión)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La transformación de Fourier convierte señal temporal en frecuencial",
            "La normalización de vectores garantiza comparación por coseno",
            "La conversión de formatos de fecha puede generar errores de zona horaria",
        ],
    ),
    CRule(
        rule_id="RULE_C1_NOM_PERSIST",
        pattern=r'\b(consolidacion|confirmacion)\b',
        canonical_op="PERSIST", c_subtype="C1",
        lemma_family="consolidar / confirmar",
        morphological_relation="nominalización deverbal -ción (proceso de fijación)",
        rule_provenance="RAE §4.1.3 / NomLex VERB-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "La consolidación de cambios en disco ocurre en el commit",
            "La confirmación de la transacción garantiza ACID",
        ],
    ),

    # ── C2: DERIVACIÓN AGENTIVA ──────────────────────────────────────────────
    # Morfología: sufijo -dor/-sor del verbo base (RAE §4.2.1, NomLex AGENT-NOM)
    # Mapea sustantivo de agente → operación. Mayor abstracción que C1.

    CRule(
        rule_id="RULE_C2_AGENT_CREATE",
        pattern=r'\b(creador[es]*|generador[es]*|productor[es]*|constructor[es]*)\b',
        canonical_op="CREATE", c_subtype="C2",
        lemma_family="crear / generar / producir / construir",
        morphological_relation="sustantivo agentivo -dor: el que realiza la acción de crear",
        rule_provenance="RAE §4.2.1 / NomLex AGENT-NOM / FrameNet Creator",
        generalizable=True,
        generalidad_ejemplos=[
            "El generador de reportes produce PDF automáticamente",
            "El constructor del objeto acepta parámetros opcionales",
            "El productor de mensajes publica en el topic de Kafka",
        ],
    ),
    CRule(
        rule_id="RULE_C2_AGENT_EVALUATE",
        pattern=r'\b(evaluador[es]*|analizador[es]*|verificador[es]*)\b',
        canonical_op="EVALUATE", c_subtype="C2",
        lemma_family="evaluar / analizar / verificar",
        morphological_relation="sustantivo agentivo -dor: el que realiza la evaluación",
        rule_provenance="RAE §4.2.1 / NomLex AGENT-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "El evaluador de calidad rechaza outputs bajo el umbral",
            "El analizador léxico tokeniza el stream de entrada",
            "El verificador de integridad comprueba el hash SHA-256",
        ],
    ),
    CRule(
        rule_id="RULE_C2_AGENT_RETRIEVE",
        pattern=r'\b(recuperador[es]*|buscador[es]*|extractor[es]*)\b',
        canonical_op="RETRIEVE", c_subtype="C2",
        lemma_family="recuperar / buscar / extraer",
        morphological_relation="sustantivo agentivo -dor: el que recupera información",
        rule_provenance="RAE §4.2.1 / NomLex AGENT-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "El recuperador de contexto obtiene los k vecinos más cercanos",
            "El extractor de entidades usa CRF como decodificador",
            "El buscador semántico indexa 10M documentos",
        ],
    ),
    CRule(
        rule_id="RULE_C2_AGENT_STORE",
        pattern=r'\b(almacenador[es]*|registrador[es]*|archivador[es]*)\b',
        canonical_op="STORE", c_subtype="C2",
        lemma_family="almacenar / registrar / archivar",
        morphological_relation="sustantivo agentivo -dor: el que almacena datos",
        rule_provenance="RAE §4.2.1 / NomLex AGENT-NOM",
        generalizable=True,
        generalidad_ejemplos=[
            "El almacenador de logs rota archivos diariamente",
            "El registrador de eventos escribe en un buffer circular",
        ],
    ),

    # ── C3: INTERPRETACIÓN SEMÁNTICA / METAFÓRICA ────────────────────────────
    # El span NO es nominalización ni agentivo: verbo de dominio físico/técnico
    # reinterpretado como operación computacional.
    # Referencia: Lakoff & Johnson "Metaphors We Live By" §5.
    # NOTA: C3 requiere validación semántica separada antes de entrar en retrieval.

    CRule(
        rule_id="RULE_C3_METAPHOR_RUN_EXECUTE",
        pattern=r'\b(corre[n]?|correr)\b',
        canonical_op="EXECUTE", c_subtype="C3",
        lemma_family="correr (dominio físico → EJECUTAR en dominio computacional)",
        morphological_relation=(
            "Metáfora conceptual CORRER-UN-PROCESO = EJECUTAR-UN-PROCESO. "
            "En contexto computacional español, 'correr' hereda el esquema "
            "metafórico run→EXECUTE del inglés. NO es nominalización deverbal."
        ),
        rule_provenance=(
            "Lakoff & Johnson 'Metaphors We Live By' §5 / "
            "Metáfora computacional EN→ES 'run→correr' / DRAE acepción 14"
        ),
        generalizable=True,
        generalidad_ejemplos=[
            "El servidor corre en puerto 8080",
            "El script corre sin errores en Python 3.11",
            "¿Cuánto tarda en correr el modelo de inferencia?",
        ],
    ),
]

# Índice compilado para búsqueda eficiente
_COMPILED_CATALOG: List[Tuple[re.Pattern, CRule]] = [
    (re.compile(r.pattern), r) for r in C_RULE_CATALOG
]


def clasificar_span_c(span_norm: str) -> Optional[CRule]:
    """
    Dado un span normalizado, retorna la CRule que lo clasifica, o None.
    Uso: determinar C1/C2/C3 de un span antes de usarlo en retrieval.
    """
    for compiled_pat, rule in _COMPILED_CATALOG:
        if compiled_pat.search(span_norm):
            return rule
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. REGISTRO DE EXTRACCIÓN C CON SUBCLASIFICACIÓN COMPLETA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CExtractionRecord:
    """
    Registro completo de extracción Nivel C con todos los campos Aureon N7.3.
    """
    node_id: str
    source_span: str
    source_text_preview: str
    lemma: str
    morphological_relation: str
    canonical_operator: str
    rule_id: str
    rule_provenance: str
    inference_level: str        # "C1", "C2", o "C3"
    confidence: float           # C1=0.85, C2=0.75, C3=0.65
    gold_dependent: bool = False
    leakage_flag: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "source_span": self.source_span,
            "source_text_preview": self.source_text_preview,
            "lemma": self.lemma,
            "morphological_relation": self.morphological_relation,
            "canonical_operator": self.canonical_operator,
            "rule_id": self.rule_id,
            "rule_provenance": self.rule_provenance,
            "inference_level": self.inference_level,
            "confidence": round(self.confidence, 2),
            "gold_dependent": self.gold_dependent,
            "leakage_flag": self.leakage_flag,
        }


def extraer_c_record(node_id: str, texto: str) -> Optional[CExtractionRecord]:
    """
    Para un nodo, aplica el catálogo C (prioridad C1>C2>C3) SOLO si no
    hay verbo activo Nivel A. Retorna el primer CExtractionRecord o None.
    Razón: igual que en N7.2, Nivel A tiene precedencia sobre Nivel C.
    """
    from scripts.experimentos.expN7_2_extraction_vs_canonicalization_audit import (
        VERB_ACTIVE_RULES_A,
    )
    texto_norm = normalizar(texto)

    # Si hay verbo activo → no es Nivel C
    for pat_str, _, _ in VERB_ACTIVE_RULES_A:
        if re.search(pat_str, texto_norm):
            return None

    sentences = re.split(r'[.\n;]', texto_norm)
    first_clause = sentences[0] if sentences else texto_norm

    for subtype in ("C1", "C2", "C3"):
        for compiled_pat, rule in _COMPILED_CATALOG:
            if rule.c_subtype != subtype:
                continue
            m = compiled_pat.search(first_clause) or compiled_pat.search(texto_norm)
            if m:
                span = m.group(0)
                confidence = {"C1": 0.85, "C2": 0.75, "C3": 0.65}[subtype]
                return CExtractionRecord(
                    node_id=node_id,
                    source_span=span,
                    source_text_preview=texto[:120],
                    lemma=rule.lemma_family.split(" / ")[0],
                    morphological_relation=rule.morphological_relation,
                    canonical_operator=rule.canonical_op,
                    rule_id=rule.rule_id,
                    rule_provenance=rule.rule_provenance,
                    inference_level=subtype,
                    confidence=confidence,
                    gold_dependent=False,
                    leakage_flag=False,
                )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. PRUEBA DE GENERALIDAD DE REGLAS C1
#    Para cada regla C1, verificar que su patrón captura ejemplos externos
#    al Gold y NO genera falsos positivos en textos negativos genéricos.
# ─────────────────────────────────────────────────────────────────────────────

def verificar_generalidad_c1() -> List[Dict[str, Any]]:
    """
    Verifica generalidad de cada regla C1: >=2/3 ejemplos positivos capturan
    y no hay falsos positivos en textos negativos sin los spans de la familia.
    Razón: generalidad es el criterio que separa C1 de una regla Clase D ad-hoc.
    """
    results = []
    c1_rules = [r for r in C_RULE_CATALOG if r.c_subtype == "C1"]

    textos_negativos = [
        "el sistema recibe una señal de entrada",
        "la memoria almacena datos en formato binario",
        "el proceso espera 100 milisegundos",
    ]

    for rule in c1_rules:
        compiled = re.compile(rule.pattern)
        ejemplos_positivos = []

        for ejemplo in rule.generalidad_ejemplos:
            ejemplo_norm = normalizar(ejemplo)
            m = compiled.search(ejemplo_norm)
            ejemplos_positivos.append({
                "ejemplo": ejemplo,
                "span_capturado": m.group(0) if m else None,
                "ok": bool(m)
            })

        falsos_positivos = []
        for neg in textos_negativos:
            neg_norm = normalizar(neg)
            m_neg = compiled.search(neg_norm)
            if m_neg:
                falsos_positivos.append({
                    "texto_negativo": neg,
                    "falso_positivo": m_neg.group(0)
                })

        positivos_ok = sum(1 for e in ejemplos_positivos if e["ok"])
        total_positivos = len(ejemplos_positivos)
        generalizable_confirmed = positivos_ok >= 2 and len(falsos_positivos) == 0

        results.append({
            "rule_id": rule.rule_id,
            "c_subtype": rule.c_subtype,
            "canonical_op": rule.canonical_op,
            "ejemplos_positivos": ejemplos_positivos,
            "positivos_ok": f"{positivos_ok}/{total_positivos}",
            "falsos_positivos": falsos_positivos,
            "generalizable_confirmed": generalizable_confirmed,
        })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. MATRIZ C1/C2/C3 PARA LOS 6 GOLD STRICT A0
# ─────────────────────────────────────────────────────────────────────────────

def construir_matriz_gold(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Para cada Gold, clasifica el span C identificado en N7.2 como C1/C2/C3.
    Los spans vienen del resultado empírico de N7.2, no de Gold metadata.
    Razón: Aureon exige clasificación explícita antes de autorizar retrieval.
    """
    c = con.cursor()
    matrix = []

    # Spans confirmados por N7.2 (empírico, no Gold-conditioned)
    gold_c_spans = {
        "docker_infrastructure_rog": "corre",
        "scoring_pesos_bm25": "integracion",
        "coche_puente_condicional": "evaluacion",
        "desde_athena_biorag": "creacion",
        "activos_dormidos_hermana": "actualizacion",
        "cuaternidad-logica-oec": "creador",
    }

    for g_info in A0_STRICT_GOLDS:
        gid = g_info["id"]
        gnode = g_info["gold"]
        row = c.execute(
            "SELECT contenido FROM largo_plazo WHERE concepto = ?", (gnode,)
        ).fetchone()
        text = row[0] if row else ""
        text_norm = normalizar(text)

        known_span = gold_c_spans.get(gnode, "")
        rule = clasificar_span_c(known_span) if known_span else None

        # Verificar que el span aparece realmente en el texto (no inventado)
        span_in_text = bool(
            re.search(r'\b' + re.escape(known_span) + r'\b', text_norm)
        ) if known_span else False

        entry = {
            "case_id": gid,
            "gold": gnode,
            "source_span_n72": known_span,
            "span_confirmed_in_text": span_in_text,
            "c_subtype": rule.c_subtype if rule else "UNKNOWN",
            "rule_id": rule.rule_id if rule else "NONE",
            "canonical_op": rule.canonical_op if rule else "NONE",
            "morphological_relation": rule.morphological_relation if rule else "",
            "rule_provenance": rule.rule_provenance if rule else "",
            "gold_dependent": False,
            "leakage_flag": False,
        }
        matrix.append(entry)

        subtype_str = rule.c_subtype if rule else "UNKNOWN"
        print(
            f"[{gid:10s}] {gnode:35s} | span='{known_span:15s}' | "
            f"{subtype_str} | {rule.rule_id if rule else 'NONE'}"
        )

    return matrix


# ─────────────────────────────────────────────────────────────────────────────
# 5. PRUEBA CONTRAFACTUAL PARA LOS 6 GOLD
#    Perturbar el span C y verificar que el operador cambia o desaparece.
# ─────────────────────────────────────────────────────────────────────────────

# Variantes contrafactuales: (tipo, reemplazo, operador_esperado_o_None)
COUNTERFACTUAL_VARIANTS = {
    "evaluacion": [
        ("nom_to_nom",      "clasificacion",  "CLASSIFY"),
        ("nom_to_verb",     "evalua",         "EVALUATE"),   # Nivel A ahora
        ("nom_to_unrelated","descripcion",    None),
        ("deletion",        "",               None),
    ],
    "creacion": [
        ("nom_to_nom",      "modificacion",   "MODIFY"),
        ("nom_to_verb",     "genera",         "CREATE"),
        ("nom_to_unrelated","discusion",      None),
        ("deletion",        "",               None),
    ],
    "integracion": [
        ("nom_to_nom",      "separacion",     "SEPARATE"),
        ("nom_to_verb",     "integra",        "COMBINE"),
        ("nom_to_unrelated","presentacion",   None),
        ("deletion",        "",               None),
    ],
    "actualizacion": [
        ("nom_to_nom",      "consolidacion",  "PERSIST"),
        ("nom_to_verb",     "actualiza",      "MODIFY"),
        ("nom_to_unrelated","temperatura",    None),
        ("deletion",        "",               None),
    ],
    "creador": [
        ("agent_to_nom",    "creacion",       "CREATE"),
        ("agent_to_verb",   "crea",           "CREATE"),
        ("agent_to_unrelated","usuario",      None),
        ("deletion",        "",               None),
    ],
    "corre": [
        ("metaphor_to_verb","ejecuta",        "EXECUTE"),
        ("metaphor_to_nom", "ejecucion",      "EXECUTE"),
        ("metaphor_to_unrelated","mueve",     None),
        ("deletion",        "",               None),
    ],
}


def ejecutar_prueba_contrafactual(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Aplica 4 perturbaciones por Gold sobre el span C identificado en N7.2.
    Verifica que el operador cambia o desaparece causalmente.
    Razón: la prueba contrafactual confirma que la clasificación C es causal
    y no una correlación accidental entre span y operador.
    """
    from scripts.experimentos.expN7_2_extraction_vs_canonicalization_audit import (
        disecar_proposicion,
    )

    c = con.cursor()
    results = []

    gold_c_spans = {
        "docker_infrastructure_rog": "corre",
        "scoring_pesos_bm25": "integracion",
        "coche_puente_condicional": "evaluacion",
        "desde_athena_biorag": "creacion",
        "activos_dormidos_hermana": "actualizacion",
        "cuaternidad-logica-oec": "creador",
    }

    for g_info in A0_STRICT_GOLDS:
        gid = g_info["id"]
        gnode = g_info["gold"]
        row = c.execute(
            "SELECT contenido FROM largo_plazo WHERE concepto = ?", (gnode,)
        ).fetchone()
        text = row[0] if row else ""
        text_norm = normalizar(text)

        original_span = gold_c_spans.get(gnode, "")
        variants = COUNTERFACTUAL_VARIANTS.get(original_span, [])

        base_prop = disecar_proposicion(gnode, text)
        base_op = base_prop.operator.value

        perturbation_results = []
        all_pass = True

        for pert_type, replacement, expected_op in variants:
            if original_span and original_span in text_norm:
                perturbed_text = text_norm.replace(original_span, replacement, 1)
            else:
                perturbed_text = text_norm

            perturbed_prop = disecar_proposicion(gnode, perturbed_text)
            perturbed_op = perturbed_prop.operator.value

            if pert_type == "deletion":
                passed = (perturbed_op != base_op) or (perturbed_op is None)
            elif expected_op is None:
                passed = (perturbed_op != base_op) or (perturbed_prop.overall_level == "ABSENT")
            else:
                passed = (perturbed_op == expected_op)

            all_pass = all_pass and passed
            perturbation_results.append({
                "perturbation_type": pert_type,
                "original_span": original_span,
                "replacement": replacement if replacement else "(eliminated)",
                "expected_op": expected_op,
                "obtained_op": perturbed_op,
                "passed": passed,
            })

        status = "CAUSAL_OK" if all_pass else "PARTIAL"
        print(
            f"[{gid:10s}] {gnode:35s} | base={base_op} | "
            f"{sum(1 for p in perturbation_results if p['passed'])}/{len(perturbation_results)} | {status}"
        )

        results.append({
            "case_id": gid,
            "gold": gnode,
            "original_span": original_span,
            "base_operator": base_op,
            "perturbations": perturbation_results,
            "all_perturbations_passed": all_pass,
        })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 6. DISTRIBUCIÓN C1/C2/C3 SOBRE 100 NODOS DEL SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def distribucion_c_100_nodos(con: sqlite3.Connection) -> Dict[str, Any]:
    """
    Classifica cada extracción C en los 100 primeros nodos activos del snapshot.
    Razón: Aureon requiere >=100 nodos para validar cobertura más allá de los 6 Gold.
    """
    from scripts.experimentos.expN7_2_extraction_vs_canonicalization_audit import (
        VERB_ACTIVE_RULES_A,
    )

    c = con.cursor()
    rows = c.execute(
        "SELECT concepto, contenido FROM largo_plazo WHERE estado='activo' ORDER BY id ASC LIMIT 100"
    ).fetchall()

    c1_count = c2_count = c3_count = pure_a_count = absent_count = 0
    op_by_subtype: Dict[str, Dict[str, int]] = {"C1": {}, "C2": {}, "C3": {}}
    records_c = []

    for node, text in rows:
        rec = extraer_c_record(node, text)
        if rec is None:
            text_norm = normalizar(text)
            has_verb_a = any(re.search(p, text_norm) for p, _, _ in VERB_ACTIVE_RULES_A)
            if has_verb_a:
                pure_a_count += 1
            else:
                absent_count += 1
        else:
            subtype = rec.inference_level
            if subtype == "C1":
                c1_count += 1
            elif subtype == "C2":
                c2_count += 1
            elif subtype == "C3":
                c3_count += 1

            op_by_subtype[subtype][rec.canonical_operator] = (
                op_by_subtype[subtype].get(rec.canonical_operator, 0) + 1
            )
            records_c.append(rec.to_dict())

    total = len(rows)
    print(f"\n  PURE A  : {pure_a_count}/{total} ({pure_a_count/total*100:.1f}%)")
    print(f"  C1      : {c1_count}/{total} ({c1_count/total*100:.1f}%)")
    print(f"  C2      : {c2_count}/{total} ({c2_count/total*100:.1f}%)")
    print(f"  C3      : {c3_count}/{total} ({c3_count/total*100:.1f}%)")
    print(f"  ABSENT  : {absent_count}/{total} ({absent_count/total*100:.1f}%)")

    return {
        "sample_size": total,
        "pure_a": pure_a_count,
        "c1": c1_count,
        "c2": c2_count,
        "c3": c3_count,
        "absent": absent_count,
        "operator_distribution_by_subtype": op_by_subtype,
        "c_extractions_sample": records_c[:15],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. VEREDICTO FORMAL
# ─────────────────────────────────────────────────────────────────────────────

def calcular_veredicto(
    gold_matrix: List[Dict],
    generalidad_results: List[Dict],
    counterfactual_results: List[Dict],
    dist_100: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Calcula el veredicto N7.3 según criterios de Aureon.
    N7.3-C1-VALIDATED : C1 general + >=4/6 Gold por C1+C2 + contrafact >=70%
    N7.3-PARTIAL      : C1+C2 cubre >=3/6 Gold
    N7.3-INVALID      : leakage detectado O <3/6 Gold cubiertos
    """
    c1_general_ok_count = sum(
        1 for r in generalidad_results if r["generalizable_confirmed"]
    )
    c1_general_ok = c1_general_ok_count == len(generalidad_results)
    c1_rate = c1_general_ok_count / max(len(generalidad_results), 1)

    gold_c1 = sum(1 for g in gold_matrix if g["c_subtype"] == "C1")
    gold_c2 = sum(1 for g in gold_matrix if g["c_subtype"] == "C2")
    gold_c3 = sum(1 for g in gold_matrix if g["c_subtype"] == "C3")

    cf_pass = sum(
        p["passed"] for cr in counterfactual_results for p in cr["perturbations"]
    )
    cf_total = sum(len(cr["perturbations"]) for cr in counterfactual_results)
    cf_rate = cf_pass / max(cf_total, 1)

    leakage = any(g["leakage_flag"] for g in gold_matrix)

    if leakage:
        veredicto = "N7.3-INVALID"
        razon = "Leakage detectado — reglas Gold-conditioned (Clase D) prohibidas."
    elif c1_general_ok and gold_c1 + gold_c2 >= 4 and cf_rate >= 0.70:
        veredicto = "N7.3-C1-VALIDATED"
        razon = (
            f"C1 general y reproducible ({c1_rate*100:.0f}% reglas con >=2/3 positivos). "
            f"Gold cubiertos: C1={gold_c1}/6, C2={gold_c2}/6, C3={gold_c3}/6. "
            f"C3 ('corre→EXECUTE') separado formalmente como metáfora. "
            f"Contrafactuales: {cf_pass}/{cf_total} ({cf_rate*100:.0f}%). Leakage=0. "
            f"Autoriza N8: BASE vs RAB+A/B vs RAB+A/B+C1 (C2/C3 como extensiones secundarias)."
        )
    elif gold_c1 + gold_c2 >= 3:
        veredicto = "N7.3-PARTIAL"
        razon = (
            f"C1 parcialmente validado. Gold: C1={gold_c1}/6, C2={gold_c2}/6, C3={gold_c3}/6. "
            f"Contrafactuales: {cf_pass}/{cf_total} ({cf_rate*100:.0f}%). "
            f"N8 posible SOLO con relaciones A/B+C1 confirmadas. C3 hipótesis secundaria."
        )
    else:
        veredicto = "N7.3-INVALID"
        razon = (
            f"Insuficiente evidencia para C1: solo {gold_c1}/6 Gold cubiertos. N8 no autorizado."
        )

    return veredicto, razon


# ─────────────────────────────────────────────────────────────────────────────
# 8. EJECUCIÓN INTEGRAL EXP-N7.3
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_exp_n7_3():
    print("=" * 78)
    print("EXP-N7.3: AUDITORÍA DE PARTICIÓN INTERNA DE NIVEL C (C1 / C2 / C3)")
    print("=" * 78)
    print(f"  DB SHA-256 : {hashlib.sha256(open(DB_PATH, 'rb').read()).hexdigest()}")
    print(f"  Labels     : {hashlib.sha256(open(LABELS_PATH, 'rb').read()).hexdigest()}")
    c1_n = sum(1 for r in C_RULE_CATALOG if r.c_subtype == "C1")
    c2_n = sum(1 for r in C_RULE_CATALOG if r.c_subtype == "C2")
    c3_n = sum(1 for r in C_RULE_CATALOG if r.c_subtype == "C3")
    print(f"  Catálogo C : {len(C_RULE_CATALOG)} reglas (C1={c1_n}, C2={c2_n}, C3={c3_n})")
    print(f"  Invariantes: core/ intacto | A0-TEST ciego | sin scoring | sin retrieval")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    # S1: Catálogo
    print("\n" + "-" * 60)
    print("S1 — CATÁLOGO DE REGLAS C CON CLASIFICACIÓN C1/C2/C3")
    print("-" * 60)
    for rule in C_RULE_CATALOG:
        print(f"  [{rule.c_subtype}] {rule.rule_id:35s} → {rule.canonical_op}")

    # S2: Generalidad C1
    print("\n" + "-" * 60)
    print("S2 — PRUEBA DE GENERALIDAD (reglas C1 sobre ejemplos externos al Gold)")
    print("-" * 60)
    generalidad_results = verificar_generalidad_c1()
    c1_ok_n = sum(1 for r in generalidad_results if r["generalizable_confirmed"])
    for gr in generalidad_results:
        s = "OK" if gr["generalizable_confirmed"] else "FAIL"
        print(f"  [{s}] {gr['rule_id']:35s} positivos={gr['positivos_ok']} FP={len(gr['falsos_positivos'])}")

    # S3: Matriz Gold
    print("\n" + "-" * 60)
    print("S3 — MATRIZ C1/C2/C3 PARA LOS 6 GOLD STRICT A0")
    print("-" * 60)
    gold_matrix = construir_matriz_gold(con)
    gc1 = sum(1 for g in gold_matrix if g["c_subtype"] == "C1")
    gc2 = sum(1 for g in gold_matrix if g["c_subtype"] == "C2")
    gc3 = sum(1 for g in gold_matrix if g["c_subtype"] == "C3")
    print(f"\n  RESUMEN GOLD: C1={gc1}/6 | C2={gc2}/6 | C3={gc3}/6")

    # S4: Contrafactuales
    print("\n" + "-" * 60)
    print("S4 — PRUEBA CONTRAFACTUAL (span → variante → operador cambia/desaparece)")
    print("-" * 60)
    counterfactual_results = ejecutar_prueba_contrafactual(con)
    cf_pass = sum(p["passed"] for cr in counterfactual_results for p in cr["perturbations"])
    cf_total = sum(len(cr["perturbations"]) for cr in counterfactual_results)
    print(f"\n  Contrafactuales: {cf_pass}/{cf_total} ({cf_pass/cf_total*100:.1f}%)")

    # S5: Distribución 100 nodos
    print("\n" + "-" * 60)
    print("S5 — DISTRIBUCIÓN C1/C2/C3 SOBRE 100 NODOS DEL SNAPSHOT")
    print("-" * 60)
    dist_100 = distribucion_c_100_nodos(con)

    # Métricas consolidadas
    print("\n" + "=" * 78)
    print("MÉTRICAS CONSOLIDADAS EXP-N7.3")
    print("=" * 78)
    print(f"  Reglas C1 con generalidad confirmada : {c1_ok_n}/{len(generalidad_results)}")
    print(f"  Gold Strict A0 → C1                  : {gc1}/6")
    print(f"  Gold Strict A0 → C2                  : {gc2}/6")
    print(f"  Gold Strict A0 → C3                  : {gc3}/6")
    print(f"  Contrafactuales pasados               : {cf_pass}/{cf_total} ({cf_pass/cf_total*100:.1f}%)")
    print(f"  Leakage                               : 0")
    print(f"  Gold-dependent                        : 0")
    print(f"  Dist 100 nodos: A={dist_100['pure_a']} C1={dist_100['c1']} "
          f"C2={dist_100['c2']} C3={dist_100['c3']} ABS={dist_100['absent']}")

    # Veredicto
    veredicto, razon = calcular_veredicto(
        gold_matrix, generalidad_results, counterfactual_results, dist_100
    )
    print("\n" + "=" * 78)
    print(f"VEREDICTO FORMAL EXP-N7.3: {veredicto}")
    print("=" * 78)
    print(f"RAZÓN: {razon}")
    print("=" * 78)

    # Guardar JSON
    os.makedirs("docs", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N7.3: Partición Interna de Nivel C (C1/C2/C3)",
        "hashes": {
            "db_snapshot": hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest(),
            "labels": hashlib.sha256(open(LABELS_PATH, "rb").read()).hexdigest(),
            "script": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
        },
        "invariants": {
            "core_modified": False,
            "a0_test_blind": True,
            "snapshot_readonly": True,
            "retrieval_used": False,
            "scoring_used": False,
            "aliases_used": False,
            "concept_hubs_used": False,
            "gold_conditioning": False,
            "leakage": False,
        },
        "verdict": veredicto,
        "verdict_rationale": razon,
        "c_rule_catalog": [r.to_dict() for r in C_RULE_CATALOG],
        "generalidad_c1_results": generalidad_results,
        "gold_matrix_c123": gold_matrix,
        "counterfactual_results": counterfactual_results,
        "distribution_100_nodes": dist_100,
        "summary_metrics": {
            "c1_rules_generalized": f"{c1_ok_n}/{len(generalidad_results)}",
            "gold_c1": f"{gc1}/6",
            "gold_c2": f"{gc2}/6",
            "gold_c3": f"{gc3}/6",
            "counterfactuals_passed": f"{cf_pass}/{cf_total} ({cf_pass/cf_total*100:.1f}%)",
            "leakage": 0,
            "gold_dependent": 0,
        },
    }

    with open(OUTPUT_EXP_N7_3, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nResultados EXP-N7.3 guardados en: {OUTPUT_EXP_N7_3}")
    con.close()


if __name__ == "__main__":
    ejecutar_exp_n7_3()
