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

# Caché del vector SDM del query para no regenerarlo en cada candidato.
# Se setea antes del loop y se limpia al final.
_sdm_query_vector_cache: dict = {}

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
    """Limpia caché local incluyendo el vector SDM del query."""
    _sdm_query_vector_cache.clear()


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
        conceptos_ref = list(nodos_cache)[:25] if nodos_cache else []
        if conceptos_ref:
            ph = ",".join("?" * len(conceptos_ref))
            cursor.execute(
                f"SELECT COUNT(DISTINCT d.dimension_id) FROM largo_plazo_dimensiones d "
                f"WHERE d.concepto = ? AND d.dimension_id IN ("
                f"  SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto IN ({ph})"
                f")",
                (nodo_concepto, *conceptos_ref)
            )
            r = cursor.fetchone()
            if r and r[0]:
                score_dim = min(1.0, r[0] * 0.35)
    except Exception:
        pass

    # 6. SDM Similitud Hamming (0.10)
    #    Lee vector pre-calculado de nodos_sdm en vez de regenerarlo.
    #    Solo genera el vector del query (fuera del loop por el caller).
    score_sdm = 0.0
    try:
        from core.sdm import similitud_sdm
        n_vec = None
        if cerebro and hasattr(cerebro, 'cursor'):
            row = cerebro.cursor.execute(
                "SELECT vector FROM nodos_sdm WHERE concepto = ?", (nodo_concepto,)
            ).fetchone()
            if row:
                n_vec = row[0]
        if n_vec is None:
            from core.sdm import generar_vector_sdm
            n_vec = generar_vector_sdm(nodo_concepto, nodo_contenido or "")
        q_vec = _sdm_query_vector_cache.get("vector")
        if q_vec is not None:
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


def buscar_por_similitud_latente(cursor, frase, limite=None, umbral=None, cerebro=None):
    """
    Búsqueda por similitud conceptual latente con Propagación Sináptica.

    Implementa un modelo de dos fases análogo a la evocación hipocampal:

      FASE 1 — Activación Léxica (Corteza sensorial → Hipocampo):
        El query activa nodos que contienen las palabras exactas.
        Se evalúan con las 8 señales cognitivas (texto, PMI, Jaccard, etc.)
        Los top-K nodos se convierten en SEMILLAS (neuronas activadas).

      FASE 2 — Propagación Sináptica (CA3 Pattern Completion):
        Las semillas propagan energía por sus sinapsis (directas + latentes)
        a TODOS los candidatos. Un candidato que está conectado a MÚLTIPLES
        semillas recibe amplificación (resonancia por convergencia).
        Un candidato conectado a UNA sola semilla recibe atenuación.

    Esto permite que nodos semánticamente relacionados (que no contienen
    las palabras del query pero SÍ están conectados a los nodos que sí las
    contienen) suban al ranking.

    Ejemplo: Query "arquitectura frontend" → activa cv_adevcom (semilla)
             → caso_formularios_anidados_angular (conectado con peso 0.493)
             → SUBE al ranking aunque no contiene "arquitectura frontend"
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

    # ═══════════════════════════════════════════════════════════════════
    # FASE 1: Scoring de 8 señales (Activación Léxica)
    # ═══════════════════════════════════════════════════════════════════
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

    # Pre-generar vector SDM del query (una sola vez para todos los candidatos)
    _sdm_query_vector_cache.clear()
    try:
        from core.sdm import generar_vector_sdm
        q_str = " ".join(query_tokens)
        _sdm_query_vector_cache["vector"] = generar_vector_sdm(q_str, q_str)
    except Exception:
        pass

    try:
        # Pre-filtro suave: permitir que más candidatos pasen a la Fase 2.
        # El umbral real se aplica DESPUÉS de la propagación sináptica.
        # Analogía: el cerebro no descarta una neurona antes de que la
        # activación llegue a ella — espera a ver si recibe energía.
        umbral_prefiltro = umbral * 0.5
        for rowid, concepto, contenido, peso, estado, asoc in candidatos:
            s = score_similitud_latente(cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache, cerebro=cerebro)
            if s >= umbral_prefiltro:
                scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))
    finally:
        _limpiar_cache()

    if not scored:
        return []

    scored.sort(key=lambda x: x[0], reverse=True)

    # ═══════════════════════════════════════════════════════════════════
    # FASE 2: Propagación Sináptica desde Semillas (Pattern Completion)
    # ═══════════════════════════════════════════════════════════════════
    # Analogía biológica: en la región CA3 del hipocampo, las neuronas
    # activadas (semillas) propagan energía a través de sus colaterales
    # recurrentes (sinapsis) a neuronas vecinas.
    #
    # Inhibición Lateral de Hubs: para evitar que nodos hiperconectados
    # (ej. perfil general) absorban toda la energía, cada peso se atenia
    # por la masa del grado del nodo destino (grados ^ 0.3).
    K_SEMILLAS = 10
    PESO_PROPAGACION = 0.25

    semillas = [row[1] for _, row in scored[:K_SEMILLAS]]

    # Precalculo de grados para inhibición lateral
    try:
        cur_g = cursor.execute(
            "SELECT origen, COUNT(*) FROM sinapsis GROUP BY origen "
            "UNION ALL SELECT destino, COUNT(*) FROM sinapsis GROUP BY destino"
        ).fetchall()
        grados = {}
        for r in cur_g:
            grados[r[0]] = grados.get(r[0], 0) + r[1]
    except Exception:
        grados = {}

    sinapsis_semillas = {}  # {concepto_candidato: peso_total}
    for semilla in semillas:
        # Directas
        rows = cursor.execute(
            'SELECT destino, peso FROM sinapsis WHERE origen = ? '
            'UNION SELECT origen, peso FROM sinapsis WHERE destino = ?',
            (semilla, semilla)
        ).fetchall()
        for destino, peso in rows:
            deg = max(1, grados.get(destino, 1))
            peso_eff = peso / (deg ** 0.3)
            sinapsis_semillas.setdefault(destino, 0.0)
            sinapsis_semillas[destino] += peso_eff

        # Latentes (incluye inmaduras con su peso atenuado)
        rows_lat = cursor.execute(
            'SELECT destino, peso_atenuado FROM sinapsis_latentes WHERE origen = ? '
            'UNION SELECT origen, peso_atenuado FROM sinapsis_latentes WHERE destino = ?',
            (semilla, semilla)
        ).fetchall()
        for destino, peso in rows_lat:
            deg = max(1, grados.get(destino, 1))
            peso_eff = peso / (deg ** 0.3)
            sinapsis_semillas.setdefault(destino, 0.0)
            sinapsis_semillas[destino] += peso_eff

    # Calcular score de propagación para cada candidato
    propagados = []
    for score_original, row in scored:
        concepto = row[1]

        # ¿Este candidato recibe energía de las semillas?
        energia_recibida = sinapsis_semillas.get(concepto, 0.0)

        # Normalizar
        prop_score = min(1.0, energia_recibida / 2.5)

        # Combinar: score original + propagación sináptica
        score_final = score_original * (1.0 - PESO_PROPAGACION) + prop_score * PESO_PROPAGACION

        propagados.append((score_final, row))

    propagados.sort(key=lambda x: x[0], reverse=True)
    # Aplicar umbral real DESPUÉS de la propagación
    return [row for score_f, row in propagados if score_f >= umbral][:limite]

