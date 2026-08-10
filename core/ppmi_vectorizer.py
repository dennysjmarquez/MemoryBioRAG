#!/usr/bin/env python3
"""ppmi_vectorizer.py — Motor de Factorización de Matriz PPMI+SVD y Retrofitting de Grafo

Modulo listo para integrar en MemoryBioRAG/core/ppmi_vectorizer.py.
Construye la representación vectorial distribucional de la corteza (largo_plazo + sinapsis)
sin dependencias de modelos preentrenados externos (PyTorch, Transformers, FastText).

Algoritmo:
  1. Matriz Término-Documento con PPMI (alpha=0.75, k_shift=1.0)
  2. Factorización TruncatedSVD (dim=100) para obtener W (palabras) y D (documentos/nodos)
  3. Retrofitting de Grafo (Faruqui et al., 2015) sobre sinapsis (5 iters, lambda=0.2)
  4. Almacenamiento binario en las tablas `tokens`, `nodos` y `data`
"""
import math
import sqlite3
import time
import numpy as np
from pathlib import Path
from core.pmi_semantico import _TOKEN_PATTERN, _TOKENS_CORTOS
from core.stopwords import STOPWORDS
from core.stemmer_es import stem as _stem

EXCEPCIONES_STOPWORD = {'memoria', 'buscar', 'memory'}
STOPWORDS_SUAVE = STOPWORDS - EXCEPCIONES_STOPWORD

# ─── Constantes de Configuración Estática del Motor Vectorial PPMI+SVD ───
DIM_VECTORIAL = 100
RETROFIT_LAMBDA = 0.2
RETROFIT_ITERS = 5
MOTOR_NOMBRE = "PPMI+SVD+Retrofit"


def _tokenizar(texto: str) -> list[str]:
    """Tokeniza texto a lista de stems limpios, preservando excep. de stopwords suaves y tokens técnicos."""
    if not texto:
        return []
    texto = texto.replace('_', ' ').replace('-', ' ')
    tokens = _TOKEN_PATTERN.findall(texto.lower())
    cortos = [t for t in texto.lower().split() if t in _TOKENS_CORTOS]
    todos = [t for t in (tokens + cortos) if t not in STOPWORDS_SUAVE]
    return [_stem(t) for t in todos]


