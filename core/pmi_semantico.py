"""
PMI Semántico para BioRAG v19.0
================================
Implementa Pointwise Mutual Information (PMI) y su variante normalizada (NPMI)
para medir la fuerza real de asociación entre tokens en el corpus de nodos.

Referencia: Church & Hanks (1990) — Word Association Norms, Mutual Information, and Lexicography

NPMI(x, y) = PMI(x, y) / (-log2(P(x, y)))   → rango [-1, +1]
  +1 = co-ocurrencia perfecta
   0 = independencia estadística
  -1 = nunca co-ocurren

Sin dependencias externas. Funciona solo con el corpus de largo_plazo.
Cache en RAM. Recálculo automático cuando crece >10% el corpus.
"""

import math
import re
import time
import os
from collections import Counter
from core.stopwords import STOPWORDS

# =============================================================================
# Configuración
# =============================================================================

VENTANA_NODO = int(os.environ.get('BIORAG_PMI_VENTANA', '0'))
"""
0 = ventana = nodo completo (tokens del nodo co-ocurren entre sí).
N > 0 = ventana deslizante de N tokens (más preciso, más costoso).
Default 0 es óptimo para corpus de nodos cortos (BioRAG).
"""

UMBRAL_PMI_SINAPSIS = float(os.environ.get('BIORAG_PMI_UMBRAL_SINAPSIS', '0.10'))
"""NPMI mínimo para considerar que dos tokens tienen asociación semántica real."""

UMBRAL_FREQ_MINIMA = int(os.environ.get('BIORAG_PMI_FREQ_MIN', '3'))
"""
Frecuencia mínima de un token para incluirlo en el corpus PMI.
Tokens que aparecen 1-2 veces tienen PMI inestable y generan ruido.
"""

PMI_REBATCH_RATIO = float(os.environ.get('BIORAG_PMI_REBATCH', '0.10'))
"""Recalcular si el corpus creció >10% desde el último cálculo."""

# =============================================================================
# Regex — reutiliza el patrón de sinapsis.py
# =============================================================================

_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,}\b')
_TOKENS_CORTOS = {'dsl', 'api', 'mcp', 'rag', 'cpu', 'ram', 'gpu', 'cli', 'sql', 'orm'}


def _tokenizar(texto: str) -> list[str]:
    """Tokeniza texto → lista de STEMS limpios (sin stopwords, con términos técnicos).
    Usar stems garantiza que buscar/búsqueda/búscamos contribuyan al mismo token
    en la matriz de co-ocurrencia.
    """
    if not texto:
        return []
    from core.stemmer_es import stem as _stem
    texto = texto.replace('_', ' ').replace('-', ' ')
    tokens = _TOKEN_PATTERN.findall(texto.lower())
    cortos = [t for t in texto.lower().split() if t in _TOKENS_CORTOS]
    todos = [t for t in (tokens + cortos) if t not in STOPWORDS]
    # Aplicar stem → normaliza morfología antes de calcular PMI
    return [_stem(t) for t in todos]


# =============================================================================
# Estado del cache (módulo-level singleton, thread-unsafe pero BioRAG es single-thread)
# =============================================================================

_cache: dict = {
    'npmi': {},           # (tok_a, tok_b) → float  (tok_a < tok_b lexicográficamente)
    'freq': {},           # token → int (frecuencia de documento)
    'total_nodos': 0,     # N total de nodos en el corpus cuando se calculó
    'calculado_en': 0.0,  # timestamp Unix del último cálculo
}


def _cache_valido(total_nodos_actual: int) -> bool:
    """Retorna True si el cache es aún válido para el corpus actual."""
    if _cache['total_nodos'] == 0:
        return False
    crecimiento = abs(total_nodos_actual - _cache['total_nodos']) / max(1, _cache['total_nodos'])
    return crecimiento < PMI_REBATCH_RATIO


# =============================================================================
# Construcción del corpus PMI
# =============================================================================

