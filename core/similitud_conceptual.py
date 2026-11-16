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

# El camino latente es un rescate, no debe materializar el grafo completo en RAM.
# La cota conserva el grafo actual del snapshot (grado máximo observado: 270)
# y hace constante el trabajo incluso si un hub crece con el corpus.
_MAX_ARISTAS_POR_DIRECCION = 512
_MAX_CANDIDATOS_LATENTES = 256
_MAX_SEMILLAS_EXPANSION = 10
_MAX_VECINOS_EXPANSION = 16


def _rowid_corte_positivo(valor):
    """Return a positive rowid cutoff; zero and invalid values mean no cutoff."""
    try:
        cutoff = int(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return cutoff if cutoff > 0 else None


class _GrafoSinapticoLazy:
    """Vista indexada y acotada del grafo, limitada al cohorte de referencia."""

    def __init__(self, cursor, rowid_max=None):
        self._cursor = cursor
        self._rowid_max = _rowid_corte_positivo(rowid_max)
        self._vecinos_cache = {}
        self._grado_cache = {}
        try:
            sql = "SELECT 1 FROM sinapsis"
            params = ()
            if self._rowid_max is not None:
                sql += " WHERE rowid <= ?"
                params = (self._rowid_max,)
            self._hay_aristas = cursor.execute(sql + " LIMIT 1", params).fetchone() is not None
        except sqlite3.Error:
            self._hay_aristas = False

    def __bool__(self):
        return self._hay_aristas

    def _consulta_acotada(self, columna, vecino, concepto, limite):
        sql = (
            f"SELECT {vecino} FROM sinapsis WHERE {columna} = ?"
        )
        params = [concepto]
        if self._rowid_max is not None:
            sql += " AND rowid <= ?"
            params.append(self._rowid_max)
        # rowid es el sufijo implícito de los índices de endpoint; se lee una
        # ventana estable sin ordenar ni recorrer el resto de un nodo hub.
        sql += " ORDER BY rowid LIMIT ?"
        params.append(min(_MAX_ARISTAS_POR_DIRECCION, max(1, int(limite))))
        try:
            return self._cursor.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error:
            return []

    def vecinos_ponderados(self, concepto, limite=_MAX_VECINOS_EXPANSION):
        """Retorna una ventana acotada de aristas incidentes para expansión."""
        if not concepto:
            return []
        por_direccion = min(_MAX_ARISTAS_POR_DIRECCION, max(1, int(limite)))
        salida = self._consulta_ponderada("origen", "destino", concepto, por_direccion)
        entrada = self._consulta_ponderada("destino", "origen", concepto, por_direccion)
        # La selección es determinista incluso con edges recíprocos.
        return list(dict.fromkeys(salida + entrada))

    def _consulta_ponderada(self, columna, vecino, concepto, limite):
        sql = f"SELECT {vecino}, peso, rowid FROM sinapsis WHERE {columna} = ?"
        params = [concepto]
        if self._rowid_max is not None:
            sql += " AND rowid <= ?"
            params.append(self._rowid_max)
        sql += " ORDER BY rowid DESC LIMIT ?"
        params.append(limite)
        try:
            return self._cursor.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error:
            return []

    def get(self, concepto, default=None):
        """Compatibilidad con dict.get(), cargando solo vecinos solicitados."""
        if not concepto:
            return default
        if concepto not in self._vecinos_cache:
            vecinos = set()
            for fila in self._consulta_acotada(
                "origen", "destino", concepto, _MAX_ARISTAS_POR_DIRECCION
            ):
                vecinos.add(fila[0])
            for fila in self._consulta_acotada(
                "destino", "origen", concepto, _MAX_ARISTAS_POR_DIRECCION
            ):
                vecinos.add(fila[0])
            self._vecinos_cache[concepto] = vecinos
        vecinos = self._vecinos_cache[concepto]
        return vecinos if vecinos else default

    def grado(self, concepto):
        """Grado incidente acotado, con la misma multiplicidad que el cálculo legacy."""
        if not concepto:
            return 0
        if concepto not in self._grado_cache:
            total = 0
            for columna in ("origen", "destino"):
                sql = f"SELECT COUNT(*) FROM (SELECT rowid FROM sinapsis WHERE {columna} = ?"
                params = [concepto]
                if self._rowid_max is not None:
                    sql += " AND rowid <= ?"
                    params.append(self._rowid_max)
                sql += " LIMIT ?)"
                params.append(_MAX_ARISTAS_POR_DIRECCION)
                try:
                    total += int(self._cursor.execute(sql, tuple(params)).fetchone()[0] or 0)
                except (sqlite3.Error, TypeError, ValueError):
                    pass
            self._grado_cache[concepto] = total
        return self._grado_cache[concepto]


def _cargar_grafo(cursor, rowid_max=None):
    """Devuelve una vista lazy; no lee la tabla completa de sinapsis."""
    return _GrafoSinapticoLazy(cursor, rowid_max=rowid_max)


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
    if grafo is None:
        grafo = _cargar_grafo(cursor)
    vecinos_a = grafo.get(concepto_a, set())
    vecinos_b = grafo.get(concepto_b, set())

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


def _tabla_fts_latente(cursor, baseline_rowid=None):
    """Usa postings congelados para el cohorte histórico si están disponibles."""
    if baseline_rowid is not None:
        try:
            from core.memory.growth_stable_fts import REFERENCE_FTS
            exists = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                (REFERENCE_FTS,),
            ).fetchone()
            if exists:
                return REFERENCE_FTS, True
        except sqlite3.Error:
            pass
    return "largo_plazo_fts", False


