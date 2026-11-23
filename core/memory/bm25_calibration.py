"""Normalización experimental de las puntuaciones crudas de SQLite FTS5.

SQLite FTS5 devuelve BM25 negativo: cuanto más negativo, mejor la coincidencia.
El modo histórico ``minmax`` escala cada consulta usando el mínimo y máximo de
su pool; por eso el score de un candidato depende de qué otros candidatos haya
entrado en el pool. ``relative_top1`` evita la dependencia del extremo inferior
y conserva las puntuaciones existentes cuando se añade un candidato más débil.

El modo nuevo es opt-in con ``BIORAG_BM25_NORM_MODE=relative_top1``. No es una
probabilidad ni garantiza invariancia frente a cambios no uniformes de las
estadísticas internas de FTS5 (N, df, longitud media) o del propio pool. El modo
por defecto sigue siendo ``minmax`` hasta validar la ablación completa.
"""
from __future__ import annotations

import logging
import math
import os
from collections.abc import Mapping

_LOG = logging.getLogger("BioRAG.MemoryStore")
_MODES = frozenset({"minmax", "relative_top1"})
_ENV = "BIORAG_BM25_NORM_MODE"


def modo_normalizacion_bm25() -> str:
    """Devuelve el modo activo; una configuración desconocida cae al modo legacy."""
    mode = os.environ.get(_ENV, "minmax").strip().lower()
    if mode not in _MODES:
        _LOG.warning("Valor %r no válido para %s; se conserva minmax", mode, _ENV)
        return "minmax"
    return mode


def normalizar_mapa_bm25(
    raw_scores: Mapping[str, float],
    *,
    mode: str | None = None,
    base_bounds: tuple[float, float, float] | None = None,
) -> tuple[dict[str, float], tuple[float, float, float] | None]:
    """Normaliza un mapa ``{concepto: bm25_raw}`` y devuelve también sus límites.

    ``base_bounds`` permite que la ruta de ráfaga comparta la escala cruda de la
    búsqueda de frase, como hacía el normalizador anterior.

    - ``minmax`` reproduce la fórmula histórica.
    - ``relative_top1`` usa ``abs(raw) / max(abs(raw))``. El mayor BM25 (más
      negativo en FTS5) vale 1; el score no depende del peor candidato.

    La complejidad es O(k) en los candidatos ya recuperados, no O(N) en el
    tamaño total del corpus.
    """
    if mode is None:
        mode = modo_normalizacion_bm25()
    else:
        mode = str(mode).strip().lower()
        if mode not in _MODES:
            raise ValueError(f"Modo BM25 no soportado: {mode!r}")

    if not raw_scores:
        return {}, None

    magnitudes: dict[str, float] = {}
    for concept, raw in raw_scores.items():
        value = abs(float(raw))
        if not math.isfinite(value):
            value = 0.0
        magnitudes[concept] = value

    values = list(magnitudes.values())
    raw_lo, raw_hi = min(values), max(values)
    if base_bounds is not None:
        lo = min(float(base_bounds[0]), raw_lo)
        hi = max(float(base_bounds[1]), raw_hi)
    else:
        lo, hi = raw_lo, raw_hi

    if mode == "relative_top1":
        # En este modo la tercera coordenada significa «escala sintética estable»
        # para los rescates no BM25; no es min(1, max(abs(raw))).
        bounds = (lo, hi, 1.0)
        if hi <= 0.0:
            return {concept: 0.0 for concept in magnitudes}, bounds
        return {concept: value / hi for concept, value in magnitudes.items()}, bounds

    # Compatibilidad exacta con el normalizador min-max histórico, incluyendo
    # el caso especial de un único resultado muy fuerte.
    scale = min(1.0, hi) if hi > 0.0 else 1.0
    span = hi - lo if hi > lo else 1.0
    if hi > lo:
        result = {
            concept: ((value - lo) / span) * scale
            for concept, value in magnitudes.items()
        }
    elif len(magnitudes) == 1 and hi >= 3.0:
        result = {concept: scale for concept in magnitudes}
    else:
        result = {concept: 0.0 for concept in magnitudes}
    return result, (lo, hi, scale)