def _construir_corpus(cursor) -> tuple[Counter, Counter, int]:
    """
    Lee todos los nodos activos y construye:
    - co_freq: Counter de pares de tokens co-ocurrentes (dentro del mismo nodo)
    - doc_freq: Counter de frecuencia por token
    - total_nodos: número de nodos procesados

    Complejidad: O(n × k²) donde k = tokens promedio por nodo (~20-50 tokens).
    Con 500 nodos activos y k=30: 500 × 900 = 450,000 operaciones → <100ms.
    """
    cursor.execute(
        "SELECT concepto, contenido, sinonimos FROM largo_plazo WHERE estado = 'activo'"
    )
    filas = cursor.fetchall()

    doc_freq: Counter = Counter()
    co_freq: Counter = Counter()
    total = 0

    for concepto, contenido, sinonimos in filas:
        texto = f"{concepto} {contenido or ''} {sinonimos or ''}"
        tokens = _tokenizar(texto)
        if len(tokens) < 2:
            continue

        # Frecuencia de documento: cada token suma 1 por nodo (no por repetición)
        tokens_unicos = list(dict.fromkeys(tokens))  # dedupligar manteniendo orden
        for tok in tokens_unicos:
            doc_freq[tok] += 1

        # Co-ocurrencia: todos los pares dentro del mismo nodo
        # (Ventana = nodo completo → más eficiente para corpus de nodos cortos)
        n = len(tokens_unicos)
        limite = min(n, 30)  # cap: max 30 tokens/nodo → max 435 pares → O(n²) controlado
        for i in range(limite):
            for j in range(i + 1, limite):
                par = (tokens_unicos[i], tokens_unicos[j])
                par_ord = (min(par), max(par))
                co_freq[par_ord] += 1

        total += 1

    return co_freq, doc_freq, total


def _calcular_npmi(co_freq: Counter, doc_freq: Counter, total: int) -> dict:
    """
    Calcula NPMI para todos los pares con frecuencia ≥ UMBRAL_FREQ_MINIMA.
    Retorna dict (tok_a, tok_b) → npmi_score [-1, +1].
    """
    npmi_map: dict = {}
    N = max(1, total)

    for (tok_a, tok_b), count_ab in co_freq.items():
        # Filtrar pares raros (PMI inestable con pocas ocurrencias)
        if count_ab < UMBRAL_FREQ_MINIMA:
            continue
        if doc_freq.get(tok_a, 0) < UMBRAL_FREQ_MINIMA:
            continue
        if doc_freq.get(tok_b, 0) < UMBRAL_FREQ_MINIMA:
            continue

        p_xy = count_ab / N
        p_x = doc_freq[tok_a] / N
        p_y = doc_freq[tok_b] / N

        if p_x <= 0 or p_y <= 0 or p_xy <= 0:
            continue

        pmi = math.log2(p_xy / (p_x * p_y))

        # Normalizar: NPMI = PMI / (-log2(P(x,y)))
        denom = -math.log2(p_xy)
        if denom <= 0:
            npmi = 1.0  # co-ocurrencia perfecta (misma probabilidad)
        else:
            npmi = pmi / denom

        # Clampar al rango [-1, +1] por seguridad numérica
        npmi = max(-1.0, min(1.0, npmi))
        npmi_map[(tok_a, tok_b)] = round(npmi, 4)

    return npmi_map


def _extract_cursor(obj):
    """Extrae un cursor de SQLite de un objeto cerebro o pasa el objeto si ya es un cursor."""
    if obj is None:
        return None
    if hasattr(obj, 'cursor'):
        return obj.cursor
    return obj


# =============================================================================
# API pública
# =============================================================================