def _consulta_fts_latente(cursor, fts_table, fts_query, baseline_rowid,
                          limite, *, exigir_palabra_completa=False):
    """Consulta FTS con resultados acotados y orden estable para el corpus base."""
    filtro = " AND l.estado = 'activo'"
    params = [fts_query]
    if baseline_rowid is not None:
        filtro += " AND l.rowid <= ?"
        params.append(int(baseline_rowid))

    pc_clause = ""
    if exigir_palabra_completa:
        # Solo se activa para el set pequeño de puentes que se usa al calcular
        # Jaccard; el pool de candidatos mantiene tolerancia trigram.
        fts_terms = [t[1:-1] for t in fts_query.split(" OR ") if t.startswith('"') and t.endswith('"')]
        if fts_terms:
            pc_clause = " AND (" + " OR ".join(
                [
                    "(PALABRA_COMPLETA(?, l.contenido) = 1 OR "
                    "PALABRA_COMPLETA(?, l.concepto) = 1 OR "
                    "PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)"
                ] * len(fts_terms)
            ) + ")"
            params.extend(value for term in fts_terms for value in (term, term, term))

    # El ranking BM25 es estable únicamente cuando se usa el índice de
    # referencia. Si hay que caer al FTS mutable, rowid mantiene determinista
    # la selección del cohorte frente a nuevas inserciones.
    rank = (
        f"bm25({fts_table}, 5.0, 1.0, 2.0, 4.0)"
        if fts_table != "largo_plazo_fts" else "l.rowid"
    )
    sql = (
        f"SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
        f"l.estado, l.asociaciones, {rank} AS _rank "
        f"FROM {fts_table} f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
        f"WHERE {fts_table} MATCH ?{filtro}{pc_clause} "
        f"ORDER BY _rank ASC, l.rowid ASC LIMIT ?"
    )
    params.append(max(1, int(limite)))
    return cursor.execute(sql, tuple(params)).fetchall()


def _obtener_puentes_fts(cursor, query_tokens, baseline_rowid=None, limite=50):
    """Obtiene puentes léxicos exactos en una ventana fija del FTS de referencia."""
    filtrar = [t for t in query_tokens if len(t) >= 3]
    if not filtrar:
        return set()
    fts_query = " OR ".join(f'"{token}"' for token in filtrar)
    fts_table, _ = _tabla_fts_latente(cursor, baseline_rowid)
    try:
        rows = _consulta_fts_latente(
            cursor, fts_table, fts_query, baseline_rowid, limite,
            exigir_palabra_completa=True,
        )
        return {row[1] for row in rows if row[1]}
    except sqlite3.OperationalError:
        # Cursors sin el UDF PALABRA_COMPLETA (por ejemplo herramientas de
        # diagnóstico) conservan el límite y usan solo el índice invertido.
        try:
            rows = _consulta_fts_latente(
                cursor, fts_table, fts_query, baseline_rowid, limite,
            )
            return {row[1] for row in rows if row[1]}
        except sqlite3.Error:
            return set()
    except sqlite3.Error:
        return set()


