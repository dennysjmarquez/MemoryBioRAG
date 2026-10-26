"""
Concept Hub — Capa semántica que resuelve vocabulario sin overlap.

Fundamentos científicos:
    - Teoría de Prototipos y Categorización Conceptual (Rosch, 1975; Posner & Keele, 1968).
    - Modelos de Redes Semánticas de Memoria Humana (Collins & Quillian, 1969; Collins & Loftus, 1975).
    - Mediación Semántica y Zonas de Sentido (Vygotsky, 1934).

Problema que resuelve:
    Cuando la query y el nodo no comparten palabras pero comparten significado (Abismo Léxico),
    BM25/FTS5 devuelve 0 resultados. Las dimensiones y PPMI/SVD tampoco rescatan
    porque el corpus es demasiado pequeño para aprender sinonimia estadística.

Solución:
    Grafo de significado con bridges explícitos clasificados por 5 ángulos semánticos.
    No depende de estadística — construye la semántica determinista mediante
    conceptos canónicos y frases puente estructuradas en 5 perspectivas canónicas:
    1. 'sinonimo' (paráfrasis formal / denominación técnica alternativa)
    2. 'problema' (formulación de la necesidad o síntoma)
    3. 'solucion' (declaración resolutiva de la arquitectura)
    4. 'situacion' (contexto de aplicación / caso de uso)
    5. 'ingenuo'   (expresión profana / lenguaje no técnico / cross-lingual ES-EN)

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
Versión del producto: consultar el archivo raíz `VERSION` (fuente única).
"""

import os
import re
import math
import time
import json
import logging
import sqlite3
from typing import Optional, List, Dict, Any, Tuple, Union

logger = logging.getLogger("BioRAG.ConceptHub")


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
            except Exception as exc:
                logger.debug(f"[ConceptHub.validar_bridges] Error parseando JSON de bridges: {exc}")
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
    """Tokeniza y normaliza texto: minúsculas, sin acentos/tildes, sin puntuación.

    La normalización NFD + strip de marcas diacríticas asegura que 'librería' == 'libreria',
    'recopilación' == 'recopilacion', 'instanciación' == 'instanciacion', etc.
    Sin esto, cualquier query con tildes falla contra bridges sin tildes (Jaccard=0).
    """
    if not texto:
        return set()
    import unicodedata
    # Descomponer caracteres compuestos (NFD) y eliminar las marcas diacríticas (Mn)
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    texto = texto.lower().strip()
    texto = re.sub(r'[^\w\s]', ' ', texto)
    tokens = set()
    for w in texto.split():
        w = w.strip()
        if len(w) >= 2:
            tokens.add(w)
    return tokens