def recalcular(cursor_or_cerebro=None, forzar: bool = False) -> int:
    """
    Recalcula el cache PMI desde el corpus actual.
    Soporta pasar cursor o cerebro.
    """
    cursor = _extract_cursor(cursor_or_cerebro)
    if cursor is None:
        return len(_cache['npmi'])

    cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    total_actual = cursor.fetchone()[0]

    if not forzar and _cache_valido(total_actual):
        return len(_cache['npmi'])

    t0 = time.perf_counter()
    co_freq, doc_freq, total = _construir_corpus(cursor)
    npmi_map = _calcular_npmi(co_freq, doc_freq, total)

    _cache['npmi'] = npmi_map
    _cache['freq'] = dict(doc_freq)
    _cache['total_nodos'] = total
    _cache['calculado_en'] = time.time()

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"[PMI] Corpus recalculado: {total} nodos, {len(npmi_map)} pares, {elapsed:.1f}ms")
    return len(npmi_map)


def get_npmi(cursor_or_cerebro, tok_a: str, tok_b: str) -> float:
    """
    Retorna el NPMI entre dos tokens.
    Soporta cursor o cerebro como primer argumento.
    """
    if not tok_a or not tok_b or tok_a == tok_b:
        return 0.0

    cursor = _extract_cursor(cursor_or_cerebro)
    if not _cache['npmi'] and cursor is not None:
        recalcular(cursor)

    par = (min(tok_a, tok_b), max(tok_a, tok_b))
    return _cache['npmi'].get(par, 0.0)


def score_pmi_nodo(arg1, arg2=None, arg3=None) -> float:
    """
    Calcula el score PMI entre tokens/conceptos con firma polimórfica:
      - score_pmi_nodo(concepto_a, concepto_b)
      - score_pmi_nodo(cursor, query_tokens, contenido_tokens)
      - score_pmi_nodo(cursor, concepto_a, concepto_b)
    """
    cursor = None
    q_input = None
    c_input = None

    if arg3 is not None:
        cursor = _extract_cursor(arg1)
        q_input = arg2
        c_input = arg3
    elif arg2 is not None:
        if hasattr(arg1, 'cursor') or hasattr(arg1, 'execute'):
            cursor = _extract_cursor(arg1)
            q_input = arg2
            c_input = arg2
        else:
            q_input = arg1
            c_input = arg2

    if isinstance(q_input, str):
        q_tokens = set(_tokenizar(q_input))
    elif isinstance(q_input, (set, list, tuple)):
        q_tokens = set(q_input)
    else:
        q_tokens = set()

    if isinstance(c_input, str):
        c_tokens = set(_tokenizar(c_input))
    elif isinstance(c_input, (set, list, tuple)):
        c_tokens = set(c_input)
    else:
        c_tokens = set()

    if not q_tokens or not c_tokens:
        return 0.0

    if not _cache['npmi'] and cursor is not None:
        recalcular(cursor)

    scores = []
    for qt in q_tokens:
        for ct in c_tokens:
            if qt == ct:
                scores.append(1.0)
                continue
            npmi = get_npmi(cursor, qt, ct)
            if npmi > 0:
                scores.append(npmi)

    if not scores:
        return 0.0

    return round(min(1.0, sum(scores) / len(scores)), 4)


def pares_fuertes(cursor, token: str, top_n: int = 10) -> list[tuple[str, float]]:
    """
    Retorna los top_n tokens más fuertemente asociados a `token` por NPMI.
    Útil para debug y para expandir queries.

    Returns: Lista de (token_asociado, npmi_score) ordenada por score desc.
    """
    if not _cache['npmi']:
        recalcular(cursor)

    resultados = []
    for (ta, tb), npmi in _cache['npmi'].items():
        if npmi <= 0:
            continue
        if ta == token:
            resultados.append((tb, npmi))
        elif tb == token:
            resultados.append((ta, npmi))

    resultados.sort(key=lambda x: x[1], reverse=True)
    return resultados[:top_n]


def invalidar_cache():
    """
    Invalida el cache PMI forzando recálculo en la próxima consulta.
    Llamar desde consolidar_sueño() después de agregar nodos nuevos.
    """
    _cache['total_nodos'] = 0
    _cache['npmi'] = {}
    _cache['freq'] = {}
    _cache['calculado_en'] = 0.0
