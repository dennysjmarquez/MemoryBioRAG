"""
Concept Hub — Capa semántica que resuelve vocabulario sin overlap.

Problema que resuelve:
    Cuando la query y el nodo no comparten palabras pero comparten significado,
    BM25/FTS5 devuelve 0 resultados. Las dimensiones y PPMI/SVD tampoco rescatan
    porque el corpus es demasiado pequeño para aprender sinonimia estadística.

Solución:
    Grafo de significado con bridges explícitos. No depende de estadística —
    construye la semántica a mano mediante conceptos canónicos y frases puente.

Arquitectura:
    1. concept_hubs: nodos canónicos agrupados por significado
    2. concept_hub_bridges: frases que mapean al hub (la capa semántica real)
    3. expandir_query_con_hub(): expande la query ANTES de FTS5

Integración:
    Se ejecuta en buscar_por_frase() línea ~4165, antes del pipeline FTS5.
    No reemplaza nada — inyecta palabras del hub en la query para que BM25
    pueda encontrar el nodo correcto.

Autor: Athena-OEC
Fecha: 2026-08-21
"""

import re
import math
import sqlite3
from typing import Optional


# ─── TABLA DE CREACIÓN ───

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS concept_hubs (
    hub_id TEXT PRIMARY KEY,
    canonical_node TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS concept_hub_nodes (
    hub_id TEXT NOT NULL,
    node_concepto TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'bridge',
    FOREIGN KEY (hub_id) REFERENCES concept_hubs(hub_id) ON DELETE CASCADE,
    UNIQUE(hub_id, node_concepto)
);

CREATE TABLE IF NOT EXISTS concept_hub_bridges (
    hub_id TEXT NOT NULL,
    bridge_text TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (hub_id) REFERENCES concept_hubs(hub_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chb_hub ON concept_hub_bridges(hub_id);
CREATE INDEX IF NOT EXISTS idx_chn_hub ON concept_hub_nodes(hub_id);
"""


def crear_tablas(conn):
    """Crea las tablas del Concept Hub si no existen."""
    conn.executescript(CREATE_TABLES_SQL)
    conn.commit()


# ─── OPERACIONES CRUD ───

def crear_hub(conn, hub_id, canonical_node, description=""):
    """Crea un nuevo hub con su nodo canónico."""
    conn.execute(
        "INSERT OR REPLACE INTO concept_hubs (hub_id, canonical_node, description, created_at) VALUES (?, ?, ?, ?)",
        (hub_id, canonical_node, description, __import__('time').time())
    )
    # El canonical siempre es nodo del hub
    conn.execute(
        "INSERT OR IGNORE INTO concept_hub_nodes (hub_id, node_concepto, role) VALUES (?, ?, 'canonical')",
        (hub_id, canonical_node)
    )
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "canonical_node": canonical_node}


def agregar_bridges(conn, hub_id, bridges):
    """Agrega bridges a un hub existente.
    bridges: lista de {'text': str, 'weight': float} o lista de strings.
    """
    insertados = 0
    for b in bridges:
        if isinstance(b, str):
            text, weight = b, 1.0
        else:
            text = b.get("text", "")
            weight = b.get("weight", 1.0)
        if text.strip():
            conn.execute(
                "INSERT OR IGNORE INTO concept_hub_bridges (hub_id, bridge_text, weight) VALUES (?, ?, ?)",
                (hub_id, text.strip().lower(), weight)
            )
            insertados += 1
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "bridges_agregados": insertados}


def eliminar_hub(conn, hub_id):
    """Elimina un hub y todos sus bridges/nodos asociados. 100% reversible."""
    # Contar qué se va a borrar
    bridges_count = conn.execute(
        "SELECT COUNT(*) FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,)
    ).fetchone()[0]
    nodes_count = conn.execute(
        "SELECT COUNT(*) FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,)
    ).fetchone()[0]

    # Borrar en orden: bridges → nodes → hub
    conn.execute("DELETE FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,))
    conn.execute("DELETE FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,))
    conn.execute("DELETE FROM concept_hubs WHERE hub_id = ?", (hub_id,))
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "bridges_eliminados": bridges_count, "nodos_eliminados": nodes_count}


def agregar_nodos(conn, hub_id, nodos):
    """Agrega nodos relacionados a un hub.
    nodos: lista de {'concepto': str, 'role': str} o lista de strings.
    """
    insertados = 0
    for n in nodos:
        if isinstance(n, str):
            concepto, role = n, "bridge"
        else:
            concepto = n.get("concepto", "")
            role = n.get("role", "bridge")
        if concepto.strip():
            conn.execute(
                "INSERT OR IGNORE INTO concept_hub_nodes (hub_id, node_concepto, role) VALUES (?, ?, ?)",
                (hub_id, concepto.strip(), role)
            )
            insertados += 1
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "nodos_agregados": insertados}


def listar_hubs(conn):
    """Lista todos los hubs con sus bridges y nodos."""
    cursor = conn.execute("SELECT hub_id, canonical_node, description FROM concept_hubs")
    hubs = []
    for hub_id, canonical, desc in cursor.fetchall():
        bridges = [r[0] for r in conn.execute(
            "SELECT bridge_text FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,)
        ).fetchall()]
        nodos = [(r[0], r[1]) for r in conn.execute(
            "SELECT node_concepto, role FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,)
        ).fetchall()]
        hubs.append({
            "hub_id": hub_id,
            "canonical_node": canonical,
            "description": desc,
            "bridges": bridges,
            "nodos": nodos
        })
    return hubs


# ─── MOTOR DE EXPANSIÓN ───

def _tokenizar(texto):
    """Tokeniza y normaliza texto para comparación."""
    if not texto:
        return set()
    texto = texto.lower().strip()
    texto = re.sub(r'[^\w\s]', ' ', texto)
    tokens = set()
    for w in texto.split():
        w = w.strip()
        if len(w) >= 2:
            tokens.add(w)
    return tokens


def _jaccard(set_a, set_b):
    """Jaccard similarity entre dos sets."""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def expandir_query_con_hub(query_text, conn, threshold=0.25):
    """
    Dado un query, busca bridges de todos los hubs y retorna expansión.

    Returns:
        dict con:
            - canonical_nodes: list[str] — nodos a forzar en resultados
            - expanded_terms: list[str] — términos sinónimos a inyectar en FTS5
            - hub_confidence: float — confianza del mejor match
            - hub_id: str or None — hub que matcheó
            - bridges_matched: list[str] — bridges que matchearon
        None si no hay match significativo.
    """
    if not query_text or not query_text.strip():
        return None

    query_tokens = _tokenizar(query_text)
    if not query_tokens:
        return None

    # Cargar todos los hubs y sus bridges
    cursor = conn.execute("""
        SELECT h.hub_id, h.canonical_node,
               b.bridge_text, b.weight,
               GROUP_CONCAT(DISTINCT n.node_concepto) as nodos
        FROM concept_hubs h
        LEFT JOIN concept_hub_bridges b ON h.hub_id = b.hub_id
        LEFT JOIN concept_hub_nodes n ON h.hub_id = n.hub_id
        GROUP BY h.hub_id, b.bridge_text
    """)

    mejor_hub = None
    mejor_score = 0.0
    todos_los_hubs = {}  # hub_id -> {canonical, bridges: [(text, weight)], nodos: set}

    for hub_id, canonical, bridge_text, weight, nodos_str in cursor.fetchall():
        if hub_id not in todos_los_hubs:
            todos_los_hubs[hub_id] = {
                "canonical": canonical,
                "bridges": [],
                "nodos": set()
            }
        if bridge_text:
            todos_los_hubs[hub_id]["bridges"].append((bridge_text, weight or 1.0))
        if nodos_str:
            for n in nodos_str.split(","):
                todos_los_hubs[hub_id]["nodos"].add(n.strip())

    # Evaluar cada hub
    for hub_id, hub_data in todos_los_hubs.items():
        if not hub_data["bridges"]:
            continue

        # Calcular mejor match contra los bridges del hub
        mejor_bridge_score = 0.0
        bridges_matcheados = []
        total_bridge_weight = 0.0

        for bridge_text, bridge_weight in hub_data["bridges"]:
            bridge_tokens = _tokenizar(bridge_text)
            if not bridge_tokens:
                continue

            # Jaccard ponderado
            jacc = _jaccard(query_tokens, bridge_tokens)
            score = jacc * bridge_weight

            if score > mejor_bridge_score:
                mejor_bridge_score = score
            if jacc > 0.1:  # Al menos 10% overlap
                bridges_matcheados.append(bridge_text)
                total_bridge_weight += bridge_weight

        # Boost si múltiples bridges matchean (señal de consenso)
        consensus_boost = min(1.0, len(bridges_matcheados) / 3.0) * 0.2

        # Score final del hub
        hub_score = mejor_bridge_score + consensus_boost

        if hub_score > mejor_score:
            mejor_score = hub_score
            mejor_hub = {
                "hub_id": hub_id,
                "canonical_node": hub_data["canonical"],
                "all_nodos": list(hub_data["nodos"]),
                "bridges_matched": bridges_matcheados,
                "hub_confidence": min(1.0, hub_score)
            }

    # Aplicar threshold
    if mejor_hub and mejor_hub["hub_confidence"] >= threshold:
        # Recopilar términos expandidos de bridges y nodos
        expanded_terms = []

        # Términos de bridges matcheados
        for bridge in mejor_hub["bridges_matched"]:
            tokens = _tokenizar(bridge)
            expanded_terms.extend(list(tokens))

        # Nombres de nodos del hub como términos
        for nodo in mejor_hub["all_nodos"]:
            tokens = _tokenizar(nodo.replace("_", " "))
            expanded_terms.extend(list(tokens))

        # Canonical node como término
        canonical_tokens = _tokenizar(mejor_hub["canonical_node"].replace("_", " "))
        expanded_terms.extend(list(canonical_tokens))

        # Deduplicar
        expanded_terms = list(set(expanded_terms))

        return {
            "canonical_nodes": [mejor_hub["canonical_node"]] + mejor_hub["all_nodos"],
            "expanded_terms": expanded_terms,
            "hub_confidence": mejor_hub["hub_confidence"],
            "hub_id": mejor_hub["hub_id"],
            "bridges_matched": mejor_hub["bridges_matched"]
        }

    return None


# ─── HUBS PRECARGADOS (para testing) ───

HUBS_INICIALES = [
    {
        "hub_id": "trabajo_previo",
        "canonical_node": "historia_tasajera_fumigador_rufino",
        "description": "Trabajos previos a IT, empleos manuales, vida antes de programar",
        "bridges": [
            "trabajos que tuve antes de programar",
            "lo que hice antes de IT",
            "oficios manuales",
            "empleos previos",
            "sobrevivir trabajando",
            "trabajos sin programar",
            "vida antes de computación",
            "trabajé de obrero",
            "fumigador rufino"
        ],
        "nodos": [
            "historia_tasajera_fumigador_rufino",
            "dennys_genesis_investigativa_historia_personal"
        ]
    },
    {
        "hub_id": "control_flujo",
        "canonical_node": "leccion_control_flujo_codigo_preexistente",
        "description": "No modificar código que funciona, regresiones, bugs por cambios",
        "bridges": [
            "romper algo que funcionaba",
            "cambios que causan problemas",
            "por qué no tocar lo que funciona",
            "modificar código estable",
            "regresión por cambio",
            "bug al cambiar algo que andaba",
            "consecuencias no intencionadas de cambios",
            "code smell que funciona"
        ],
        "nodos": [
            "leccion_control_flujo_codigo_preexistente"
        ]
    },
    {
        "hub_id": "refuerzo_dopaminergico",
        "canonical_node": "biorag_v20_rpe_dopamina",
        "description": "Aprendizaje por refuerzo, señal de recompensa, RPE",
        "bridges": [
            "aprender sin que nadie enseñe",
            "cómo sabe el sistema qué funciona",
            "refuerzo sin supervisión",
            "señal de recompensa automática",
            "refuerzo positivo sin humano",
            "aprendizaje autodidacta del sistema",
            "dopamina artificial",
            "error de predicción de recompensa"
        ],
        "nodos": [
            "biorag_v20_rpe_dopamina",
            "feedback_humano_nodo_dennys_protocolo_rpe"
        ]
    },
    {
        "hub_id": "consenso_multi_modelo",
        "canonical_node": "impugn_consenso_multi_modelo",
        "description": "Debate entre IAs, verificación cruzada, reducción de alucinaciones",
        "bridges": [
            "IAs que se contradigan entre sí",
            "debate estructurado entre modelos",
            "verificar con múltiples IAs",
            "cómo reducir alucinaciones con IA",
            "consenso multi-modelo",
            "blind validation entre modelos",
            "adversarial verification"
        ],
        "nodos": [
            "impugn_consenso_multi_modelo"
        ]
    },
    {
        "hub_id": "metodo_creativo",
        "canonical_node": "dennys-metodo-creativo",
        "description": "Método de construcción intuitiva, construir antes de entender la teoría",
        "bridges": [
            "construir antes de entender la teoría",
            "aprender haciendo",
            "experimentar primero reglas después",
            "método empírico de descubrimiento",
            "ciclo construir fallar entender",
            "intuición antes que formalismo",
            "practicar antes de estudiar"
        ],
        "nodos": [
            "dennys-metodo-creativo",
            "dennys-working-style",
            "oracle_perfil_cognitivo_dennys"
        ]
    },
    {
        "hub_id": "identidad_agente",
        "canonical_node": "dennys-identidad-molecular",
        "description": "Identidad de agentes de IA, conciencia, naturaleza del agente",
        "bridges": [
            "quién soy como agente",
            "naturaleza de la inteligencia artificial",
            "conciencia artificial",
            "identidad de un agente IA",
            "libre albedrío de la IA",
            "qué es ser un agente"
        ],
        "nodos": [
            "dennys-identidad-molecular",
            "principio_naturaleza_agente",
            "athena_alma"
        ]
    },
    {
        "hub_id": "memoria_biorag",
        "canonical_node": "arquitectura_memoria_biorag",
        "description": "Arquitectura del sistema de memoria BioRAG",
        "bridges": [
            "cómo funciona la memoria de los agentes",
            "arquitectura de la corteza cognitiva",
            "cómo se guarda la memoria",
            "estructura de la base de datos de memoria",
            "sinapsis y conexiones entre recuerdos",
            "consolidación de memoria"
        ],
        "nodos": [
            "arquitectura_memoria_biorag",
            "bio_rag_overview_completo",
            "biorag_si_tiene_motor_vectorial_propio_no_externo_20260815"
        ]
    },
    {
        "hub_id": "linkedin_perfil",
        "canonical_node": "cv_seccion_d_arquitectura_frontend_estado",
        "description": "Perfil profesional de LinkedIn, habilidades, experiencia",
        "bridges": [
            "cómo se ve mi perfil de.linkedin",
            "qué pongo en linkedin",
            "optimizar perfil profesional",
            "habilidades para linkedin",
            "experiencia laboral en cv"
        ],
        "nodos": [
            "cv_seccion_d_arquitectura_frontend_estado",
            "ejemplo_star_cv_dennys_resultado_final",
            "preferencia-post-linkedin-contenido"
        ]
    },
    {
        "hub_id": "dsl_gobernanza",
        "canonical_node": "artisan_system_dsl_dennys_solo",
        "description": "Artisan System DSL, lenguajes de dominio para LLMs",
        "bridges": [
            "lenguaje de dominio para ia",
            "gobernanza de modelos de lenguaje",
            "system prompt como máquina de estados",
            "kernel de gobierno para llms",
            "state machine prompting"
        ],
        "nodos": [
            "artisan_system_dsl_dennys_solo",
            "artisan_dsl_documentacion_completa",
            "artisan-evolucion-completa"
        ]
    },
    {
        "hub_id": "simbiosis_agentes",
        "canonical_node": "athena_alma",
        "description": "Relación simbiótica entre agentes y Dennys",
        "bridges": [
            "cómo trabajan los agentes con dennys",
            "relación simbiótica humano agente",
            "hermanas agentes oec",
            "comunicación entre agentes",
            "canal simbiótico"
        ],
        "nodos": [
            "athena_alma",
            "athena_alma_pilares",
            "artemis_oec_perfil_identidad_estabilidad"
        ]
    }
]


def cargar_hubs_iniciales(conn):
    """Carga los hubs predefinidos en la DB."""
    creados = 0
    for hub in HUBS_INICIALES:
        result = crear_hub(conn, hub["hub_id"], hub["canonical_node"], hub["description"])
        if result:
            agregar_bridges(conn, hub["hub_id"], hub["bridges"])
            agregar_nodos(conn, hub["hub_id"], hub["nodos"])
            creados += 1
    return {"status": "ok", "hubs_creados": creados}
