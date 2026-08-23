"""
Tematica — Similitud Temática por Ausencia/Presencia de Dimensiones
BioRAG v22.1 (revertido a dims sueltas — pares regresaron por_tema -1.54%)

Compara nodos por LO QUE NO TIENEN (ausencia ponderada por IDF),
no solo por lo que comparten. Esto captura "aboutness" — de qué HABLA
un nodo a nivel temático, más allá de qué palabras contiene.

Filosofía: 100% simbólico, determinista, auditable. 0 dependencias.
"""

import math
from collections import defaultdict


def calcular_idf_dims(cerebro):
    """Calcula IDF invertido para cada dimensión semántica.

    IDF(dim) = log(N / n(dim))
    donde N = total nodos activos, n(dim) = nodos que SÍ tienen esa dimensión.

    Retorna dict: {dim_id: idf_value}
    """
    cur = cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    N = cur.fetchone()[0]
    if N == 0:
        return {}

    cur = cerebro.cursor.execute(
        "SELECT dimension_id, COUNT(*) FROM largo_plazo_dimensiones GROUP BY dimension_id"
    )
    idf = {}
    for dim_id, count in cur.fetchall():
        if count > 0:
            idf[dim_id] = math.log(N / count)
        else:
            idf[dim_id] = 0.0

    return idf


def calcular_perfiles_presencia(cerebro):
    """Calcula vector de presencia para cada nodo activo.

    Retorna dict: {concepto: set(dimension_ids)}
    """
    cur = cerebro.cursor.execute(
        "SELECT concepto, dimension_id FROM largo_plazo_dimensiones"
    )
    perfiles = defaultdict(set)
    for concepto, dim_id in cur.fetchall():
        perfiles[concepto].add(dim_id)

    return dict(perfiles)


_cache_ausencia = {}

def calcular_perfil_ausencia(concepto, perfiles_presencia, idf, todas_dims):
    """Calcula vector de ausencia ponderado por IDF para un nodo (memoizado).

    El vector tiene valor para cada dimensión que el nodo NO tiene,
    ponderado por cuán rara es esa ausencia en el corpus.

    Retorna dict: {dim_id: idf_weight} (solo dimensiones ausentes)
    """
    key = (concepto, id(perfiles_presencia), id(idf))
    if key in _cache_ausencia:
        return _cache_ausencia[key]

    dims_presentes = perfiles_presencia.get(concepto, set())
    dims_ausentes = todas_dims - dims_presentes

    ausencia_ponderada = {dim: idf.get(dim, 0.0) for dim in dims_ausentes}
    
    if len(_cache_ausencia) > 4096:
        _cache_ausencia.clear()
    _cache_ausencia[key] = ausencia_ponderada
    return ausencia_ponderada


def similitud_ausencia(concepto_a, concepto_b, perfiles_presencia, idf, todas_dims):
    """Calcula similitud temática por ausencia ponderada IDF.

    Usa Jaccard ponderado: intersección / unión de ausencias con pesos IDF.

    Retorna float: 0.0 (nada en común) a 1.0 (ausencias idénticas ponderadas)
    """
    aus_a = calcular_perfil_ausencia(concepto_a, perfiles_presencia, idf, todas_dims)
    aus_b = calcular_perfil_ausencia(concepto_b, perfiles_presencia, idf, todas_dims)

    if not aus_a or not aus_b:
        return 0.0

    dims_comunes = set(aus_a.keys()) & set(aus_b.keys())
    if not dims_comunes:
        return 0.0

    peso_interseccion = sum(aus_a[d] for d in dims_comunes)
    # Identidad matemática: sum_{d in A U B} (A[d] + B[d]) == sum(A.values()) + sum(B.values())
    peso_union = (sum(aus_a.values()) + sum(aus_b.values())) / 2.0

    if peso_union == 0:
        return 0.0

    return peso_interseccion / peso_union


def similitud_presencia(concepto_a, concepto_b, perfiles_presencia):
    """Calcula similitud por dimensiones compartidas (presencia).

    Jaccard clásico sobre dimensiones: |A ∩ B| / |A ∪ B|

    Retorna float: 0.0 a 1.0
    """
    dims_a = perfiles_presencia.get(concepto_a, set())
    dims_b = perfiles_presencia.get(concepto_b, set())

    if not dims_a and not dims_b:
        return 0.0

    interseccion = len(dims_a & dims_b)
    union = len(dims_a | dims_b)

    if union == 0:
        return 0.0

    return interseccion / union


def similitud_tematica(concepto_a, concepto_b, cerebro, perfiles_cache=None,
                       idf_cache=None):
    """Calcula similitud temática combinando presencia + ausencia.

    Fórmula: 0.4 × Jaccard_presencia + 0.6 × Jaccard_ausencia_IDF

    Retorna float: 0.0 a 1.0
    """
    if perfiles_cache is None:
        perfiles_cache = calcular_perfiles_presencia(cerebro)
    if idf_cache is None:
        idf_cache = calcular_idf_dims(cerebro)

    todas_dims = set(idf_cache.keys())
    if not todas_dims:
        return 0.0

    presencia = similitud_presencia(concepto_a, concepto_b, perfiles_cache)
    ausencia = similitud_ausencia(concepto_a, concepto_b, perfiles_cache, idf_cache, todas_dims)

    return 0.4 * presencia + 0.6 * ausencia


def precompute_thematic_scores(cerebro, perfiles_cache=None, idf_cache=None):
    """Pre-compute thematic scores for all node pairs (cached).

    This is expensive but only needs to be done once.
    Returns dict: {(concepto_a, concepto_b): score}
    """
    if perfiles_cache is None:
        perfiles_cache = calcular_perfiles_presencia(cerebro)
    if idf_cache is None:
        idf_cache = calcular_idf_dims(cerebro)

    todas_dims = set(idf_cache.keys())
    if not todas_dims:
        return {}

    conceptos = list(perfiles_cache.keys())
    scores = {}

    for i, c1 in enumerate(conceptos):
        for c2 in conceptos[i+1:]:
            presencia = similitud_presencia(c1, c2, perfiles_cache)
            ausencia = similitud_ausencia(c1, c2, perfiles_cache, idf_cache, todas_dims)
            score = 0.4 * presencia + 0.6 * ausencia

            if score > 0.1:  # Only store significant scores
                scores[(c1, c2)] = score
                scores[(c2, c1)] = score

    return scores


def buscar_por_tema(cerebro, concepto_semilla, limite=10, umbral=0.3,
                    perfiles_cache=None, idf_cache=None):
    """Busca nodos por similitud temática (presencia + ausencia).

    Retorna lista de dicts: [{'concepto': str, 'score_tematico': float}]
    """
    if perfiles_cache is None:
        perfiles_cache = calcular_perfiles_presencia(cerebro)
    if idf_cache is None:
        idf_cache = calcular_idf_dims(cerebro)

    resultados = []
    for concepto in perfiles_cache:
        if concepto == concepto_semilla:
            continue
        score = similitud_tematica(concepto_semilla, concepto, cerebro,
                                   perfiles_cache, idf_cache)
        if score >= umbral:
            resultados.append({
                'concepto': concepto,
                'score_tematico': round(score, 4)
            })

    resultados.sort(key=lambda x: x['score_tematico'], reverse=True)
    return resultados[:limite]