class PPMISVD:
    def __init__(self, dim: int = DIM_VECTORIAL, min_count: int = 1, alpha: float = 0.75,
                 k_shift: float = 1.0, seed: int = 42):
        self.dim = dim
        self.min_count = min_count
        self.alpha = alpha
        self.k_shift = k_shift
        self.seed = seed
        self.vocab: dict[str, int] = {}
        self.id2token: list[str] = []
        self.token_freq: np.ndarray = np.array([])
        self.W: np.ndarray = np.array([[]])
        self.idf_words: np.ndarray = np.array([])
        self.n_docs: int = 0

    def _construir_vocabulario(self, corpus: list[list[str]]):
        counts = {}
        for doc in corpus:
            for t in doc:
                counts[t] = counts.get(t, 0) + 1
        filtrados = sorted([t for t, c in counts.items() if c >= self.min_count])
        self.vocab = {t: i for i, t in enumerate(filtrados)}
        self.id2token = filtrados
        self.token_freq = np.array([counts[t] for t in filtrados], dtype='float64')

    def entrenar(self, corpus: list[list[str]]) -> dict:
        t0 = time.perf_counter()
        self._construir_vocabulario(corpus)
        V = len(self.id2token)
        D = len(corpus)
        self.n_docs = D

        if V == 0 or D == 0:
            return {'vocab': 0, 'dim_efectiva': 0, 'varianza_explicada_top_k': 0.0, 'segundos': 0.0}

        doc_counts = np.zeros((V, D), dtype='float64')
        for d_idx, doc in enumerate(corpus):
            for t in doc:
                if t in self.vocab:
                    doc_counts[self.vocab[t], d_idx] += 1.0

        tf = np.log1p(doc_counts)
        p_td = tf / (tf.sum() + 1e-12)
        p_t = p_td.sum(axis=1, keepdims=True)
        p_d = p_td.sum(axis=0, keepdims=True)

        p_t_alpha = p_t ** self.alpha
        p_t_alpha /= (p_t_alpha.sum() + 1e-12)

        den = p_t_alpha @ p_d
        pmi = np.log(np.maximum(p_td, 1e-12) / np.maximum(den, 1e-12))
        ppmi = np.maximum(pmi - math.log(self.k_shift), 0.0)

        dim_real = min(self.dim, V, D)
        np.random.seed(self.seed)

        try:
            U, S, Vt = np.linalg.svd(ppmi, full_matrices=False)
            U = U[:, :dim_real]
            S = S[:dim_real]
        except np.linalg.LinAlgError:
            U = np.eye(V, dim_real)
            S = np.ones(dim_real)

        self.W = U * np.power(S, 0.5)

        df = (doc_counts > 0).sum(axis=1)
        self.idf_words = np.log((D + 1.0) / (df + 1.0)) + 1.0

        var_total = (S**2).sum()
        var_expl = float((S[:dim_real]**2).sum() / (var_total + 1e-12))
        dt = time.perf_counter() - t0

        return {
            'vocab': V,
            'dim_efectiva': dim_real,
            'varianza_explicada_top_k': round(var_expl, 4),
            'segundos': round(dt, 3)
        }

    def vector_documento(self, doc_toks: list[str], pooling: str = 'idf') -> tuple[np.ndarray, int, int]:
        if len(self.W) == 0:
            return np.zeros(self.dim), 0, 0
        indices = [self.vocab[t] for t in doc_toks if t in self.vocab]
        if not indices:
            return np.zeros(self.W.shape[1]), len(doc_toks), 0

        vecs = self.W[indices]
        if pooling == 'idf':
            weights = self.idf_words[indices, np.newaxis]
            v = (vecs * weights).sum(axis=0) / (weights.sum() + 1e-12)
        else:
            v = vecs.mean(axis=0)
        return v, len(doc_toks), len(indices)


def retrofit(vectors: dict[str, np.ndarray], adjacency: dict[str, list[tuple[str, float]]],
             iters: int = 5, lam: float = 0.2) -> dict[str, np.ndarray]:
    """Retrofitting de Faruqui et al. (2015): (1-lam)*v_i + lam * mean(v_j * w_ij)"""
    new_vecs = {k: v.copy() for k, v in vectors.items()}
    for _ in range(iters):
        for node in new_vecs:
            vecinos = adjacency.get(node, [])
            if not vecinos:
                continue
            num = np.zeros_like(new_vecs[node])
            den = 0.0
            for vec_id, weight in vecinos:
                if vec_id in new_vecs:
                    num += weight * new_vecs[vec_id]
                    den += weight
            if den > 0:
                target = num / den
                new_vecs[node] = (1.0 - lam) * vectors[node] + lam * target
    return new_vecs


def _cargar_sinapsis(con: sqlite3.Connection, tipos=('sinonimo_explicito', 'pmi_hebbiano', 'co_semantica', 'manual')):
    adj: dict[str, list[tuple[str, float]]] = {}
    ph = ",".join("?" for _ in tipos)
    rows = con.execute(f"SELECT origen, destino, peso FROM sinapsis WHERE tipo IN ({ph})", tipos).fetchall()
    for o, d, w in rows:
        weight = float(w or 0.5)
        adj.setdefault(o, []).append((d, weight))
        adj.setdefault(d, []).append((o, weight))
    return adj


