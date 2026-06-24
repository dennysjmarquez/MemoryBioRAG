"""
Similitud Conceptual Latente.

Calcula similitud entre conceptos usando la red sináptica existente
(Jaccard sobre vecinos compartidos) + tokens compartidos en contenido.
Sin dependencias externas. Funciona desde el día uno con la DB actual.
"""

import os
import re
import sqlite3

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================

CANDIDATOS_SIMILITUD = int(os.environ.get('BIORAG_CANDIDATOS_SIMILITUD', '100'))
"""Cuántos nodos considerar como candidatos en similitud conceptual."""

UMBRAL_JACCARD = float(os.environ.get('BIORAG_UMBRAL_JACCARD', '0.15'))
"""Umbral Jaccard para similitud conceptual (0.0-1.0)."""

LIMITE_SIMILITUD = int(os.environ.get('BIORAG_LIMITE_SIMILITUD', '5'))
"""Límite de resultados en similitud conceptual."""

# Stopwords adicionales para queries (complementa STOPWORDS_ES de sinapsis)
_STOPWORDS_QUERY = {
    'de', 'la', 'el', 'en', 'con', 'por', 'para', 'un', 'una',
    'y', 'o', 'que', 'es', 'se', 'al', 'lo', 'como', 'mas',
    'su', 'los', 'las', 'del', 'las', 'les', 'por', 'sin',
}

_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,}\b')

# Cache global de sinapsis (se carga una vez por búsqueda)
_grafo_cache = None


def _cargar_grafo(cursor):
    """Carga todas las sinapsis en un dict de Python (una sola query SQL).
    Reduce de 200+ queries a 1 query para todo el pipeline Jaccard."""
    global _grafo_cache
    if _grafo_cache is not None:
        return _grafo_cache
    grafo = {}
    try:
        cursor.execute("SELECT origen, destino FROM sinapsis")
        for origen, destino in cursor.fetchall():
            if origen not in grafo:
                grafo[origen] = set()
            grafo[origen].add(destino)
            if destino not in grafo:
                grafo[destino] = set()
            grafo[destino].add(origen)
    except sqlite3.OperationalError:
        grafo = {}
    _grafo_cache = grafo
    return grafo


def _limpiar_cache():
    """Limpia el cache de sinapsis. Llamar al final de cada búsqueda."""
    global _grafo_cache
    _grafo_cache = None


def _tokenizar_query(texto):
    """Tokeniza un query para similitud conceptual. Filtra stopwords cortas."""
    texto = texto.replace('_', ' ')
    tokens = set(_TOKEN_PATTERN.findall(texto.lower()))
    return tokens - _STOPWORDS_QUERY


def _tokenizar_contenido(texto):
    """Tokeniza contenido de nodo. Reutiliza lógica de sinapsis."""
    if not texto:
        return set()
    texto = texto.replace('_', ' ')
    return set(_TOKEN_PATTERN.findall(texto.lower()))


def jaccard_vecinos(cursor, concepto_a, concepto_b, grafo=None):
    """
    Jaccard sobre vecinos sinápticos de dos conceptos.
    Si grafo (dict) se provee, usa cache en memoria (sin queries SQL).
    Retorna float [0, 1].
    """
    if grafo is not None:
        vecinos_a = grafo.get(concepto_a, set())
        vecinos_b = grafo.get(concepto_b, set())
    else:
        cursor.execute(
            "SELECT destino FROM sinapsis WHERE origen = ? "
            "UNION SELECT origen FROM sinapsis WHERE destino = ?",
            (concepto_a, concepto_a)
        )
        vecinos_a = set(r[0] for r in cursor.fetchall())

        cursor.execute(
            "SELECT destino FROM sinapsis WHERE origen = ? "
            "UNION SELECT origen FROM sinapsis WHERE destino = ?",
            (concepto_b, concepto_b)
        )
        vecinos_b = set(r[0] for r in cursor.fetchall())

    if not vecinos_a or not vecinos_b:
        return 0.0

    interseccion = vecinos_a & vecinos_b
    union = vecinos_a | vecinos_b

    return len(interseccion) / len(union)


def similitud_por_contenido(query_tokens, contenido_tokens):
    """
    Fracción de tokens del query que aparecen en el contenido.
    Retorna float [0, 1].
    """
    if not query_tokens or not contenido_tokens:
        return 0.0
    interseccion = query_tokens & contenido_tokens
    return len(interseccion) / len(query_tokens)


