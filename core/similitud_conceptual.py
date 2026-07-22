"""
Similitud Conceptual Latente.

Calcula similitud entre conceptos usando la red sináptica existente
(Jaccard sobre vecinos compartidos) + tokens compartidos en contenido.
Sin dependencias externas. Funciona desde el día uno con la DB actual.
"""

import os
import re
import sqlite3
from core.stopwords import _STOPWORDS_QUERY

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================

CANDIDATOS_SIMILITUD = int(os.environ.get('BIORAG_CANDIDATOS_SIMILITUD', '100'))
"""Cuántos nodos considerar como candidatos en similitud conceptual."""

UMBRAL_JACCARD = float(os.environ.get('BIORAG_UMBRAL_JACCARD', '0.15'))
"""Umbral Jaccard para similitud conceptual (0.0-1.0)."""

LIMITE_SIMILITUD = int(os.environ.get('BIORAG_LIMITE_SIMILITUD', '5'))
"""Límite de resultados en similitud conceptual."""


_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,}\b')

def _cargar_grafo(cursor):
    """Carga todas las sinapsis en un dict de Python (una sola query SQL).
    Función pura y stateless para evitar concurrencia."""
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
    except Exception:
        pass
    return grafo


def _limpiar_cache(*args, **kwargs):
    """No-op. El caché es stateless y se maneja localmente."""
    pass


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


def score_similitud_latente(cursor, query_tokens, nodo_concepto, nodo_contenido,
                            grafo=None, nodos_cache=None, cerebro=None, peso_sinaptico=1.0):
    """
    Score compuesto v19.0 (8 Señales Cognitivas):
      0.25 × Texto / BM25 / Contenido
      0.15 × Jaccard sobre vecinos directos
      0.15 × PMI / NPMI Semántico (co-ocurrencia)
      0.15 × Inferencia Transitiva Latente (SLS)
      0.10 × Coincidencia en Dimensiones Semánticas
      0.10 × SDM Similitud Hamming (Sparse Distributed Memory)
      0.05 × Peso Sináptico (LTP / LTD)
      0.05 × Context Window Bonus (Memoria de trabajo)

    Retorna float [0.0, 1.0].
    """
    # 1. Contenido / Texto (0.25)
    contenido_tokens = _tokenizar_contenido(nodo_contenido)
    score_texto = similitud_por_contenido(query_tokens, contenido_tokens)

    # 2. Jaccard Vecinos (0.15)
    score_red = _similitud_red(cursor, query_tokens, nodo_concepto, grafo=grafo, nodos_cache=nodos_cache)

    # 3. PMI / NPMI Semántico (0.15)
    score_pmi = 0.0
    try:
        from core.pmi_semantico import score_pmi_nodo
        q_frase = " ".join(query_tokens)
        score_pmi = score_pmi_nodo(q_frase, nodo_concepto)
    except Exception:
        pass

    # 4. Inferencia Transitiva Latente SLS (0.15)
    score_latente = 0.0
    try:
        from core.inferencia_transitiva import obtener_score_latente
        score_latente = obtener_score_latente(cursor, list(query_tokens), nodo_concepto)
    except Exception:
        pass

    # 5. Overlap de Dimensiones Semánticas (0.10)
    score_dim = 0.0
    try:
        if query_tokens:
            ph = ",".join("?" * len(query_tokens))
            cursor.execute(
                f"SELECT COUNT(DISTINCT d.dimension_id) FROM largo_plazo_dimensiones d "
                f"WHERE d.concepto = ? AND d.dimension_id IN ("
                f"  SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto IN ({ph})"
                f")",
                (nodo_concepto, *query_tokens)
            )
            r = cursor.fetchone()
            if r and r[0]:
                score_dim = min(1.0, r[0] * 0.5)
    except Exception:
        pass

    # 6. SDM Similitud Hamming (0.10)
    score_sdm = 0.0
    try:
        from core.sdm import generar_vector_sdm, similitud_sdm
        q_str = " ".join(query_tokens)
        q_vec = generar_vector_sdm(q_str, q_str)
        n_vec = generar_vector_sdm(nodo_concepto, nodo_contenido or "")
        score_sdm = similitud_sdm(q_vec, n_vec)
    except Exception:
        pass

    # 7. Peso Sináptico (0.05)
    peso_norm = min(1.0, max(0.0, peso_sinaptico / 5.0))

    # 8. Context Window Bonus (0.05)
    score_context = 0.0
    if cerebro and hasattr(cerebro, 'obtener_bonus_contexto'):
        score_context = cerebro.obtener_bonus_contexto(nodo_concepto)

    # Suma ponderada de 8 señales
    score_final = (
        0.25 * score_texto +
        0.15 * score_red +
        0.15 * score_pmi +
        0.15 * score_latente +
        0.10 * score_dim +
        0.10 * score_sdm +
        0.05 * peso_norm +
        0.05 * score_context
    )

    return round(min(1.0, score_final), 4)


