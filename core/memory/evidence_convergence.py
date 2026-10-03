"""Re-ranking aditivo por convergencia de evidencia en campos del recuerdo.

El motor ya busca y puntúa cuatro columnas FTS con pesos distintos:
concepto (5), contenido (1), sinónimos (2) y sustantivos_clave (4). Este
módulo reutiliza esa jerarquía para el re-ranking final, sin añadir reglas por
ID/categoría y sin descontar puntos por campos vacíos.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable, Mapping, Sequence

from core.fallback_simbolico import _tokenizar_normalizado, similitud_levenshtein
from core.stemmer_es import stem

# Pesos tomados del FTS5 de buscar_por_frase: bm25(..., 5, 1, 2, 4),
# cuyo orden de columnas es concepto, contenido, sinonimos, sustantivos_clave.
PESOS_CAMPOS = {
    "concepto": 5.0,
    "sinonimos": 2.0,
    "sustantivos_clave": 4.0,
    "contenido": 1.0,
}
UMBRAL_COBERTURA_CAMPO = 0.20
PESO_DISTRIBUCION = 0.50
UMBRAL_MATCH_DIFUSO = 0.75


@lru_cache(maxsize=16384)
def _stem_cache(token: str) -> str:
    return stem(token)


def _similitud_token(query_token: str, target_tokens: set[str]) -> float:
    """Mejor evidencia de un token: exacta, morfológica o Levenshtein.

    Cada token de consulta contribuye como máximo una vez por campo. El
    contenido puede ser largo, así que primero se comprueban igualdad y stem;
    Levenshtein solo se evalúa para tokens sin match y de longitud compatible.
    """
    if not query_token or not target_tokens:
        return 0.0
    if query_token in target_tokens:
        return 1.0

    query_stem = _stem_cache(query_token)
    if any(_stem_cache(token) == query_stem for token in target_tokens):
        return 1.0

    if len(query_token) < 4:
        return 0.0

    best = 0.0
    for target_token in target_tokens:
        if len(target_token) < 4:
            continue
        max_len = max(len(query_token), len(target_token))
        # La similitud mínima admitida es 0.75; por tanto, una diferencia de
        # longitudes mayor al 25% no puede producir un match que pase el umbral.
        if abs(len(query_token) - len(target_token)) / max_len > (1.0 - UMBRAL_MATCH_DIFUSO):
            continue
        similarity = similitud_levenshtein(query_token, target_token)
        if similarity > best:
            best = similarity
            if best == 1.0:
                break
    return best if best >= UMBRAL_MATCH_DIFUSO else 0.0


def cobertura_campo(query_tokens: Iterable[str], texto_campo: str | None) -> float:
    """Cobertura de consulta en un único campo, independiente de repeticiones.

    Los tokens de la consulta se comparan con el conjunto normalizado del campo;
    el contenido repetido no gana por frecuencia. Los stems bilingües y el
    umbral difuso mantienen la tolerancia morfológica/typo del motor.
    """
    query_set = {str(token) for token in query_tokens if token}
    target_tokens = _tokenizar_normalizado(texto_campo or "")
    if not query_set or not target_tokens:
        return 0.0

    matched = sum(_similitud_token(token, target_tokens) for token in query_set)
    return min(1.0, matched / len(query_set))


def _max_cobertura_variantes(
    query_variants: Sequence[Iterable[str]],
    texto_campo: str | None,
) -> float:
    """Usa la mejor variante de consulta, sin mezclar ni diluir sus tokens."""
    best = 0.0
    for tokens in query_variants:
        score = cobertura_campo(tokens, texto_campo)
        if score > best:
            best = score
    return best


def evidencia_multicampo(
    query_variants: Sequence[Iterable[str]],
    concepto: str,
    sinonimos: str | None,
    sustantivos_clave: str | None,
    contenido: str | None,
    *,
    concepto_ratio: float = 0.0,
    sinonimos_ratio: float = 0.0,
) -> dict[str, float]:
    """Calcula fuerza [0,1] por canal para una consulta y sus paráfrasis.

    `concepto_ratio` y `sinonimos_ratio` son las señales difusas/semánticas que
    ya calcula el ranker para esos campos. Se combinan con cobertura directa de
    cada variante para que una paráfrasis sí aporte evidencia independiente.
    """
    concept_score = max(
        float(concepto_ratio or 0.0),
        _max_cobertura_variantes(query_variants, concepto),
    )
    synonym_score = max(
        float(sinonimos_ratio or 0.0),
        _max_cobertura_variantes(query_variants, sinonimos),
    )
    return {
        "concepto": min(1.0, max(0.0, concept_score)),
        "sinonimos": min(1.0, max(0.0, synonym_score)),
        "sustantivos_clave": _max_cobertura_variantes(query_variants, sustantivos_clave),
        "contenido": _max_cobertura_variantes(query_variants, contenido),
    }


def calcular_bono_convergencia(
    evidencia: Mapping[str, float],
    max_bonus: float = 0.085,
    query_size: int = 3,
) -> float:
    """Bono solo positivo que premia fuerza y distribución entre campos.

    La mitad del bono depende de la cobertura ponderada y la otra mitad de la
    distribución de evidencia por campos. Un match incidental en contenido
    puede contribuir, pero su peso es 1/12; una coincidencia explícita en
    sinónimos pesa 2/12, y los campos curados concepto/sustantivos pesan 5/12
    y 4/12. Los campos vacíos nunca restan. Se reduce la escala en consultas
    de uno o dos tokens: con una sola palabra no hay suficiente diversidad de
    consulta para distinguir la coincidencia pertinente de la accidental.
    """
    try:
        cap = float(max_bonus)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(cap) or cap <= 0.0:
        return 0.0
    cap = min(cap, 0.12)
    try:
        n_query_tokens = max(0, int(query_size))
    except (TypeError, ValueError):
        n_query_tokens = 0
    if n_query_tokens <= 1:
        cap *= 0.10
    elif n_query_tokens == 2:
        cap *= 0.50

    total_weight = sum(PESOS_CAMPOS.values())
    weighted_coverage = 0.0
    distributed_weight = 0.0
    for field, weight in PESOS_CAMPOS.items():
        try:
            strength = float(evidencia.get(field, 0.0) or 0.0)
        except (TypeError, ValueError):
            strength = 0.0
        if not math.isfinite(strength):
            strength = 0.0
        strength = min(1.0, max(0.0, strength))
        weighted_coverage += weight * strength
        if strength >= UMBRAL_COBERTURA_CAMPO:
            distributed_weight += weight

    coverage = weighted_coverage / total_weight
    distribution = distributed_weight / total_weight
    normalized_evidence = (1.0 - PESO_DISTRIBUCION) * coverage + PESO_DISTRIBUCION * distribution
    return round(cap * normalized_evidence, 6)


def rerank_con_evidencia_multicampo(
    resultados: Sequence[tuple],
    evidencia_por_concepto: Mapping[str, Mapping[str, float]],
    max_bonus: float = 0.085,
    query_size: int = 3,
) -> tuple[list[tuple], dict[str, float], dict[str, float]]:
    """Suma el bono tras los filtros, conserva score-base y ordena por score final.

    Retorna (resultados, score_base_por_concepto, bono_efectivo_por_concepto).
    Cada fila conserva su forma de seis elementos y el score público de salida
    coincide con el score usado para ordenar.
    """
    ajustados: list[tuple] = []
    score_base: dict[str, float] = {}
    bonos_efectivos: dict[str, float] = {}

    for fila in resultados:
        if len(fila) < 5:
            ajustados.append(tuple(fila))
            continue
        concepto = fila[0]
        try:
            base = float(fila[4] or 0.0)
        except (TypeError, ValueError):
            base = 0.0
        bono = calcular_bono_convergencia(
            evidencia_por_concepto.get(concepto, {}),
            max_bonus=max_bonus,
            query_size=query_size,
        )
        score_final = round(min(1.0, max(0.0, base + bono)), 4)
        score_base[concepto] = base
        bonos_efectivos[concepto] = round(max(0.0, score_final - base), 4)
        ajustados.append(tuple(fila[:4]) + (score_final,) + tuple(fila[5:]))

    ajustados.sort(key=lambda fila: fila[4] if len(fila) > 4 else 0.0, reverse=True)
    return ajustados, score_base, bonos_efectivos


def incorporar_delta_postprocesamiento(
    resultados: Sequence[tuple],
    score_base: dict[str, float],
    bonos_efectivos: dict[str, float],
) -> None:
    """Mantiene el score calibrable cuando el grafo ajusta primarios después.

    La expansión sináptica preexistente puede subir o bajar el score de un nodo
    primario. Ese delta no es parte del bono multicampo, así que se incorpora al
    score-base paralelo y se conserva el bono explícito como campo separado. Si
    el score final queda por debajo del bono, el bono efectivo se limita al score
    final para mantener la descomposición no negativa y exacta.
    """
    for fila in resultados:
        if len(fila) < 5 or fila[0] not in score_base:
            continue
        try:
            base = float(score_base[fila[0]])
            bonus = float(bonos_efectivos.get(fila[0], 0.0) or 0.0)
            final = float(fila[4])
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (base, bonus, final)):
            continue
        final = round(min(1.0, max(0.0, final)), 4)
        bonus = round(min(final, max(0.0, bonus)), 4)
        score_base[fila[0]] = round(max(0.0, final - bonus), 4)
        bonos_efectivos[fila[0]] = bonus