def cargar_contenidos(con: sqlite3.Connection, estados=None):
    if estados is None:
        filas = con.execute("SELECT concepto, contenido, sinonimos, estado FROM largo_plazo").fetchall()
    else:
        ph = ",".join("?" for _ in estados)
        filas = con.execute(f"SELECT concepto, contenido, sinonimos, estado FROM largo_plazo WHERE estado IN ({ph})", estados).fetchall()

    corpus, conceptos, ests = [], [], []
    for concepto, contenido, sinonimos, estado in filas:
        concepto_clean = concepto.replace('_', ' ').replace('-', ' ')
        texto = f"{concepto_clean} {sinonimos or ''} {contenido or ''}"
        toks = _tokenizar(texto)
        if len(toks) >= 1:
            corpus.append(toks)
            conceptos.append(concepto)
            ests.append(estado)
    return corpus, conceptos, ests


def _ppmi_full_reindex_due(con: sqlite3.Connection, delta_nodos_nuevos: int = 0) -> bool:
    """True si pasaron al menos 7 días Y se acumularon >= 50 nodos nuevos.
    Diseñado para computadoras personales (evita picos de CPU inútiles).
    """
    try:
        count = con.execute("SELECT COUNT(*) FROM nodos").fetchone()[0]
        if count == 0:
            return True
        row = con.execute("SELECT valor FROM data WHERE clave = 'ppmi_ultima_reindexacion'").fetchone()
        if not row:
            return True
        ultimo_ts = float(row[0])
        
        row_delta = con.execute("SELECT valor FROM data WHERE clave = 'ppmi_nodos_acumulados'").fetchone()
        acumulados = int(row_delta[0]) if row_delta else 0
        acumulados += delta_nodos_nuevos
        con.execute(
            "INSERT INTO data (clave, valor) VALUES ('ppmi_nodos_acumulados', ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (str(acumulados),),
        )
        con.commit()

        
        hace_7_dias = (time.time() - ultimo_ts) >= 7 * 86400
        return hace_7_dias and acumulados >= 50
    except Exception:
        return True


def fold_in_nodos(con: sqlite3.Connection, conceptos_nuevos: list[str]) -> int:
    """Calcula vectores de forma incremental solo para nodos nuevos usando la tabla tokens existente.
    Tarda < 10ms y no congela la CPU en laptops.
    """
    if not conceptos_nuevos:
        return 0

    token_rows = con.execute("SELECT token, freq, vector FROM tokens").fetchall()
    if not token_rows:
        return reindexar_ppmi_svd(con)

    token_vecs = {}
    token_freq = {}
    for t, f, blob in token_rows:
        token_vecs[t] = np.frombuffer(blob, dtype='float32').astype('float64')
        token_freq[t] = f

    n_docs_row = con.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()
    n_docs = n_docs_row[0] if n_docs_row else 100

    ph = ",".join("?" for _ in conceptos_nuevos)
    filas = con.execute(f"SELECT concepto, contenido, sinonimos, estado FROM largo_plazo WHERE concepto IN ({ph})", conceptos_nuevos).fetchall()

    nuevos_vecs = {}
    nodos_rows = []
    for concepto, contenido, sinonimos, estado in filas:
        texto = f"{concepto.replace('_', ' ').replace('-', ' ')} {sinonimos or ''} {contenido or ''}"
        toks = _tokenizar(texto)

        vsum = None
        wsum = 0.0
        n_conv = 0
        for tok in set(toks):
            if tok in token_vecs:
                freq = token_freq.get(tok, 1)
                idf_w = math.log((n_docs + 1.0) / (freq + 1.0)) + 1.0
                v = token_vecs[tok] * idf_w
                vsum = v if vsum is None else vsum + v
                wsum += idf_w
                n_conv += 1

        if vsum is None or wsum < 1e-10:
            v_final = np.zeros(100, dtype='float64')
        else:
            v_final = vsum / wsum

        nuevos_vecs[concepto] = v_final
        nodos_rows.append((concepto, estado, len(toks), n_conv, v_final.astype('float32').tobytes()))

    if not nodos_rows:
        return 0

    con.executemany("INSERT OR REPLACE INTO nodos VALUES (?, ?, ?, ?, ?)", nodos_rows)

    adj = _cargar_sinapsis(con)
    vecinos_set = set()
    for c in conceptos_nuevos:
        for dest, _ in adj.get(c, []):
            vecinos_set.add(dest)

    if vecinos_set:
        ph_v = ",".join("?" for _ in vecinos_set)
        vecinos_rows = con.execute(f"SELECT concepto, vector FROM nodos WHERE concepto IN ({ph_v})", list(vecinos_set)).fetchall()
        vecs_dict = {c: v for c, v in nuevos_vecs.items()}
        for c, blob in vecinos_rows:
            vecs_dict[c] = np.frombuffer(blob, dtype='float32').astype('float64')

        retro = retrofit(vecs_dict, adj, iters=3, lam=0.2)
        con.executemany(
            "UPDATE nodos SET vector = ? WHERE concepto = ?",
            [(v.astype('float32').tobytes(), c) for c, v in retro.items()]
        )

    con.commit()
    return len(nodos_rows)


