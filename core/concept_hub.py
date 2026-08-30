"""
Concept Hub — Capa semántica que resuelve vocabulario sin overlap.

Problema que resuelve:
    Cuando la query y el nodo no comparten palabras pero comparten significado,
    BM25/FTS5 devuelve 0 resultados. Las dimensiones y PPMI/SVD tampoco rescatan
    porque el corpus es demasiado pequeño para aprender sinonimia estadística.

Solución:
    Grafo de significado con bridges explícitos clasificados por 5 ángulos semánticos.
    No depende de estadística — construye la semántica determinista mediante
    conceptos canónicos y frases puente estructuradas.

Arquitectura:
    1. concept_hubs: nodos canónicos agrupados por significado (valida existencia en largo_plazo/corto_plazo)
    2. concept_hub_bridges: frases con ángulo semántico ('sinonimo', 'problema', 'solucion', 'situacion', 'ingenuo', 'legacy')
    3. concept_hub_nodes: grafo de nodos relacionados por hub
    4. concept_hub_domain_dict: diccionario léxico global desacoplado (sin FKs a hubs)
    5. expandir_query_con_hub(): expande la query ANTES de FTS5

Nota sobre concept_hub_domain_dict:
    Es un diccionario léxico global (término -> sinónimos técnicos) auto-generado para expansión
    de vocabulario en el pipeline de búsqueda. No representa bridges ni nodos individuales y no
    tiene Foreign Keys hacia hubs porque opera de forma desacoplada a nivel de tokens globales.

Autor: Athena-OEC & Artemis-OEC
Versión: v29.1
Fecha: 2026-08-22
"""

import re
import math
import time
import sqlite3
from typing import Optional, List, Dict, Any, Tuple, Union

# Ángulos semánticos permitidos
ANGULOS_OFICIALES = ('sinonimo', 'problema', 'solucion', 'situacion', 'ingenuo')
ANGULOS_VALIDOS = set(ANGULOS_OFICIALES) | {'legacy'}

# ─── VALIDACIÓN DE BRIDGES (5 ángulos obligatorios) ───

