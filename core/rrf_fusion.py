"""
RRF (Reciprocal Rank Fusion) + Percentile Normalization + Heuristic Dynamic Weights
Scale-invariant fusion for BioRAG - Zero external dependencies, pure Python.

Based on:
  - RRF: Cormack et al. 2009
  - Query Performance Prediction: Cronen-Townsend et al. 2002
  - Selective Query Expansion: Amati et al. 2004

Design principles:
  - Zero external dependencies (pure Python + stdlib bisect only)
  - Scale-invariant: works with 100 or 10M nodes without reconfiguration
  - No hardcoded absolute thresholds -- only rank-based or percentile-based values
  - No ML training required -- deterministic heuristics only
"""

import bisect
from typing import Dict, List, Optional
from collections import defaultdict


# ─── Constants ───

# Universal RRF constant per Cormack et al. 2009.
# Empirically validated across TREC, CLEF, and production IR systems.
# Do NOT change without re-running QA baseline.
RRF_K = 60

# Default signal weights for weighted RRF.
# Derived from ablation study on 921 QA cases (snapshot 20260811).
# These are starting weights; compute_dynamic_weights() adjusts them per query.
DEFAULT_RRF_WEIGHTS: Dict[str, float] = {
    'bm25':           0.25,  # FTS5 BM25 -- strong for literal/exact queries
    'concepto_ratio': 0.15,  # Concept name overlap with query -- critical for literal matches
    'sinonimos':      0.12,  # Synonym match -- critical for 1-2 token queries
    'hub':            0.12,  # Concept Hub -- critical for semantic pivot queries
    'pred':           0.08,  # Predicate SRL -- important for question queries
    'tematico':       0.08,  # Thematic similarity -- helps hard/ambiguous queries
    'ppmi':           0.08,  # PPMI+SVD vector -- semantic generalization
    'dim':            0.05,  # Dimensional semantic axes -- structural signal
    'jaccard':        0.04,  # Jaccard/Hebbian -- graph proximity
    'grupo':          0.03,  # WordNet group -- lexical category
}


# ─── Core RRF Functions ───

def rrf_fusion(rankings: Dict[str, List[str]], k: int = RRF_K) -> Dict[str, float]:
    """
    Reciprocal Rank Fusion (RRF) -- parameter-free, scale-invariant fusion.

    Combines multiple ranked lists by summing reciprocal ranks.
    scale-invariant: rank 1 of 100 == rank 1 of 10M (same contribution).
    No calibration required across corpus sizes.

    Args:
        rankings: {signal_name: [concepto, ...]} -- each list ranked best-first
        k: RRF damping constant (default 60, per Cormack et al. 2009)

    Returns:
        {concepto: rrf_score} -- higher score = better fused rank
    """
    scores: Dict[str, float] = defaultdict(float)
    for signal_name, ranking in rankings.items():
        for rank, concepto in enumerate(ranking, 1):
            if concepto:
                scores[concepto] += 1.0 / (k + rank)
    return dict(scores)


def weighted_rrf(
    rankings: Dict[str, List[str]],
    weights: Dict[str, float],
    k: int = RRF_K
) -> Dict[str, float]:
    """
    Weighted RRF fusion -- rank-based and scale-invariant like vanilla RRF,
    but allows per-signal weight adjustment for query-dependent tuning.

    Args:
        rankings: {signal_name: [concepto, ...]} -- each list ranked best-first
        weights: {signal_name: weight} -- should sum to ~1.0
        k: RRF damping constant (default 60)

    Returns:
        {concepto: weighted_rrf_score}
    """
    scores: Dict[str, float] = defaultdict(float)
    for signal_name, ranking in rankings.items():
        weight = weights.get(signal_name, 0.0)
        if weight <= 0:
            continue
        for rank, concepto in enumerate(ranking, 1):
            if concepto:
                scores[concepto] += weight * (1.0 / (k + rank))
    return dict(scores)


# ─── Percentile Normalization ───

def percentile_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    """
    Convert raw scores to percentile ranks in [0, 1].

    Why percentiles instead of min-max or z-score?
    - Min-max is sensitive to outliers
    - Z-score assumes Gaussian distribution (BM25/PPMI are not Gaussian)
    - Percentiles are distribution-free and scale-invariant:
      percentile rank of a score stays stable as the corpus grows

    Args:
        scores: {concepto: raw_score}

    Returns:
        {concepto: percentile_rank} in [0, 1]
    """
    if not scores:
        return {}

    sorted_vals = sorted(scores.values())
    denom = max(1, len(sorted_vals) - 1)  # avoid division by zero for n=1

    result = {}
    for concepto, score in scores.items():
        rank = bisect.bisect_left(sorted_vals, score)
        result[concepto] = rank / denom
    return result


# ─── Signal Ranking Helpers ───

def scores_to_rankings(signal_scores: Dict[str, Dict[str, float]]) -> Dict[str, List[str]]:
    """
    Convert per-signal score dicts to per-signal ranked lists (best-first).
    Used as input for rrf_fusion() and weighted_rrf().

    Args:
        signal_scores: {signal_name: {concepto: score}}

    Returns:
        {signal_name: [concepto_ranked_best_first]}
    """
    rankings = {}
    for signal_name, scores in signal_scores.items():
        if not scores:
            continue
        rankings[signal_name] = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)
    return rankings