def _tokenizar_stems(texto: str) -> set:
    """Tokeniza, normaliza, filtra stopwords y aplica stemming para matching semántico robusto."""
    if not texto:
        return set()
    import unicodedata
    from core.stopwords import STOPWORDS_ES
    from core.stemmer_es import stem

    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    texto = texto.lower().strip()
    texto = re.sub(r'[^\w\s]', ' ', texto)
    tokens = set()
    for w in texto.split():
        w = w.strip()
        if len(w) >= 2 and w not in STOPWORDS_ES:
            tokens.add(stem(w))
    if not tokens and texto.strip():
        for w in texto.split():
            w = w.strip()
            if len(w) >= 2:
                tokens.add(stem(w))
    return tokens


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity entre dos sets de tokens."""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


# ─── v35.2 HUB A ESCALA: neuronas de concepto que funcionan con 6 o con 6000 hubs ───
#
# Por qué existe esto. El hub nació (v29) como un puñado de conceptos curados (10–17)
# para cruzar el abismo léxico: preguntas que no comparten palabras con el recuerdo.
# Desde que `aprender` crea un hub con 5 puentes por CADA recuerdo, una base real tiene
# cientos o miles de hubs, pero la fórmula seguía siendo la de 17: cada palabra valía
# lo mismo y el mejor hub se lo llevaba todo. Con 866 hubs el hub se disparaba en 875
# de las 921 preguntas de la QA, una palabra común ("regla", "cv") que aparece en
# decenas de puentes daba confianza 1.0 a un hub cualquiera, y su recuerdo se forzaba
# al TOP1. Además releía y tokenizaba todos los puentes en cada búsqueda (~0.5 s).
#
# Cómo lo resuelve el cerebro, y cómo lo resolvemos aquí:
#   1. Efecto abanico (ACT-R, Anderson 1974) / sobrecarga de pista (Watkins & Watkins
#      1975): una pista asociada a muchos recuerdos activa a cada uno con menos fuerza,
#      S_ji = S − ln(abanico_j). Con S = ln(H) es el IDF de la recuperación de información.
#      Cada palabra pesa ln(1 + (H − abanico + 0.5)/(abanico + 0.5)) (siempre positivo,
#      también con 1 solo hub).
#      Palabras de función ("antes", "dónde", "que", "de"): en una paráfrasis pueden cambiar
#      el sentido ("qué hacía ANTES de ser programador"), así que cuentan, pero aportan
#      como mucho 1 bit: el peso de una palabra que parte la memoria en dos mitades,
#      ln(1 + (H − H/2 + .5)/(H/2 + .5)) = ln 2. Menos si en ESTA base son aún más comunes.
#      El tope existe porque los puentes son frases cortas y telegráficas: ahí "dónde"
#      parece rara y, sin tope, pesaría como una palabra de contenido. Tampoco abren
#      candidatos: compartir solo palabras de función no es una coincidencia.
#      (v35.2 las quitaba con la lista de la búsqueda por texto: "qué hacía antes de ser
#      programador" quedaba en {ser, programador} y, en la base viva, cualquier puente con
#      "programador" empataba con el correcto y el hub no decidía.)
#   2. Priming por repetición > priming morfológico: la palabra idéntica cuenta entera; la
#      misma familia (solo la raíz: programador / programación) cuenta la mitad.
#   3. Completar un patrón exige parecido, no solo inclusión: la "cobertura del puente" se
#      reemplaza por el coseno (Ochiai, √(cobertura_pregunta × cobertura_puente)). Un puente
#      diminuto ("algo no tiene identidad") contenido en la pregunta vale solo lo que
#      explica de ella.
#   4. Elección de Luce / recuperación de ACT-R: un recuerdo se recupera por su ventaja
#      sobre los rivales, no solo por su parecido: ventaja = e^(s/T) / Σ e^(s_k/T) entre los
#      RECUERDOS activados (dos hubs que apuntan al mismo recuerdo son aliados, no rivales).
#      Si 10 recuerdos empatan, cada uno tiene 0.1 y ninguno se impone (antes ganaba el
#      primero en orden alfabético). confianza = parecido × ventaja; con un ganador claro,
#      ventaja ≈ 1 y nada cambia.
#   5. Índice invertido en memoria, reconstruido solo cuando cambian las tablas del hub
#      (huella de ~1 ms): cada búsqueda mira solo los hubs que comparten alguna palabra.
#
# Lo demás es lo de siempre: multiplicador por ángulo, bonus de consenso, umbral 0.40 y
# todo lo que el motor hace después con el hub (expansión, señal #14, paso por el QCR,
# promoción competitiva al TOP1).
# Ablación: BIORAG_HUB_ESCALA=0 vuelve exactamente al cálculo anterior.

ANGLE_MULT_HUB = {
    "sinonimo": 1.5,
    "problema": 1.2,
    "solucion": 1.1,
    "situacion": 1.0,
    "ingenuo": 0.85,
    "legacy": 1.0,
}
HUB_TEMPERATURA = float(os.environ.get("BIORAG_HUB_TEMPERATURA", "0.10"))
_INDICE_HUBS: dict = {}


def _hub_escala_activa() -> bool:
    return os.environ.get("BIORAG_HUB_ESCALA", "1") != "0"


def _firma_hubs(conn: sqlite3.Connection) -> tuple:
    """Huella barata de las 3 tablas del hub: cambia con cualquier alta, baja o edición
    (texto, ángulo, peso, recuerdo canónico, nodos). Cuesta ~1 ms con miles de puentes."""
    b = conn.execute(
        "SELECT COUNT(*), COALESCE(MAX(bridge_id), 0), COALESCE(SUM(LENGTH(bridge_text) * bridge_id), 0), "
        "COALESCE(SUM(weight * bridge_id), 0), "
        "COALESCE(SUM(bridge_id * CASE angle WHEN 'sinonimo' THEN 1 WHEN 'problema' THEN 2 "
        "WHEN 'solucion' THEN 3 WHEN 'situacion' THEN 4 WHEN 'ingenuo' THEN 5 ELSE 6 END), 0), "
        "COALESCE(SUM(LENGTH(hub_id) * bridge_id), 0) FROM concept_hub_bridges"
    ).fetchone()
    h = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM((LENGTH(hub_id) + 31 * LENGTH(canonical_node)) * rowid), 0), "
        "COALESCE(SUM((unicode(canonical_node) + 7 * unicode(substr(canonical_node, -1))) * rowid), 0) "
        "FROM concept_hubs"
    ).fetchone()
    n = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM((LENGTH(hub_id) + 31 * LENGTH(node_concepto)) * rowid), 0), "
        "COALESCE(SUM((unicode(node_concepto) + 7 * unicode(substr(node_concepto, -1))) * rowid), 0) "
        "FROM concept_hub_nodes"
    ).fetchone()
    return tuple(b) + tuple(h) + tuple(n)


def _indice_hubs(conn: sqlite3.Connection) -> dict:
    """Índice invertido de los puentes (palabra → hubs), con el abanico de cada palabra."""
    try:
        ruta = next((r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"), "") or f"mem:{id(conn)}"
        firma = _firma_hubs(conn)
    except sqlite3.Error:
        return {}
    clave = (ruta, firma)
    idx = _INDICE_HUBS.get(ruta)
    if idx is not None and idx["clave"] == clave:
        return idx

    hubs: dict = {}
    for hub_id, canonical, bridge_text, weight, angle, nodos_str in conn.execute("""
        SELECT h.hub_id, h.canonical_node,
               b.bridge_text, b.weight, b.angle,
               GROUP_CONCAT(DISTINCT n.node_concepto) as nodos
        FROM concept_hubs h
        LEFT JOIN concept_hub_bridges b ON h.hub_id = b.hub_id
        LEFT JOIN concept_hub_nodes n ON h.hub_id = n.hub_id
        GROUP BY h.hub_id, b.bridge_text
    """):
        d = hubs.setdefault(hub_id, {"canonical": canonical, "bridges": [], "nodos": set()})
        if bridge_text:
            pal = _palabras_hub(bridge_text)
            if pal:
                d["bridges"].append((set(pal), set(pal.values()), weight or 1.0,
                                     ANGLE_MULT_HUB.get(angle or "legacy", 1.0), bridge_text))
        if nodos_str:
            d["nodos"].update(x.strip() for x in nodos_str.split(","))

    inv_s: dict = {}
    inv_t: dict = {}
    for hub_id, d in hubs.items():
        if not d["bridges"]:
            continue
        for t in set().union(*(b[0] for b in d["bridges"])):
            inv_t.setdefault(t, set()).add(hub_id)
        for st in set().union(*(b[1] for b in d["bridges"])):
            inv_s.setdefault(st, set()).add(hub_id)
    idx = {
        "clave": clave,
        "hubs": hubs,
        "inv_s": inv_s,
        "inv_t": inv_t,
        "H": sum(1 for d in hubs.values() if d["bridges"]),
    }
    if len(_INDICE_HUBS) > 16:
        _INDICE_HUBS.clear()
    _INDICE_HUBS[ruta] = idx
    return idx


def _palabras_hub(texto: str) -> dict:
    """Todas las palabras → su raíz (misma normalización que _tokenizar). Las de función
    también: cuánto pesan lo decide _puntajes_por_recuerdo (máximo 1 bit)."""
    from core.stemmer_es import stem
    return {t: stem(t) for t in _tokenizar(texto)}


_FUNCION_HUB: dict = {}


def _palabras_funcion() -> tuple:
    """(palabras de función, sus raíces). Se calcula una vez."""
    if not _FUNCION_HUB:
        from core.stopwords import STOPWORDS_ES
        from core.stemmer_es import stem
        _FUNCION_HUB["t"] = frozenset(STOPWORDS_ES)
        _FUNCION_HUB["s"] = frozenset(stem(w) for w in STOPWORDS_ES)
    return _FUNCION_HUB["t"], _FUNCION_HUB["s"]


def _puntajes_por_recuerdo(query_text: str, conn: sqlite3.Connection):
    """Parecido de cada RECUERDO activado por la pregunta, de mayor a menor:
    [(parecido, hub_id, puentes_que_coinciden), ...] y el índice. ([], None) si nada."""
    if not query_text or not query_text.strip():
        return [], None
    q_pal = _palabras_hub(query_text)
    if not q_pal:
        return [], None
    idx = _indice_hubs(conn)
    if not idx or not idx["H"]:
        return [], None
    H = idx["H"]
    inv_s, inv_t = idx["inv_s"], idx["inv_t"]

    fun_t, fun_s = _palabras_funcion()
    UN_BIT = math.log(2.0)

    def es_funcion(inv, x):
        return x in fun_t or (inv is inv_s and x in fun_s)

    def peso(inv, x):
        f = max(1, len(inv.get(x, ())))
        w = math.log(1.0 + (H - f + 0.5) / (f + 0.5))
        return min(w, UN_BIT) if es_funcion(inv, x) else w

    q_t = set(q_pal)
    q_s = set(q_pal.values())
    wt = {t: peso(inv_t, t) for t in q_t}
    ws = {st: peso(inv_s, st) for st in q_s}
    W_qt, W_qs = sum(wt.values()), sum(ws.values())

    candidatos = set()
    for t in q_t:
        if not es_funcion(inv_t, t):
            candidatos |= inv_t.get(t, set())
    for st in q_s:
        if not es_funcion(inv_s, st):
            candidatos |= inv_s.get(st, set())
    if not candidatos:
        return [], idx

    def vista(q, w_q, W_q, b, inv):
        inter = q & b
        if not inter:
            return 0.0, 0.0, 0.0
        w_i = sum(w_q[x] for x in inter)
        W_b = sum(w_q.get(x) or peso(inv, x) for x in b)
        union = W_q + W_b - w_i
        return (w_i / union if union > 0 else 0.0,
                w_i / W_q if W_q > 0 else 0.0,
                w_i / W_b if W_b > 0 else 0.0)

    # Competencia entre RECUERDOS: dos hubs que apuntan al mismo recuerdo son aliados.
    por_recuerdo: dict = {}
    for hub_id in candidatos:
        d = idx["hubs"][hub_id]
        mejor = 0.0
        matcheados = []
        for b_t, b_s, b_w, mult, b_text in d["bridges"]:
            jt, rqt, rbt = vista(q_t, wt, W_qt, b_t, inv_t)
            js, rqs, rbs = vista(q_s, ws, W_qs, b_s, inv_s)
            if not (jt or js):
                continue
            # Palabra idéntica cuenta entera; misma familia (solo raíz), la mitad.
            # Cobertura del puente → coseno (Ochiai, √(cob_pregunta × cob_puente)): un puente
            # diminuto contenido en la pregunta vale solo lo que explica de ella.
            rq = (rqt + rqs) / 2
            cos = (math.sqrt(rqt * rbt) + math.sqrt(rqs * rbs)) / 2
            sim = max((jt + js) / 2, 0.80 * rq, 0.80 * cos)
            sc = sim * b_w * mult
            if sc > mejor:
                mejor = sc
            if sim > 0.10:
                matcheados.append(b_text)
        hub_score = min(1.0, mejor + min(1.0, len(matcheados) / 3.0) * 0.2)
        if hub_score <= 0:
            continue
        previo = por_recuerdo.get(d["canonical"])
        if previo is None or (hub_score, hub_id) > (previo[0], previo[1]):
            por_recuerdo[d["canonical"]] = (hub_score, hub_id, matcheados)
    return sorted(por_recuerdo.values(), key=lambda x: (-x[0], x[1])), idx


def _expandir_a_escala(query_text: str, conn: sqlite3.Connection, threshold: float) -> Optional[dict]:
    puntajes, idx = _puntajes_por_recuerdo(query_text, conn)
    if not puntajes:
        return None
    s_top, hub_top, matcheados_top = puntajes[0]
    T = HUB_TEMPERATURA if HUB_TEMPERATURA > 0 else 0.10
    ventaja = 1.0 / sum(math.exp((s - s_top) / T) for s, _, _ in puntajes)
    confianza = s_top * ventaja
    if confianza < threshold - 1e-6:
        return None

    d = idx["hubs"][hub_top]
    expanded_terms = []
    for bridge in matcheados_top:
        expanded_terms.extend(_tokenizar(bridge))
    for nodo in d["nodos"]:
        expanded_terms.extend(_tokenizar(nodo.replace("_", " ")))
    expanded_terms.extend(_tokenizar(d["canonical"].replace("_", " ")))
    return {
        "canonical_nodes": [d["canonical"]] + [n for n in d["nodos"] if n != d["canonical"]],
        "expanded_terms": list(set(expanded_terms)),
        "hub_confidence": confianza,
        "hub_id": hub_top,
        "bridges_matched": matcheados_top,
        "hub_parecido": s_top,
        "hub_ventaja": ventaja,
    }


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
    if _hub_escala_activa():
        return _expandir_a_escala(query_text, conn, threshold)

    if not query_text or not query_text.strip():
        return None

    query_tokens = _tokenizar(query_text)
    query_stems = _tokenizar_stems(query_text)
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
            bridge_stems = _tokenizar_stems(bridge_text)
            if not bridge_tokens:
                continue

            jacc_raw = _jaccard(query_tokens, bridge_tokens)
            jacc_stem = _jaccard(query_stems, bridge_stems)
            jacc = max(jacc_raw, jacc_stem)
            mult = ANGLE_MULT.get(angle, 1.0)

            # Recall asimétrico bidireccional sobre stems (filtrando stopwords):
            # 1. rec_q: qué fracción de la query está en el bridge (queries concisas)
            # 2. rec_b: qué fracción del bridge está en la query (queries explicativas/largas)
            rec_q = (len(query_stems & bridge_stems) / len(query_stems)) if query_stems else 0.0
            rec_b = (len(query_stems & bridge_stems) / len(bridge_stems)) if bridge_stems else 0.0

            sim = max(jacc, rec_q * 0.80, rec_b * 0.80)
            score = sim * bridge_weight * mult

            if score > mejor_bridge_score:
                mejor_bridge_score = score
            # Umbral de match: > 0.10 en la similitud combinada
            if sim > 0.10:
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

    # Guard de ambigüedad con tolerancia de coma flotante
    if mejor_hub and mejor_hub["hub_confidence"] < (threshold - 1e-6) and (mejor_score - segundo_score) < 0.08:
        return None

    if mejor_hub and mejor_hub["hub_confidence"] >= (threshold - 1e-6):
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
            {"text": "oficios manuales rurales y empleo previo al desarrollo de software", "angle": "sinonimo"},
            {"text": "como sobrevivia economicamente dennys antes de entrar a la tecnologia", "angle": "problema"},
            {"text": "fumigador de campo y operario de tasajera en rufino", "angle": "solucion"},
            {"text": "vida laboral en el monte antes de aprender programacion e ingenieria", "angle": "situacion"},
            {"text": "que hacia dennys para sobrevivir y ganar dinero antes de ser programador", "angle": "ingenuo"},
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
            {"text": "regresiones y fallos al modificar codigo estable que funcionaba", "angle": "sinonimo"},
            {"text": "meti un cambio en codigo que andaba bien y todo se rompio", "angle": "problema"},
            {"text": "no tocar logica preexistente estable salvo evidencia real y medible", "angle": "solucion"},
            {"text": "toque algo que andaba bien y dejo de andar al refactorizar", "angle": "situacion"},
            {"text": "por que se rompe todo cuando cambio una sola linea que andaba", "angle": "ingenuo"},
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
            {"text": "mecanismo de recompensa interna y error de prediccion rpe", "angle": "sinonimo"},
            {"text": "sistema que no sabe si acerto o fallo y no mejora solo", "angle": "problema"},
            {"text": "disparo dopaminergico por acierto que consolida memoria via ltp", "angle": "solucion"},
            {"text": "aprendizaje autonomo sin supervision humana ni guia externa", "angle": "situacion"},
            {"text": "como hace la memoria para aprender sola sin que nadie le ensene", "angle": "ingenuo"},
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
            {"text": "discrepancia y debate entre modelos de lenguaje", "angle": "sinonimo"},
            {"text": "dos modelos de ia que no estan de acuerdo en la respuesta", "angle": "problema"},
            {"text": "sumar insights opuestos y sintetizar mentalidad sin descartar ninguno", "angle": "solucion"},
            {"text": "resolucion de contradicciones y desacuerdos entre inteligencias artificiales", "angle": "situacion"},
            {"text": "como resuelvo cuando dos ias dicen cosas distintas sobre lo mismo", "angle": "ingenuo"},
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
            {"text": "como construir y aprender antes de dominar la teoria formal", "angle": "ingenuo"},
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
            conn.execute("DELETE FROM concept_hub_bridges WHERE hub_id = ?", (hub["hub_id"],))
            agregar_bridges(conn, hub["hub_id"], hub["bridges"])
            agregar_nodos(conn, hub["hub_id"], hub["nodos"], validar_existencia=False)
            creados += 1
        except Exception as exc:
            logger.warning(f"[ConceptHub.cargar_hubs_iniciales] Error cargando hub inicial '{hub.get('hub_id')}': {exc}")
    return {"status": "ok", "hubs_creados": creados}