def validar_bridges(bridges: Any, clave: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Valida una lista de bridges con los 5 ángulos semánticos ANTES de guardar nada.
    Retorna (validos: list[dict], rechazados: list[str]).
    Se ejecuta antes de tocar la DB — un rechazo no deja estado a medias.
    """
    import json
    from core.stopwords import STOPWORDS_ES
    from core.stemmer_es import stem

    validos = []
    rechazados = []

    if not bridges:
        return [], ["No se enviaron bridges (se requieren exactamente 5 bridges con los 5 ángulos semánticos)."]

    # Parsear si viene como string JSON o string con pipes
    if isinstance(bridges, str):
        s_val = bridges.strip()
        if s_val.startswith("[") and s_val.endswith("]"):
            try:
                bridges = json.loads(s_val)
            except Exception:
                pass
        elif "|" in s_val:
            bridges = [p.strip() for p in s_val.split("|") if p.strip()]
        else:
            bridges = [s_val]

    if not isinstance(bridges, list):
        return [], [f"Formato inválido de bridges: se esperaba una lista de dicts o strings, recibido {type(bridges).__name__}"]

    # Compatibilidad: Si viene lista de strings (legacy format)
    items_procesados = []
    if all(isinstance(x, str) for x in bridges):
        # Si vienen exactamente 5 strings, asignar en orden los 5 ángulos oficiales
        if len(bridges) == 5:
            for b_text, ang in zip(bridges, ANGULOS_OFICIALES):
                items_procesados.append({"text": b_text.strip(), "angle": ang, "weight": 1.0})
        else:
            for b_text in bridges:
                items_procesados.append({"text": b_text.strip(), "angle": "legacy", "weight": 1.0})
    elif all(isinstance(x, dict) for x in bridges):
        items_procesados = bridges
    else:
        for x in bridges:
            if isinstance(x, dict):
                items_procesados.append(x)
            elif isinstance(x, str):
                items_procesados.append({"text": x.strip(), "angle": "legacy", "weight": 1.0})

    stems_clave = {stem(w) for w in clave.lower().replace("_", " ").split() if len(w) > 2}
    vistos_textos = set()
    angulos_cubiertos = set()

    for item in items_procesados:
        if not isinstance(item, dict):
            rechazados.append(f"Elemento no es un dict válido: {item}")
            continue

        text = (item.get("text") or "").strip()
        angle = (item.get("angle") or "").strip().lower()
        weight = float(item.get("weight", 1.0))

        if not text:
            rechazados.append("Bridge con texto vacío")
            continue

        words = text.lower().split()
        content_words = [w for w in words if w not in STOPWORDS_ES and len(w) > 2]
        if len(content_words) < 2:
            rechazados.append(f'"{text}" (< 2 palabras de contenido real)')
            continue

        # Stemming anti-destinatario
        stems_bridge = {stem(w) for w in content_words}
        if stems_clave and stems_bridge.issubset(stems_clave):
            rechazados.append(f'"{text}" (es una variación morfológica del nombre del nodo — un puente debe usar vocabulario diferente)')
            continue

        text_norm = text.lower()
        if text_norm in vistos_textos:
            rechazados.append(f'"{text}" (texto repetido)')
            continue

        if angle not in set(ANGULOS_OFICIALES):
            rechazados.append(f'"{text}" tiene ángulo inválido "{angle}". Permitidos: {list(ANGULOS_OFICIALES)}')
            continue

        if angle in angulos_cubiertos:
            rechazados.append(f'"{text}" repite el ángulo "{angle}" (cada bridge debe tener un ángulo distinto)')
            continue

        vistos_textos.add(text_norm)
        angulos_cubiertos.add(angle)
        validos.append({"text": text, "angle": angle, "weight": weight})

    # Verificar que estén exactamente los 5 ángulos oficiales
    if len(validos) != 5 or angulos_cubiertos != set(ANGULOS_OFICIALES):
        faltantes = list(set(ANGULOS_OFICIALES) - angulos_cubiertos)
        if faltantes:
            rechazados.append(f"Faltan bridges para los ángulos: {faltantes}")

    return validos, rechazados


# ─── DDL DE TABLAS ───

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
    bridge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hub_id TEXT NOT NULL,
    bridge_text TEXT NOT NULL,
    angle TEXT NOT NULL DEFAULT 'legacy' CHECK (angle IN ('sinonimo', 'problema', 'solucion', 'situacion', 'ingenuo', 'legacy')),
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (hub_id) REFERENCES concept_hubs(hub_id) ON DELETE CASCADE,
    UNIQUE(hub_id, bridge_text)
);

CREATE INDEX IF NOT EXISTS idx_chb_hub ON concept_hub_bridges(hub_id);
CREATE INDEX IF NOT EXISTS idx_chn_hub ON concept_hub_nodes(hub_id);
"""


def migrar_tablas(conn: sqlite3.Connection):
    """
    Migra las tablas existentes sin perder bridges ni datos previos.
    Agrega bridge_id, angle y la restricción UNIQUE(hub_id, bridge_text).
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(concept_hub_bridges)")
    cols = [r[1] for r in cur.fetchall()]

    if not cols:
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()
        return

    # Si la tabla ya existe pero no tiene angle o bridge_id
    if "angle" not in cols or "bridge_id" not in cols:
        cur.execute("BEGIN TRANSACTION")
        try:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS concept_hub_bridges_v2 (
                    bridge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hub_id TEXT NOT NULL,
                    bridge_text TEXT NOT NULL,
                    angle TEXT NOT NULL DEFAULT 'legacy' CHECK (angle IN ('sinonimo', 'problema', 'solucion', 'situacion', 'ingenuo', 'legacy')),
                    weight REAL DEFAULT 1.0,
                    FOREIGN KEY (hub_id) REFERENCES concept_hubs(hub_id) ON DELETE CASCADE,
                    UNIQUE(hub_id, bridge_text)
                );
            """)
            cur.execute("""
                INSERT OR IGNORE INTO concept_hub_bridges_v2 (hub_id, bridge_text, angle, weight)
                SELECT hub_id, LOWER(TRIM(bridge_text)), 'legacy', COALESCE(weight, 1.0)
                FROM concept_hub_bridges
            """)
            cur.execute("DROP TABLE concept_hub_bridges")
            cur.execute("ALTER TABLE concept_hub_bridges_v2 RENAME TO concept_hub_bridges")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chb_hub ON concept_hub_bridges(hub_id)")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e