def _filas_por_concepto(cursor, conceptos, baseline_rowid=None):
    """Recupera metadatos por la clave UNIQUE, nunca mediante barrido de memoria."""
    nombres = list(dict.fromkeys(c for c in conceptos if c))
    if not nombres:
        return {}
    placeholders = ",".join("?" for _ in nombres)
    filtro = " AND estado = 'activo'"
    params = list(nombres)
    if baseline_rowid is not None:
        filtro += " AND rowid <= ?"
        params.append(int(baseline_rowid))
    try:
        rows = cursor.execute(
            "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
            f"FROM largo_plazo WHERE concepto IN ({placeholders}){filtro}",
            tuple(params),
        ).fetchall()
        return {row[1]: row for row in rows}
    except sqlite3.Error:
        return {}


def _obtener_candidatos_similitud(
    cursor, query_tokens, baseline_rowid=None, edge_rowid_max=None,
    limite=None, incluir_puentes=False,
):
    """Pool acotado de FTS + vecinos cercanos; no expande el grafo globalmente.

    El límite total evita que un trigramo frecuente convierta el rescate en un
    score completo de O(N). Se reserva la mayoría para matches léxicos y el resto
    para expansión asociativa de pocas semillas, con fan-out limitado por índice.
    """
    baseline_rowid = _rowid_corte_positivo(baseline_rowid)
    edge_rowid_max = _rowid_corte_positivo(edge_rowid_max)
    sub_tokens = []
    for token in query_tokens:
        if len(token) >= 3:
            sub_tokens.extend(_generar_subterminos_fts(token))
    sub_tokens = list(dict.fromkeys(sub_tokens))
    if not sub_tokens:
        return ([], set()) if incluir_puentes else []

    limite_total = max(
        1,
        min(
            _MAX_CANDIDATOS_LATENTES,
            int(limite if limite is not None else CANDIDATOS_SIMILITUD),
        ),
    )
    limite_lexico = max(1, (limite_total * 3) // 4)
    fts_query = " OR ".join(f'"{term}"' for term in sub_tokens)
    fts_table, _ = _tabla_fts_latente(cursor, baseline_rowid)

    try:
        filas_lexicas_raw = _consulta_fts_latente(
            cursor, fts_table, fts_query, baseline_rowid, limite_lexico,
        )
    except sqlite3.Error:
        filas_lexicas_raw = []
    filas_lexicas = [tuple(row[:6]) for row in filas_lexicas_raw]
    conceptos_lexicos = [row[1] for row in filas_lexicas if row[1]]
    if not filas_lexicas:
        return ([], set()) if incluir_puentes else []

    presupuesto_grafo = max(0, limite_total - len(filas_lexicas))
    conceptos_grafo = []
    if presupuesto_grafo:
        grafo = _cargar_grafo(cursor, rowid_max=edge_rowid_max)
        puntajes_vecinos = {}
        semillas = conceptos_lexicos[:_MAX_SEMILLAS_EXPANSION]
        for semilla in semillas:
            for vecino, peso, rowid in grafo.vecinos_ponderados(
                semilla, limite=_MAX_VECINOS_EXPANSION
            ):
                if vecino and vecino not in conceptos_lexicos:
                    key = (float(peso or 0.0), int(rowid or 0))
                    if key > puntajes_vecinos.get(vecino, (-1.0, -1)):
                        puntajes_vecinos[vecino] = key

        # Segundo salto acotado: solo cinco nodos del primer anillo, nunca todo
        # el vecindario de las semillas FTS.
        primer_anillo = sorted(
            puntajes_vecinos.items(),
            key=lambda item: (-item[1][0], -item[1][1], item[0]),
        )[:5]
        for nodo, (peso_primero, _) in primer_anillo:
            for vecino, peso, rowid in grafo.vecinos_ponderados(
                nodo, limite=_MAX_VECINOS_EXPANSION
            ):
                if vecino and vecino not in conceptos_lexicos:
                    camino = (peso_primero * float(peso or 0.0), int(rowid or 0))
                    if camino > puntajes_vecinos.get(vecino, (-1.0, -1)):
                        puntajes_vecinos[vecino] = camino

        orden_vecinos = sorted(
            puntajes_vecinos,
            key=lambda nombre: (
                -puntajes_vecinos[nombre][0],
                -puntajes_vecinos[nombre][1],
                nombre,
            ),
        )
        conceptos_grafo = orden_vecinos[:presupuesto_grafo]

    filas_mapa = _filas_por_concepto(
        cursor, conceptos_grafo, baseline_rowid=baseline_rowid
    )
    filas_candidatos = filas_lexicas + [
        filas_mapa[nombre] for nombre in conceptos_grafo if nombre in filas_mapa
    ]
    puentes = _obtener_puentes_fts(
        cursor, query_tokens, baseline_rowid=baseline_rowid, limite=50
    )
    if incluir_puentes:
        return filas_candidatos[:limite_total], puentes
    return filas_candidatos[:limite_total]


def buscar_por_similitud_latente(
    cursor, frase, limite=None, umbral=None, cerebro=None,
    baseline_rowid=None, edge_rowid_max=None,
):
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
    if baseline_rowid is None and cerebro is not None:
        baseline_rowid = getattr(cerebro, "_search_baseline_rowid", None)
    if edge_rowid_max is None and cerebro is not None:
        edge_rowid_max = getattr(cerebro, "_search_baseline_sinapsis_rowid", None)
    baseline_rowid = _rowid_corte_positivo(baseline_rowid)
    edge_rowid_max = _rowid_corte_positivo(edge_rowid_max)

    query_tokens = _tokenizar_query(frase)
    if not query_tokens:
        return []

    candidatos, nodos_cache = _obtener_candidatos_similitud(
        cursor,
        query_tokens,
        baseline_rowid=baseline_rowid,
        edge_rowid_max=edge_rowid_max,
        limite=CANDIDATOS_SIMILITUD,
        incluir_puentes=True,
    )
    if not candidatos:
        return []

    # ═══════════════════════════════════════════════════════════════════
    # FASE 1: Scoring de 8 señales (Activación Léxica)
    # ═══════════════════════════════════════════════════════════════════
    scored = []
    grafo = _cargar_grafo(cursor, rowid_max=edge_rowid_max)

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

    # La propagación solo puede afectar candidatos ya puntuados. Se consultan
    # pares semilla-candidato mediante índices compuestos, no el vecindario global.
    candidatos_prop = list(dict.fromkeys(row[1] for _, row in scored if row[1]))
    sinapsis_semillas = {}  # {concepto_candidato: peso_total}
    if candidatos_prop:
        placeholders = ",".join("?" for _ in candidatos_prop)
        filtro_rowid = " AND rowid <= ?" if edge_rowid_max is not None else ""
        params_directas = [*candidatos_prop]
        params_latentes = [*candidatos_prop]
        if edge_rowid_max is not None:
            params_directas.append(int(edge_rowid_max))

        for semilla in semillas:
            try:
                rows = cursor.execute(
                    "SELECT destino, peso FROM sinapsis "
                    f"WHERE origen = ? AND destino IN ({placeholders}){filtro_rowid} "
                    "UNION SELECT origen, peso FROM sinapsis "
                    f"WHERE destino = ? AND origen IN ({placeholders}){filtro_rowid}",
                    (semilla, *params_directas, semilla, *params_directas),
                ).fetchall()
            except sqlite3.Error:
                rows = []
            for destino, peso in rows:
                deg = max(1, grafo.grado(destino))
                peso_eff = (peso or 0.0) / (deg ** 0.3)
                sinapsis_semillas.setdefault(destino, 0.0)
                sinapsis_semillas[destino] += peso_eff

            # Las latentes también se intersectan con el pool acotado de
            # candidatos; los índices por extremos evitan materializar la tabla.
            try:
                rows_lat = cursor.execute(
                    "SELECT destino, peso_atenuado FROM sinapsis_latentes "
                    f"WHERE origen = ? AND destino IN ({placeholders}) "
                    "UNION SELECT origen, peso_atenuado FROM sinapsis_latentes "
                    f"WHERE destino = ? AND origen IN ({placeholders})",
                    (semilla, *params_latentes, semilla, *params_latentes),
                ).fetchall()
            except sqlite3.Error:
                rows_lat = []
            for destino, peso in rows_lat:
                deg = max(1, grafo.grado(destino))
                peso_eff = (peso or 0.0) / (deg ** 0.3)
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
    # Retornar (score_final, row) para que el caller use el score real
    return [(score_f, row) for score_f, row in propagados if score_f >= umbral][:limite]