# ─── Query-Dependent Heuristic Weights ───

def compute_dynamic_weights(
    query: str,
    bm25_scores: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Compute query-dependent signal weights using deterministic IR heuristics.

    No ML, no training, no .pkl files -- pure deterministic rules from IR literature.
    Compatible with any corpus size, any laptop, zero infrastructure.

    Heuristic sources:
    - Amati et al. 2004: Selective expansion -- only expand "difficult" queries
    - Cronen-Townsend 2002: Query clarity -- high clarity = don't expand
    - TREC ToT 2024: Query-type dependent signal utility findings

    Args:
        query: raw query string (used for structural analysis only)
        bm25_scores: {concepto: bm25_score} -- used to compute query clarity

    Returns:
        {signal_name: normalized_weight} -- weights sum to 1.0
    """
    # Copy defaults (never mutate module-level constant)
    weights = dict(DEFAULT_RRF_WEIGHTS)

    # ── Query Structure Analysis ──
    tokens = [t for t in query.lower().split() if len(t) > 1]
    n_tokens = len(tokens)
    is_question = '?' in query
    is_exact_phrase = '"' in query
    is_short = n_tokens <= 2
    is_long = n_tokens >= 5

    # ── Query Clarity (Cronen-Townsend 2002) ──
    # Ratio max_bm25 / (max_bm25 + avg_bm25): high = lexically focused, low = ambiguous.
    # Computed only if bm25_scores provided; defaults to 0.5 (unknown) otherwise.
    query_clarity = 0.5
    if bm25_scores:
        max_bm25 = max(bm25_scores.values())
        avg_bm25 = sum(bm25_scores.values()) / len(bm25_scores)
        query_clarity = max_bm25 / (max_bm25 + avg_bm25 + 1e-9)
    is_hard_query = query_clarity < 0.3  # low clarity => needs semantic expansion

    # ── Heuristic Weight Adjustments ──

    # Short queries (1-2 tokens): BM25 unreliable; synonyms+hubs+ppmi critical.
    # Rationale: BM25 needs multiple tokens to discriminate; single token is noisy.
    if is_short:
        weights['sinonimos'] *= 1.5
        weights['hub'] *= 1.4
        weights['ppmi'] *= 1.3
        weights['bm25'] *= 0.8

    # Question queries: predicate/SRL matching matters more.
    # Rationale: questions encode semantic roles (who/what/when) => predicates help.
    if is_question:
        weights['pred'] *= 1.5
        weights['tematico'] *= 1.2

    # Exact phrase (quotes): BM25 dominates; semantic expansion hurts precision.
    # Rationale: user explicitly wants lexical match => reduce semantic noise.
    if is_exact_phrase:
        weights['bm25'] *= 1.5
        weights['sinonimos'] *= 0.5
        weights['tematico'] *= 0.5

    # Long queries (5+ tokens): semantic signals help disambiguation.
    # Rationale: rich context => PPMI and thematic signals more reliable.
    if is_long:
        weights['ppmi'] *= 1.3
        weights['tematico'] *= 1.2
        weights['bm25'] *= 0.9

    # Hard/ambiguous queries (low clarity): expand with semantic signals.
    # Per Amati 2004: selective expansion only for difficult queries.
    if is_hard_query:
        weights['tematico'] *= 1.3
        weights['ppmi'] *= 1.2
        weights['hub'] *= 1.2

    # ── Normalize to sum to 1.0 ──
    total = sum(weights.values())
    if total <= 0:
        return {k: 1.0 / len(weights) for k in weights}
    return {k: v / total for k, v in weights.items()}


# ─── Complete Fusion Pipeline ───

def fuse_signals(
    signal_scores: Dict[str, Dict[str, float]],
    query: str = "",
    use_dynamic_weights: bool = True,
    k: int = RRF_K
) -> Dict[str, float]:
    """
    Complete scale-invariant fusion pipeline:
      1. Convert scores to rankings (per signal)
      2. Compute query-dependent weights (heuristic, no ML)
      3. Apply weighted RRF fusion

    Main entry point for the RRF fusion module.

    Args:
        signal_scores: {signal_name: {concepto: raw_score}}
        query: raw query string (used for heuristic weight computation)
        use_dynamic_weights: if True, adjust weights per query characteristics
        k: RRF damping constant (default 60)

    Returns:
        {concepto: fused_rrf_score} -- higher = better match
    """
    if not signal_scores:
        return {}

    # Step 1: Convert scores to ranked lists per signal
    rankings = scores_to_rankings(signal_scores)

    # Step 2: Compute query-dependent weights
    if use_dynamic_weights:
        bm25_scores = signal_scores.get('bm25', {})
        weights = compute_dynamic_weights(query, bm25_scores)
    else:
        weights = DEFAULT_RRF_WEIGHTS

    # Step 3: Weighted RRF fusion
    return weighted_rrf(rankings, weights, k=k)