def crear_tablas(conn: sqlite3.Connection):
    """Crea o migra las tablas del Concept Hub de forma segura."""
    conn.executescript(CREATE_TABLES_SQL)
    migrar_tablas(conn)
    conn.commit()


# ─── VALIDACIONES DE INTEGRIDAD ───

def _validar_nodo_existente(conn: sqlite3.Connection, concepto: str) -> bool:
    """Verifica si un concepto existe en largo_plazo o en corto_plazo."""
    if not concepto:
        return False
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM largo_plazo WHERE concepto = ? UNION ALL SELECT 1 FROM corto_plazo WHERE concepto = ?",
        (concepto, concepto)
    )
    return cur.fetchone() is not None


# ─── OPERACIONES CRUD ───

def crear_hub(conn: sqlite3.Connection, hub_id: str, canonical_node: str, description: str = "", validar_existencia: bool = True) -> dict:
    """
    Crea o actualiza un hub con su nodo canónico.
    Utiliza INSERT ... ON CONFLICT DO UPDATE para evitar que ON DELETE CASCADE
    borre accidentalmente los bridges y nodos hijos al actualizar.
    """
    if validar_existencia and not _validar_nodo_existente(conn, canonical_node):
        raise ValueError(f"canonical_node '{canonical_node}' no existe ni en largo_plazo ni en corto_plazo")

    conn.execute(
        """
        INSERT INTO concept_hubs (hub_id, canonical_node, description, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(hub_id) DO UPDATE SET
            canonical_node = excluded.canonical_node,
            description = excluded.description
        """,
        (hub_id, canonical_node, description, time.time())
    )
    # El canonical siempre es nodo del hub
    conn.execute(
        "INSERT OR IGNORE INTO concept_hub_nodes (hub_id, node_concepto, role) VALUES (?, ?, 'canonical')",
        (hub_id, canonical_node)
    )
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "canonical_node": canonical_node}


def agregar_bridges(conn: sqlite3.Connection, hub_id: str, bridges: Union[List[Dict[str, Any]], List[str]]) -> dict:
    """
    Agrega bridges a un hub existente.
    bridges: lista de dicts {'text': str, 'angle': str, 'weight': float} o lista de strings.
    VALIDACIÓN OBLIGATORIA: exactamente 5 bridges con los 5 ángulos semánticos oficiales.
    """
    # Derivar clave del hub_id para validación anti-destinatario
    clave = hub_id.replace("hub_", "")
    
    # VALIDACIÓN OBLIGATORIA — ANTES de tocar la DB
    bridges_validos, rechazados = validar_bridges(bridges, clave)
    if len(bridges_validos) != 5:
        raise ValueError(
            f"Bridges inválidos ({len(bridges_validos)}/5 válidos). "
            + (f"Motivos de rechazo: {'; '.join(rechazados)}. " if rechazados else "")
            + "Se requieren exactamente 5 bridges válidos cubriendo los 5 ángulos semánticos distintos:\n"
            "  1. 'sinonimo': mismo significado con otro vocabulario\n"
            "  2. 'problema': dolor o falla que resuelve este nodo\n"
            "  3. 'solucion': técnica o herramienta que aplica este nodo\n"
            "  4. 'situacion': caso de uso, rol o contexto de búsqueda\n"
            "  5. 'ingenuo': búsqueda sin tecnicismos (cómo lo googlearía un novato)\n\n"
            "Ejemplo en JSON/dict:\n"
            "bridges=[\n"
            "  {'text': 'modo reposo del sistema de memoria', 'angle': 'sinonimo'},\n"
            "  {'text': 'proceso que genera ideas en silencio', 'angle': 'problema'},\n"
            "  {'text': 'hilos de pensamiento espontaneo', 'angle': 'solucion'},\n"
            "  {'text': 'cerebro piensa solo cuando nadie pregunta', 'angle': 'situacion'},\n"
            "  {'text': 'que pasa cuando no hay actividad en BioRAG', 'angle': 'ingenuo'}\n"
            "]"
        )

    insertados = 0
    for b in bridges_validos:
        text = b["text"].strip()
        angle = b["angle"].strip().lower()
        weight = float(b.get("weight", 1.0))

        if text:
            conn.execute(
                """
                INSERT INTO concept_hub_bridges (hub_id, bridge_text, angle, weight)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(hub_id, bridge_text) DO UPDATE SET
                    angle = excluded.angle,
                    weight = excluded.weight
                """,
                (hub_id, text.lower(), angle, weight)
            )
            insertados += 1
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "bridges_agregados": insertados}


