#!/usr/bin/env python3
"""ppmi_hybrid_search.py — Motor de Búsqueda Híbrida PPMI+SVD + IDF-Synonym para MemoryBioRAG

Motor listo para integrar en MemoryBioRAG/core/ppmi_hybrid_search.py.
Combina:
  1. IDF-Synonym Specificity Scoring (para queries de 1 token único / modo sinónimo)
  2. PPMI+SVD cosine similarity con IDF-weighted query vector (para queries de 2+ tokens / modo por_tema)
  3. Multi-hop synapse propagation (decay=0.4) para rescatar nodos conectados hebbianamente.
"""
import math
import sqlite3
import numpy as np
from pathlib import Path
from collections import defaultdict

from core.pmi_semantico import _TOKEN_PATTERN, _TOKENS_CORTOS
from core.stopwords import STOPWORDS
from core.stemmer_es import stem as _stem

EXCEPCIONES_STOPWORD = {'memoria', 'buscar', 'memory'}
STOPWORDS_SUAVE = STOPWORDS - EXCEPCIONES_STOPWORD

ALPHA = 5.0
BETA = 1.0
GAMMA = 1.0
DECAY = 0.4
MAX_Q = 1
TIPOS_HOP = {'sinonimo_explicito', 'pmi_hebbiano', 'manual', 'co_semantica'}


def _tokenizar(texto: str) -> list[str]:
    if not texto:
        return []
    texto = texto.replace('_', ' ').replace('-', ' ')
    tokens = _TOKEN_PATTERN.findall(texto.lower())
    cortos = [t for t in texto.lower().split() if t in _TOKENS_CORTOS]
    todos = [t for t in (tokens + cortos) if t not in STOPWORDS_SUAVE]
    return [_stem(t) for t in todos]


def _coseno(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 1e-10 and nb > 1e-10 else 0.0


class IndicesBioRAG:
    """Carga y gestiona los índices vectoriales y de sinónimos desde la DB de MemoryBioRAG."""

    def __init__(self, con_or_db):
        if isinstance(con_or_db, (str, Path)):
            con = sqlite3.connect(f"file:{con_or_db}?mode=ro", uri=True)
            auto_close = True
        else:
            con = con_or_db
            auto_close = False

        self.idx_sin: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for concepto, sinonimos in con.execute("SELECT concepto, sinonimos FROM largo_plazo"):
            if not sinonimos:
                continue
            toks = _tokenizar(sinonimos)
            n_sin = max(len(toks), 1)
            for tok in set(toks):
                self.idx_sin[tok].append((concepto, n_sin))

        self.token_vecs: dict[str, np.ndarray] = {}
        self.token_freq: dict[str, int] = {}
        for token, freq, blob in con.execute("SELECT token, freq, vector FROM tokens"):
            self.token_vecs[token] = np.frombuffer(blob, dtype='float32').astype('float64')
            self.token_freq[token] = freq

        self.vecs: dict[str, np.ndarray] = {}
        for concepto, blob in con.execute("SELECT concepto, vector FROM nodos"):
            self.vecs[concepto] = np.frombuffer(blob, dtype='float32').astype('float64')

        self.grafo_sin: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for origen, destino, peso, tipo in con.execute("SELECT origen, destino, peso, tipo FROM sinapsis"):
            if tipo in TIPOS_HOP:
                p = float(peso or 0.5)
                self.grafo_sin[origen].append((destino, p))
                self.grafo_sin[destino].append((origen, p))

        self.contenidos: dict[str, set[str]] = {}
        for concepto, contenido in con.execute("SELECT concepto, contenido FROM largo_plazo"):
            self.contenidos[concepto] = set(_tokenizar(contenido or ''))

        self.todos_los_conceptos = [r[0] for r in con.execute("SELECT concepto FROM nodos")]
        self.n_docs = len(self.todos_los_conceptos)

        if auto_close:
            con.close()

    def vector_query(self, q_toks: list[str]) -> np.ndarray:
        vsum = None
        wsum = 0.0
        for tok in set(q_toks):
            if tok not in self.token_vecs:
                continue
            freq = self.token_freq.get(tok, 1)
            idf_w = math.log((self.n_docs + 1) / (freq + 1)) + 1.0
            v = self.token_vecs[tok] * idf_w
            vsum = v if vsum is None else vsum + v
            wsum += idf_w
        if vsum is None or wsum < 1e-10:
            return np.zeros(100)
        return vsum / wsum

    def idf_sin(self, q_toks_unique: set, c_name: str, pool_set: set) -> float:
        score = 0.0
        for tok in q_toks_unique:
            matches_pool = [(c, n) for c, n in self.idx_sin.get(tok, []) if c in pool_set]
            k_pool = len(matches_pool)
            if k_pool == 0:
                continue
            n_sin = next((n for c, n in self.idx_sin.get(tok, []) if c == c_name), None)
            if n_sin is None:
                continue
            score += (1.0 / math.log(1 + n_sin)) * (1.0 / math.log(1 + k_pool))
        return score

    def hop_sin(self, q_toks_unique: set, c_name: str, pool_set: set) -> float:
        matched_direct: dict[str, float] = {}
        for tok in q_toks_unique:
            for concepto, n_sin in self.idx_sin.get(tok, []):
                if concepto not in pool_set:
                    continue
                k_pool = len([c for c, n in self.idx_sin[tok] if c in pool_set])
                idf_val = (1.0 / math.log(1 + n_sin)) * (1.0 / math.log(1 + k_pool))
                if concepto not in matched_direct or idf_val > matched_direct[concepto]:
                    matched_direct[concepto] = idf_val

        if c_name in matched_direct:
            return 0.0

        best = 0.0
        for vecino, peso_s in self.grafo_sin.get(c_name, []):
            if vecino in matched_direct:
                best = max(best, DECAY * peso_s * matched_direct[vecino])
        return best


def score_candidato(idx: IndicesBioRAG, q_toks: list[str], q_toks_unique: set,
                    es_corta: bool, c_name: str, pool_set: set) -> tuple[float, dict]:
    vq = idx.vector_query(q_toks)
    vn = idx.vecs.get(c_name, np.zeros(100))
    s_ppmi = _coseno(vq, vn)

    if es_corta:
        s_idf = idx.idf_sin(q_toks_unique, c_name, pool_set)
        s_hop = idx.hop_sin(q_toks_unique, c_name, pool_set)
        total = ALPHA * s_idf + BETA * s_ppmi + GAMMA * s_hop
    else:
        s_idf, s_hop = 0.0, 0.0
        total = BETA * s_ppmi

    return total, {'s_ppmi': s_ppmi, 's_idf': s_idf, 's_hop': s_hop}


def buscar_hibrido(query: str, con_or_db, top_k: int = 10) -> list[dict]:
    idx = IndicesBioRAG(con_or_db)
    q_toks = _tokenizar(query)
    q_toks_unique = set(q_toks)
    es_corta = len(q_toks_unique) <= MAX_Q
    if es_corta:
        try:
            from core.fallback_simbolico import expandir_query_wordnet
            wn_exp = expandir_query_wordnet(q_toks_unique)
            q_toks_unique = q_toks_unique | set(_tokenizar(" ".join(wn_exp)))
        except Exception:
            pass
    pool_set = set(idx.todos_los_conceptos)

    resultados = []
    for c_name in idx.todos_los_conceptos:
        total, det = score_candidato(idx, q_toks, q_toks_unique, es_corta, c_name, pool_set)
        resultados.append({'concepto': c_name, 'score': total, **det})

    resultados.sort(key=lambda x: -x['score'])
    return resultados[:top_k]