def reindexar_ppmi_svd(con: sqlite3.Connection, dim: int = 100, retrofit_lam: float = 0.2, retrofit_iters: int = 5):
    """Reindexa la matriz de la corteza en la conexión SQLite dada."""
    # 1. Asegurar tablas
    con.execute("CREATE TABLE IF NOT EXISTS tokens (token TEXT PRIMARY KEY, freq INTEGER, vector BLOB)")
    con.execute("""CREATE TABLE IF NOT EXISTS nodos (
                       concepto  TEXT PRIMARY KEY,
                       estado    TEXT,
                       n_tokens  INTEGER,
                       n_conv    INTEGER,
                       vector    BLOB
                   )""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_nodos_estado ON nodos(estado)")
    con.execute("CREATE TABLE IF NOT EXISTS data (clave TEXT PRIMARY KEY, valor TEXT)")

    # 2. Cargar corpus
    corpus, conceptos, ests = cargar_contenidos(con)
    if not corpus:
        return 0

    # 3. Entrenar modelo
    modelo = PPMISVD(dim=dim, min_count=1, alpha=0.75, k_shift=1.0, seed=42)
    metricas = modelo.entrenar(corpus)

    # 4. Guardar vectores de token
    con.execute("DELETE FROM tokens")
    con.executemany(
        "INSERT INTO tokens VALUES (?, ?, ?)",
        [(t, int(modelo.token_freq[i]), modelo.W[i].astype('float32').tobytes())
         for i, t in enumerate(modelo.id2token)]
    )

    # 5. Guardar vectores de nodo
    con.execute("DELETE FROM nodos")
    vecs_dict = {}
    nodos_rows = []
    for toks, c, e in zip(corpus, conceptos, ests):
        v, nt, nc = modelo.vector_documento(toks, pooling='idf')
        vecs_dict[c] = v
        nodos_rows.append((c, e, nt, nc, v.astype('float32').tobytes()))
    con.executemany("INSERT INTO nodos VALUES (?, ?, ?, ?, ?)", nodos_rows)

    # 6. Retrofitting
    adj = _cargar_sinapsis(con)
    retro = retrofit(vecs_dict, adj, iters=retrofit_iters, lam=retrofit_lam)
    con.executemany(
        "UPDATE nodos SET vector = ? WHERE concepto = ?",
        [(v.astype('float32').tobytes(), c) for c, v in retro.items()]
    )

    # 7. Estado Dinámico de Ejecución (Solo variables dinámicas de SQLite).
    # La tabla `data` la crea el sistema (memory_store._crear_tabla_data).
    for k, v in [
        ('ppmi_ultima_reindexacion', str(time.time())),
        ('ppmi_nodos_acumulados', '0')
    ]:
        con.execute(
            "INSERT INTO data (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (k, v)
        )

    con.commit()
    return len(conceptos)