def _generar_subterminos_fts(token):
    L = len(token)
    if L < 4:
        return [token]
    edits = L // 4
    k = edits + 1
    W = L // k
    if W < 3:
        trigramas = [token[i:i+3] for i in range(L - 2)]
        return trigramas if trigramas else [token]
    else:
        parts = []
        for i in range(k):
            start = i * W
            end = (i + 1) * W if i < k - 1 else L
            parts.append(token[start:end])
        return parts


def _obtener_candidatos_similitud(cursor, query_tokens):
    import json
    sub_tokens = []
    for t in query_tokens:
        if len(t) >= 3:
            sub_tokens.extend(_generar_subterminos_fts(t))
    
    if not sub_tokens:
        return []
        
    fts_tokens = [f'"{st}"' for st in sub_tokens]
    fts_q = " OR ".join(fts_tokens)
    
    try:
        cursor.execute(
            "SELECT concepto FROM largo_plazo "
            "WHERE estado = 'activo' AND rowid IN ("
            "  SELECT rowid FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?"
            ")",
            (fts_q,)
        )
        bridges = [row[0] for row in cursor.fetchall()]
    except Exception:
        bridges = []
        
    if not bridges:
        return []

    cte_query = """
    WITH puentes AS (
        SELECT concepto FROM largo_plazo 
        WHERE concepto IN (SELECT value FROM json_each(?)) AND estado = 'activo'
    ),
    vecinos_1 AS (
        SELECT destino AS concepto FROM sinapsis WHERE origen IN (SELECT concepto FROM puentes)
        UNION
        SELECT origen AS concepto FROM sinapsis WHERE destino IN (SELECT concepto FROM puentes)
    ),
    vecinos_2 AS (
        SELECT destino AS concepto FROM sinapsis WHERE origen IN (SELECT concepto FROM vecinos_1)
        UNION
        SELECT origen AS concepto FROM sinapsis WHERE destino IN (SELECT concepto FROM vecinos_1)
    )
    SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones
    FROM largo_plazo
    WHERE estado = 'activo' AND (
        concepto IN (SELECT concepto FROM puentes) OR
        concepto IN (SELECT concepto FROM vecinos_2) OR
        rowid IN (
            SELECT rowid FROM largo_plazo_fts 
            WHERE largo_plazo_fts MATCH ?
        )
    )
    """
    try:
        cursor.execute(cte_query, (json.dumps(bridges), fts_q))
        return cursor.fetchall()
    except Exception:
        try:
            cursor.execute(
                "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                "FROM largo_plazo "
                "WHERE estado = 'activo' AND rowid IN ("
                "  SELECT rowid FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?"
                ")",
                (fts_q,)
            )
            return cursor.fetchall()
        except Exception:
            return []


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

    candidatos = _obtener_candidatos_similitud(cursor, query_tokens)
    if not candidatos:
        return []

    scored = []
    grafo = _cargar_grafo(cursor)
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
                "SELECT DISTINCT l.concepto FROM largo_plazo l "
                "WHERE l.estado = 'activo' AND l.rowid IN ("
                "  SELECT rowid FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?"
                ") " + pc_clause + " LIMIT 50",
                (fts_q,) + pc_params
            )
            nodos_cache = {row[0] for row in cursor.fetchall()}
        else:
            nodos_cache = None
    except sqlite3.OperationalError:
        nodos_cache = None
    try:
        for rowid, concepto, contenido, peso, estado, asoc in candidatos:
            s = score_similitud_latente(cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache)
            if s >= umbral:
                scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))
    finally:
        _limpiar_cache()

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limite]]