def _similitud_red(cursor, query_tokens, nodo_concepto, max_puentes=10, grafo=None, nodos_cache=None):
    """
    Similitud de red: busca nodos 'puente' que contengan tokens del query,
    luego calcula Jaccard entre sus vecinos y los del nodo destino.
    Retorna float [0, 1].

    nodos_cache: set pre-cargado de conceptos puente (resultado de UNA query FTS5).
                 Si se provee, se usa en vez de N queries FTS5 separadas.
    """
    if not query_tokens:
        return 0.0

    if nodos_cache is not None:
        # MODO BATCH: usar puentes pre-cargados (1 query FTS5 en total)
        puentes = [n for n in nodos_cache if n != nodo_concepto][:max_puentes]
    else:
        # MODO LEGACY: FTS5 query por candidato (N queries)
        filtrar = [t for t in query_tokens if len(t) >= 3]
        if not filtrar:
            return 0.0
        terminos_fts = [f'"{t}"' for t in filtrar]
        fts_query = " OR ".join(terminos_fts)
        pc_clause = " AND (" + " OR ".join(
            ["(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1)"] * len(terminos_fts)
        ) + ")"
        pc_params = tuple(p for t in terminos_fts for p in (t.strip('"'), t.strip('"')))
        try:
            cursor.execute(
                "SELECT l.concepto FROM largo_plazo_fts f "
                "JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                "AND l.concepto != ?" + pc_clause + " LIMIT ?",
                (fts_query, nodo_concepto) + pc_params + (max_puentes,)
            )
            puentes = [r[0] for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            return 0.0

    if not puentes:
        return 0.0

    # Jaccard entre cada puente y el nodo destino, tomar el mejor
    mejor = 0.0
    for puente in puentes:
        j = jaccard_vecinos(cursor, puente, nodo_concepto, grafo=grafo)
        if j > mejor:
            mejor = j

    return mejor


def score_similitud_latente(cursor, query_tokens, nodo_concepto, nodo_contenido, grafo=None, nodos_cache=None):
    """
    Score compuesto: 60% red sináptica + 40% contenido.
    Retorna float [0, 1].
    """
    score_red = _similitud_red(cursor, query_tokens, nodo_concepto, grafo=grafo, nodos_cache=nodos_cache)
    contenido_tokens = _tokenizar_contenido(nodo_contenido)
    score_texto = similitud_por_contenido(query_tokens, contenido_tokens)

    return score_red * 0.60 + score_texto * 0.40


def buscar_por_similitud_latente(cursor, frase, limite=None, umbral=None):
    """
    Búsqueda por similitud conceptual latente.
    Retorna lista de (concepto, contenido, peso, estado, score_latente, asociaciones).
    """
    if limite is None:
        limite = LIMITE_SIMILITUD
    if umbral is None:
        umbral = UMBRAL_JACCARD
    query_tokens = _tokenizar_query(frase)
    if not query_tokens:
        return []

    # Buscar todos los nodos activos
    try:
        cursor.execute(
            "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
            "l.estado, l.asociaciones "
            "FROM largo_plazo l "
            "WHERE l.estado = 'activo'"
        )
        candidatos = cursor.fetchall()
    except sqlite3.OperationalError:
        return []

    scored = []
    grafo = _cargar_grafo(cursor)
    # Pre-fetch puentes FTS5 una vez (batch optimization)
    # Filtro PALABRA_COMPLETA: evita que trigramas falsos (ej: "culo" en "oráculo")
    # contaminen los puentes de similitud conceptual.
    try:
        filtrar = [t for t in query_tokens if len(t) >= 3]
        if filtrar:
            fts_tokens = [f'"{t}"' for t in filtrar]
            fts_q = " OR ".join(fts_tokens)
            pc_clause = " AND (" + " OR ".join(
                ["(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)"] * len(filtrar)
            ) + ")"
            pc_params = tuple(p for t in filtrar for p in (t, t, t))
            cursor.execute(
                "SELECT DISTINCT l.concepto FROM largo_plazo_fts f "
                "JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                + pc_clause + " LIMIT 50",
                (fts_q,) + pc_params
            )
            nodos_cache = {row[0] for row in cursor.fetchall()}
        else:
            nodos_cache = None
    except sqlite3.OperationalError:
        nodos_cache = None
    for rowid, concepto, contenido, peso, estado, asoc in candidatos:
        s = score_similitud_latente(cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache)
        if s >= umbral:
            scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))
    _limpiar_cache()

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limite]]
