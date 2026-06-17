"""
Similitud Conceptual Latente.

Calcula similitud entre conceptos usando la red sináptica existente
(Jaccard sobre vecinos compartidos) + tokens compartidos en contenido.
Sin dependencias externas. Funciona desde el día uno con la DB actual.
"""

import re
import sqlite3

# Stopwords adicionales para queries (complementa STOPWORDS_ES de sinapsis)
_STOPWORDS_QUERY = {
    'de', 'la', 'el', 'en', 'con', 'por', 'para', 'un', 'una',
    'y', 'o', 'que', 'es', 'se', 'al', 'lo', 'como', 'mas',
    'su', 'los', 'las', 'del', 'las', 'les', 'por', 'sin',
}

_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,}\b')


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


def jaccard_vecinos(cursor, concepto_a, concepto_b):
    """
    Jaccard sobre vecinos sinápticos de dos conceptos.
    Retorna float [0, 1].
    """
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


def _similitud_red(cursor, query_tokens, nodo_concepto, max_puentes=10):
    """
    Similitud de red: busca nodos 'puente' que contengan tokens del query,
    luego calcula Jaccard entre sus vecinos y los del nodo destino.
    Retorna float [0, 1].
    """
    if not query_tokens:
        return 0.0

    # Buscar nodos puente cuyo concepto contenga tokens del query
    terminos_fts = [f'"{t}"' for t in query_tokens if len(t) >= 3]
    if not terminos_fts:
        return 0.0

    fts_query = " OR ".join(terminos_fts)
    try:
        cursor.execute(
            "SELECT l.concepto FROM largo_plazo_fts f "
            "JOIN largo_plazo l ON l.rowid = f.rowid "
            "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
            "AND l.concepto != ? LIMIT ?",
            (fts_query, nodo_concepto, max_puentes)
        )
        puentes = [r[0] for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        return 0.0

    if not puentes:
        return 0.0

    # Jaccard entre cada puente y el nodo destino, tomar el mejor
    mejor = 0.0
    for puente in puentes:
        j = jaccard_vecinos(cursor, puente, nodo_concepto)
        if j > mejor:
            mejor = j

    return mejor


def score_similitud_latente(cursor, query_tokens, nodo_concepto, nodo_contenido):
    """
    Score compuesto: 60% red sináptica + 40% contenido.
    Retorna float [0, 1].
    """
    score_red = _similitud_red(cursor, query_tokens, nodo_concepto)
    contenido_tokens = _tokenizar_contenido(nodo_contenido)
    score_texto = similitud_por_contenido(query_tokens, contenido_tokens)

    return score_red * 0.60 + score_texto * 0.40


def buscar_por_similitud_latente(cursor, frase, limite=5, umbral=0.15):
    """
    Búsqueda por similitud conceptual latente.
    Retorna lista de (concepto, contenido, peso, estado, score_latente, asociaciones).
    """
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
    for rowid, concepto, contenido, peso, estado, asoc in candidatos:
        s = score_similitud_latente(cursor, query_tokens, concepto, contenido)
        if s >= umbral:
            scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limite]]
