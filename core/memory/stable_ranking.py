"""Local relevance signals that do not depend on corpus-wide statistics.

FTS5's ``bm25()`` is an excellent retrieval ranker for a fixed index, but its
scores depend on corpus size, document frequency, and average field length.
Those statistics change when unrelated memories are appended. This module
provides a deterministic lexical score from one query and one memory only;
its result is unchanged by every other row in the database.

The score keeps the existing FTS field priority (concept, content, synonyms,
curated nouns) while measuring query coverage rather than estimating IDF from
the live corpus. This is intended for the online rank path, where a global
scan or mutable collection statistics are not acceptable.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Iterable

from core.stopwords import _STOPWORDS_QUERY
from core.stemmer_es import stem

_FIELD_WEIGHTS = (
    ("concepto", 5.0),
    ("contenido", 1.0),
    ("sinonimos", 2.0),
    ("sustantivos_clave", 4.0),
)
_MAX_FIELD_WEIGHT = max(weight for _, weight in _FIELD_WEIGHTS)
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _sin_tildes(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_STOPWORDS = frozenset(_sin_tildes(word) for word in _STOPWORDS_QUERY)


@lru_cache(maxsize=8192)
def _claves_token(token: str) -> frozenset[str]:
    """Stable ES/EN morphology keys; the corpus is never consulted."""
    token = _sin_tildes(token)
    if not token:
        return frozenset()
    keys = {token}
    try:
        root = stem(token)
        if root:
            keys.add(_sin_tildes(root))
    except Exception:
        # Exact normalized matching remains available if a stemmer is absent.
        pass
    return frozenset(keys)


def _tokens(text: str, *, remove_stopwords: bool) -> tuple[frozenset[str], ...]:
    normalized = _sin_tildes(text).replace("_", " ").replace("-", " ")
    out = []
    seen = set()
    for token in _TOKEN_RE.findall(normalized):
        if len(token) < 2 or (remove_stopwords and token in _STOPWORDS) or token in seen:
            continue
        seen.add(token)
        keys = _claves_token(token)
        if keys:
            out.append(keys)
    return tuple(out)


class CorpusIndependentLexicalRanker:
    """Score candidate memories using only the query variants and that memory."""

    def __init__(self, query_variants: Iterable[str]):
        variants = []
        seen = set()
        for variant in query_variants or ():
            terms = _tokens(str(variant or ""), remove_stopwords=True)
            signature = tuple(sorted(tuple(sorted(term)) for term in terms))
            if terms and signature not in seen:
                seen.add(signature)
                variants.append(terms)
        self._query_variants = tuple(variants)

    def score(
        self,
        concepto: str,
        contenido: str | None,
        sinonimos: str | None = "",
        sustantivos_clave: str | None = "",
    ) -> float:
        """Return a stable [0, 1] lexical score for this memory.

        For each alternative query (original, cleaned, paraphrase), score the
        strongest one rather than diluting it with unrelated alternatives. The
        union coverage rewards evidence across fields; the field-weighted terms
        retain the established preference for a curated concept/name over raw
        content. No candidate-pool or corpus statistic is used.
        """
        if not self._query_variants:
            return 0.0

        field_tokens = tuple(
            frozenset(key for token in _tokens(text or "", remove_stopwords=False) for key in token)
            for _, text in (
                ("concepto", concepto),
                ("contenido", contenido),
                ("sinonimos", sinonimos),
                ("sustantivos_clave", sustantivos_clave),
            )
        )
        best = 0.0
        for query_terms in self._query_variants:
            n_terms = len(query_terms)
            if not n_terms:
                continue
            hits_by_field = [
                sum(bool(term_keys & target) for term_keys in query_terms)
                for target in field_tokens
            ]
            n_union = sum(
                any(term_keys & target for target in field_tokens)
                for term_keys in query_terms
            )
            union_coverage = n_union / n_terms
            field_coverages = [hits / n_terms for hits in hits_by_field]
            best_field_coverage = max(field_coverages, default=0.0)
            weighted_coverage = min(
                1.0,
                sum(weight * coverage
                    for (_, weight), coverage in zip(_FIELD_WEIGHTS, field_coverages))
                / _MAX_FIELD_WEIGHT,
            )
            score = (
                0.65 * union_coverage
                + 0.20 * best_field_coverage
                + 0.15 * weighted_coverage
            )
            best = max(best, score)
        return round(min(1.0, max(0.0, best)), 8)


def score_memoria_independiente(
    query_variants: Iterable[str],
    concepto: str,
    contenido: str | None,
    sinonimos: str | None = "",
    sustantivos_clave: str | None = "",
) -> float:
    """Convenience function for tests and call sites that score one memory."""
    return CorpusIndependentLexicalRanker(query_variants).score(
        concepto, contenido, sinonimos, sustantivos_clave
    )


def orden_candidato_fts(
    score: float,
    concepto: str | None,
    peso_sinaptico: float | None = 0.5,
    *,
    aplicar_peso_sinaptico: bool = True,
) -> tuple[float, str]:
    """Stable SQL/Python sort key for the primary FTS candidate list."""
    try:
        peso = float(peso_sinaptico if peso_sinaptico is not None else 0.5)
    except (TypeError, ValueError):
        peso = 0.5
    if not (peso >= 0.0 and peso < float("inf")):
        peso = 0.5
    multiplicador = 0.5 + 0.5 * max(0.0, min(1.0, peso)) if aplicar_peso_sinaptico else 1.0
    return (-float(score) * multiplicador, str(concepto or ""))