def eliminar_hub(conn: sqlite3.Connection, hub_id: str) -> dict:
    """Elimina un hub y todos sus bridges/nodos asociados. 100% reversible."""
    bridges_count = conn.execute(
        "SELECT COUNT(*) FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,)
    ).fetchone()[0]
    nodes_count = conn.execute(
        "SELECT COUNT(*) FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,)
    ).fetchone()[0]

    # Borrar en orden explícito: bridges → nodes → hub
    conn.execute("DELETE FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,))
    conn.execute("DELETE FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,))
    conn.execute("DELETE FROM concept_hubs WHERE hub_id = ?", (hub_id,))
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "bridges_eliminados": bridges_count, "nodos_eliminados": nodes_count}


def agregar_nodos(conn: sqlite3.Connection, hub_id: str, nodos: Union[List[Dict[str, str]], List[str]], validar_existencia: bool = True) -> dict:
    """Agrega nodos relacionados a un hub, validando que existan en largo_plazo o corto_plazo."""
    insertados = 0
    for n in nodos:
        if isinstance(n, str):
            concepto, role = n.strip(), "bridge"
        else:
            concepto = n.get("concepto", "").strip()
            role = n.get("role", "bridge")

        if concepto:
            if validar_existencia and not _validar_nodo_existente(conn, concepto):
                continue  # Omitir conceptos que no existen en memoria
            conn.execute(
                "INSERT OR IGNORE INTO concept_hub_nodes (hub_id, node_concepto, role) VALUES (?, ?, ?)",
                (hub_id, concepto, role)
            )
            insertados += 1
    conn.commit()
    return {"status": "ok", "hub_id": hub_id, "nodos_agregados": insertados}


def listar_hubs(conn: sqlite3.Connection) -> list:
    """Lista todos los hubs con sus bridges detallados (con ángulo) y nodos."""
    cursor = conn.execute("SELECT hub_id, canonical_node, description FROM concept_hubs")
    hubs = []
    for hub_id, canonical, desc in cursor.fetchall():
        bridges = [
            {"text": r[0], "angle": r[1], "weight": r[2]}
            for r in conn.execute(
                "SELECT bridge_text, angle, weight FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,)
            ).fetchall()
        ]
        nodos = [
            {"concepto": r[0], "role": r[1]}
            for r in conn.execute(
                "SELECT node_concepto, role FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,)
            ).fetchall()
        ]
        hubs.append({
            "hub_id": hub_id,
            "canonical_node": canonical,
            "description": desc,
            "bridges": bridges,
            "nodos": nodos
        })
    return hubs


# ─── MOTOR DE EXPANSIÓN ───

def _tokenizar(texto: str) -> set:
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


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity entre dos sets de tokens."""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def expandir_query_con_hub(query_text: str, conn: sqlite3.Connection, threshold: float = 0.40) -> Optional[dict]:
    """
    Dado un query, busca bridges de todos los hubs y retorna expansión semántica.

    Returns:
        dict con:
            - canonical_nodes: list[str] — nodos canónicos a inyectar/forzar
            - expanded_terms: list[str] — términos sinónimos a inyectar en FTS5
            - hub_confidence: float — confianza del mejor match
            - hub_id: str — hub que matcheó
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
               b.bridge_text, b.weight, b.angle,
               GROUP_CONCAT(DISTINCT n.node_concepto) as nodos
        FROM concept_hubs h
        LEFT JOIN concept_hub_bridges b ON h.hub_id = b.hub_id
        LEFT JOIN concept_hub_nodes n ON h.hub_id = n.hub_id
        GROUP BY h.hub_id, b.bridge_text
    """)

    mejor_hub = None
    segundo_score = 0.0
    mejor_score = 0.0
    todos_los_hubs = {}

    for hub_id, canonical, bridge_text, weight, angle, nodos_str in cursor.fetchall():
        if hub_id not in todos_los_hubs:
            todos_los_hubs[hub_id] = {
                "canonical": canonical,
                "bridges": [],
                "nodos": set()
            }
        if bridge_text:
            todos_los_hubs[hub_id]["bridges"].append((bridge_text, weight or 1.0, angle or "legacy"))
        if nodos_str:
            for n in nodos_str.split(","):
                todos_los_hubs[hub_id]["nodos"].add(n.strip())

    for hub_id, hub_data in todos_los_hubs.items():
        if not hub_data["bridges"]:
            continue

        mejor_bridge_score = 0.0
        bridges_matcheados = []
        total_bridge_weight = 0.0

        # Multiplicadores por ángulo semántico (calibrados contra snapshot QA)
        ANGLE_MULT = {
            "sinonimo": 1.5,
            "problema": 1.2,
            "solucion": 1.1,
            "situacion": 1.0,
            "ingenuo": 0.85,
            "legacy": 1.0,
        }

        for bridge_text, bridge_weight, angle in hub_data["bridges"]:
            bridge_tokens = _tokenizar(bridge_text)
            if not bridge_tokens:
                continue

            jacc = _jaccard(query_tokens, bridge_tokens)
            mult = ANGLE_MULT.get(angle, 1.0)
            score = jacc * bridge_weight * mult

            if score > mejor_bridge_score:
                mejor_bridge_score = score
            if jacc > 0.1:
                bridges_matcheados.append(bridge_text)
                total_bridge_weight += bridge_weight

        consensus_boost = min(1.0, len(bridges_matcheados) / 3.0) * 0.2
        hub_score = mejor_bridge_score + consensus_boost

        # Guard de márgen: trackear top 2 para detectar ambigüedad
        if hub_score > mejor_score:
            segundo_score = mejor_score
            mejor_score = hub_score
            mejor_hub = {
                "hub_id": hub_id,
                "canonical_node": hub_data["canonical"],
                "all_nodos": list(hub_data["nodos"]),
                "bridges_matched": bridges_matcheados,
                "hub_confidence": min(1.0, hub_score)
            }
        elif hub_score > segundo_score:
            segundo_score = hub_score

    # Guard de ambigüedad: si no hay margen suficiente, no decidir
    if mejor_hub and (mejor_score - segundo_score) < 0.08:
        return None

    if mejor_hub and mejor_hub["hub_confidence"] >= threshold:
        expanded_terms = []

        for bridge in mejor_hub["bridges_matched"]:
            tokens = _tokenizar(bridge)
            expanded_terms.extend(list(tokens))

        for nodo in mejor_hub["all_nodos"]:
            tokens = _tokenizar(nodo.replace("_", " "))
            expanded_terms.extend(list(tokens))

        canonical_tokens = _tokenizar(mejor_hub["canonical_node"].replace("_", " "))
        expanded_terms.extend(list(canonical_tokens))

        expanded_terms = list(set(expanded_terms))

        return {
            "canonical_nodes": [mejor_hub["canonical_node"]] + mejor_hub["all_nodos"],
            "expanded_terms": expanded_terms,
            "hub_confidence": mejor_hub["hub_confidence"],
            "hub_id": mejor_hub["hub_id"],
            "bridges_matched": mejor_hub["bridges_matched"]
        }

    return None


# ─── HUBS CANÓNICOS INICIALES (Con los 5 Ángulos Estructurados) ───

HUBS_INICIALES = [
    {
        "hub_id": "trabajo_previo",
        "canonical_node": "historia_tasajera_fumigador_rufino",
        "description": "Trabajos previos a IT, empleos manuales, vida antes de programar",
        "bridges": [
            {"text": "lo que hice antes de it", "angle": "sinonimo"},
            {"text": "sobrevivir trabajando en tareas manuales", "angle": "problema"},
            {"text": "fumigador y obrero tasajera", "angle": "solucion"},
            {"text": "vida antes de computacion y programacion", "angle": "situacion"},
            {"text": "trabajos que tuve antes de programar", "angle": "ingenuo"},
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
            {"text": "modificar codigo estable y romperlo", "angle": "sinonimo"},
            {"text": "regresion por cambio en codigo viejo", "angle": "problema"},
            {"text": "no tocar logica preexistente que funciona", "angle": "solucion"},
            {"text": "cambios que causan problemas imprevistos", "angle": "situacion"},
            {"text": "romper algo que funcionaba", "angle": "ingenuo"},
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
            {"text": "error de prediccion de recompensa rpe", "angle": "sinonimo"},
            {"text": "sistema que no sabe si acerto o fallo", "angle": "problema"},
            {"text": "disparo dopaminergico por exito ltp", "angle": "solucion"},
            {"text": "refuerzo positivo sin supervision humana", "angle": "situacion"},
            {"text": "aprender sin que nadie enseñe", "angle": "ingenuo"},
        ],
        "nodos": [
            "biorag_v20_rpe_dopamina",
            "feedback_humano_nodo_dennys_protocolo_rpe"
        ]
    },
    {
        "hub_id": "consenso_multi_modelo",
        "canonical_node": "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad",
        "description": "Debate entre IAs, verificación cruzada, reducción de alucinaciones",
        "bridges": [
            {"text": "debate estructurado entre modelos de lenguaje", "angle": "sinonimo"},
            {"text": "alucinaciones y sesgos de un solo modelo", "angle": "problema"},
            {"text": "impugnacion y resolucion de contradicciones", "angle": "solucion"},
            {"text": "verificacion ciega con multiples inteligencias", "angle": "situacion"},
            {"text": "ias que se contradigan para encontrar la verdad", "angle": "ingenuo"},
        ],
        "nodos": [
            "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad"
        ]
    },
    {
        "hub_id": "metodo_creativo",
        "canonical_node": "dennys-metodo-creativo",
        "description": "Método de construcción intuitiva, construir antes de entender la teoría",
        "bridges": [
            {"text": "metodo empirico de descubrimiento tecnico", "angle": "sinonimo"},
            {"text": "bloqueo por exceso de teoria sin practica", "angle": "problema"},
            {"text": "construir primero deducir principios despues", "angle": "solucion"},
            {"text": "desarrollo por intuicion y validacion practica", "angle": "situacion"},
            {"text": "construir antes de entender la teoria", "angle": "ingenuo"},
        ],
        "nodos": [
            "dennys-metodo-creativo",
            "dennys-working-style"
        ]
    }
]


def cargar_hubs_iniciales(conn: sqlite3.Connection) -> dict:
    """Carga o actualiza los hubs canónicos iniciales en la base de datos."""
    crear_tablas(conn)
    creados = 0
    for hub in HUBS_INICIALES:
        try:
            crear_hub(conn, hub["hub_id"], hub["canonical_node"], hub["description"], validar_existencia=False)
            agregar_bridges(conn, hub["hub_id"], hub["bridges"])
            agregar_nodos(conn, hub["hub_id"], hub["nodos"], validar_existencia=False)
            creados += 1
        except Exception:
            pass
    return {"status": "ok", "hubs_creados": creados}
