#!/usr/bin/env python3
"""ppmi_svd_puro.py — PPMI + SVD, aislado del pipeline de BioRAG.

POR QUÉ ESTE SCRIPT EXISTE:
word2vec_puro.py (SGNS) no logró discriminación semántica confiable
sobre este corpus (71k tokens, vocab 4.654). SGNS con negative sampling
necesita millones de tokens para converger a direcciones estables —
con este tamaño de corpus, el ruido estocástico del muestreo negativo
domina la señal.

PPMI + SVD es el método distribucional clásico (pre-word2vec: Church &
Hanks 1990, Landauer & Dumais 1997 / LSA). Levy & Goldberg (2015,
"Improving Distributional Similarity with Lessons Learned from Word2Vec")
mostraron que PPMI+SVD iguala o supera a SGNS, y es MÁS robusto en
corpus chicos, porque:
  - Es una factorización exacta de una matriz de conteos reales
    (sin descenso de gradiente estocástico, sin negativos muestreados
    al azar → determinista y reproducible dado el mismo corpus).
  - No necesita "ver" cada palabra en miles de contextos para que
    su dirección converja: la señal es la co-ocurrencia observada
    directamente, no una aproximación aprendida.

Qué NO usa: nada del pipeline de BioRAG (sin sinónimos, sin dimensiones,
sin sinapsis, sin fallbacks). Solo el contenido de los nodos. No toca
la DB real (memory_biorag.db se abre solo lectura).

Cómo funciona:
  1) Matriz término-documento: cuántas veces aparece cada token (fila)
     en cada nodo (columna). Documento = nodo (mismo criterio que ya
     usa core/pmi_semantico.py con VENTANA_NODO=0: el nodo completo es
     el contexto).
  2) PPMI sobre esa matriz, con context distribution smoothing (alpha=0.75,
     la misma técnica que usa word2vec en su distribución de negativos)
     y shift log(k) — hace la matriz menos sensible a palabras muy frecuentes.
  3) SVD truncada (scipy/sklearn, sin librerías de embeddings) reduce
     la matriz PPMI dispersa a vectores densos de baja dimensión.
  4) Vector de nodo = promedio de vectores de sus tokens (mismo pooling
     que word2vec_puro.py, para comparar los dos métodos en igualdad
     de condiciones).

Uso:
  python3 scripts/ppmi_svd_puro.py                       # entrena y guarda
  python3 scripts/ppmi_svd_puro.py "perfil de dennys"    # recupera top-10
  python3 scripts/ppmi_svd_puro.py --eval                # evalúa los 35 fallos
  python3 scripts/ppmi_svd_puro.py --par sistema gato     # coseno entre dos tokens (control)
"""
import argparse
import json
import math
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pmi_semantico import _TOKEN_PATTERN, _TOKENS_CORTOS  # mismo regex que el resto del proyecto
from core.stopwords import STOPWORDS  # misma STOPWORDS completa que produccion
from core.stemmer_es import stem as _stem

# -----------------------------------------------------------------------------
# Fix aislado para el punto 8.2 del brief: 'memoria', 'buscar', 'memory' son
# justo las 3 queries de 1 sola palabra del pool de 35 fallos que caen 100%
# dentro de STOPWORDS -> tokenizan a lista vacia -> vector cero -> empate
# degenerado contra los 794-796 nodos (score 0 para todos).
# No tocamos core/stopwords.py (compartido con produccion, prohibido por la
# restriccion 9) ni ampliamos categorias enteras (STOPWORDS_ES/EN/CONTROL
# siguen intactas -> no cambia el comportamiento general del filtro). Se abre
# una excepcion QUIRURGICA de exactamente estas 3 palabras, minima y
# auditable, aplicada tanto al corpus como a las queries (deben tokenizar
# igual para que el token exista en el vocabulario y se pueda recuperar).
# -----------------------------------------------------------------------------
EXCEPCIONES_STOPWORD = {'memoria', 'buscar', 'memory'}
STOPWORDS_SUAVE = STOPWORDS - EXCEPCIONES_STOPWORD


def _tokenizar(texto: str) -> list[str]:
    if not texto:
        return []
    texto = texto.replace('_', ' ').replace('-', ' ')
    tokens = _TOKEN_PATTERN.findall(texto.lower())
    cortos = [t for t in texto.lower().split() if t in _TOKENS_CORTOS]
    todos = [t for t in (tokens + cortos) if t not in STOPWORDS_SUAVE]
    return [_stem(t) for t in todos]


DEFAULT_ORIGEN = ROOT / 'MemoryBioRAG_Data' / 'memory_biorag.db'
DEFAULT_DB = ROOT / 'scripts' / 'ppmi_svd_puro' / 'ppmi_svd_vectors_ctx.db'
DEFAULT_POOL = ROOT / 'scripts' / 'experimento_rr_pool.json'

FALLOS_POR_TEMA = ['0497', '0534', '0540', '0558', '0571', '0583', '0589', '0634',
                   '0640', '0652', '0670', '0706', '0730', '0736', '0765', '0783',
                   '0795', '0801', '0807', '0824', '0830']
FALLOS_SINONIMO = ['0514', '0520', '0532', '0563', '0625', '0734', '0740', '0757',
                   '0775', '0799', '0811', '0822', '0828', '0878']
FALLOS_ID = set(FALLOS_POR_TEMA + FALLOS_SINONIMO)


# =============================================================================
# PPMI + SVD
# =============================================================================

class PPMISVD:
    """PPMI sobre matriz término-documento + SVD truncada (Levy & Goldberg 2015).

    Interfaz compatible con SGNS (vocab, dim, vector_tokens, vector_documento,
    coseno) para poder reusar recuperar()/evaluar() sin duplicar código.
    """

    def __init__(self, dim: int = 100, min_count: int = 2, alpha: float = 0.75,
                 k_shift: float = 1.0, seed: int = 42, window: int = 5):
        self.dim = dim
        self.min_count = min_count
        self.alpha = alpha
        self.k_shift = k_shift
        self.seed = seed
        self.window = window  # NUEVO: tamaño de la ventana deslizante (hipotesis 7.1)

        self.vocab: dict[str, int] = {}
        self.freqs: dict[str, int] = {}
        self.W: np.ndarray | None = None

    def _construir_vocab(self, corpus: list[list[str]]) -> None:
        freqs_total: Counter = Counter()
        for doc in corpus:
            freqs_total.update(dict.fromkeys(doc, 1))  # 1 por documento (freq-documento, no freq-token)
        self.freqs = {t: c for t, c in freqs_total.items() if c >= self.min_count}
        self.vocab = {t: i for i, t in enumerate(sorted(self.freqs))}

    def _matriz_palabra_contexto(self, corpus: list[list[str]]):
        """Hipotesis 7.1: co-ocurrencia palabra-CONTEXTO con ventana deslizante
        (no palabra-documento). La ventana NUNCA cruza limite de nodo (cada
        nodo es su propia 'oracion', igual que en word2vec_puro.py) - solo
        cambia que el 'documento'/contexto de cada palabra pasa de ser 'el
        nodo entero' a 'sus +-window vecinos inmediatos'. Es el equivalente
        exacto que describen Levy & Goldberg 2015 para una factorizacion de
        la matriz que SGNS aproxima por descenso de gradiente - mas fiel a
        SGNS que la version palabra-documento (mas parecida a LSA clasico).
        """
        from scipy.sparse import csr_matrix
        n_vocab = len(self.vocab)
        counts: Counter = Counter()
        for doc in corpus:
            idxs = [self.vocab[t] for t in doc if t in self.vocab]
            L = len(idxs)
            for i, wi in enumerate(idxs):
                lo = max(0, i - self.window)
                hi = min(L, i + self.window + 1)
                for j in range(lo, hi):
                    if j == i:
                        continue
                    counts[(wi, idxs[j])] += 1
        if not counts:
            return csr_matrix((n_vocab, n_vocab), dtype=np.float64)
        filas, cols = zip(*counts.keys())
        datos = list(counts.values())
        return csr_matrix((datos, (filas, cols)), shape=(n_vocab, n_vocab), dtype=np.float64)

    def _ppmi(self, M):
        """PPMI con context distribution smoothing (Levy & Goldberg 2015)."""
        from scipy.sparse import csr_matrix
        total = M.sum()
        freq_termino = np.asarray(M.sum(axis=1)).flatten()
        freq_doc = np.asarray(M.sum(axis=0)).flatten()
        freq_doc_suave = freq_doc ** self.alpha
        freq_doc_suave_total = freq_doc_suave.sum()

        Mc = M.tocoo()
        filas, cols, datos = [], [], []
        log_k = math.log(self.k_shift) if self.k_shift > 0 else 0.0
        for i, j, v in zip(Mc.row, Mc.col, Mc.data):
            p_wc = v / total
            p_w = freq_termino[i] / total
            p_c = freq_doc_suave[j] / freq_doc_suave_total
            if p_w <= 0 or p_c <= 0:
                continue
            pmi = math.log(p_wc / (p_w * p_c)) - log_k
            if pmi > 0:
                filas.append(i)
                cols.append(j)
                datos.append(pmi)
        return csr_matrix((datos, (filas, cols)), shape=M.shape)

    def entrenar(self, corpus: list[list[str]]) -> dict:
        t0 = time.perf_counter()
        self._construir_vocab(corpus)
        V = len(self.vocab)
        M = self._matriz_palabra_contexto(corpus)
        P = self._ppmi(M)

        from sklearn.decomposition import TruncatedSVD
        k = max(2, min(self.dim, V - 1, len(corpus) - 1))
        svd = TruncatedSVD(n_components=k, random_state=self.seed)
        self.W = svd.fit_transform(P)
        self.dim = k
        varianza_explicada = float(svd.explained_variance_ratio_.sum())

        return {
            'vocab': V,
            'docs': len(corpus),
            'dim_efectiva': k,
            'varianza_explicada_top_k': round(varianza_explicada, 4),
            'segundos': round(time.perf_counter() - t0, 1),
        }

    # ------------------------------------------------------------------
    # Interfaz compatible con SGNS

    def vector_token(self, tok: str) -> np.ndarray | None:
        i = self.vocab.get(tok)
        return self.W[i] if i is not None else None

    def vector_tokens(self, tokens: list[str]) -> np.ndarray:
        vs = [self.W[self.vocab[t]] for t in tokens if t in self.vocab]
        if not vs:
            return np.zeros(self.dim, dtype=np.float64)
        return np.mean(vs, axis=0)

    def vector_documento(self, tokens: list[str]) -> tuple[np.ndarray, int, int]:
        conocidos = [t for t in tokens if t in self.vocab]
        if not conocidos:
            return np.zeros(self.dim, dtype=np.float64), 0, len(tokens)
        v = np.mean([self.W[self.vocab[t]] for t in conocidos], axis=0)
        return v, len(conocidos), len(tokens)

    def coseno(self, a: np.ndarray, b: np.ndarray) -> float:
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        if na <= 0 or nb <= 0:
            return 0.0
        return float(a @ b) / (na * nb)


# =============================================================================
# Base de datos (dueña de sus propios vectores; nunca escribe en memory_biorag.db)
# =============================================================================

def crear_db(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE tokens (token TEXT PRIMARY KEY, freq INTEGER, vector BLOB)")
    con.execute("""CREATE TABLE nodos (
                       concepto  TEXT PRIMARY KEY,
                       estado    TEXT,
                       n_tokens  INTEGER,
                       n_conv    INTEGER,
                       vector    BLOB
                   )""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_nodos_estado ON nodos(estado)")
    con.execute("""CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT)""")
    return con


def cargar_contenidos(origen: Path, estados: list[str] | None = None):
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    if estados is None:
        filas = con.execute("SELECT concepto, contenido, estado FROM largo_plazo").fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con.execute(
            f"SELECT concepto, contenido, estado FROM largo_plazo WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    con.close()
    corpus, conceptos, ests = [], [], []
    for concepto, contenido, estado in filas:
        toks = _tokenizar(contenido or '')
        if len(toks) >= 2:
            corpus.append(toks)
            conceptos.append(concepto)
            ests.append(estado)
    return corpus, conceptos, ests


def guardar_vectores(db: sqlite3.Connection, modelo: PPMISVD, corpus, conceptos, ests) -> None:
    cur = db.cursor()
    cur.execute("BEGIN")
    data_tok = [(tok, modelo.freqs[tok], modelo.W[i].astype(np.float32).tobytes())
                for tok, i in modelo.vocab.items()]
    cur.executemany("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", data_tok)

    data_nodos = []
    for toks, concepto, estado in zip(corpus, conceptos, ests):
        v, n_conv, n_tot = modelo.vector_documento(toks)
        data_nodos.append((concepto, estado, n_tot, n_conv, v.astype(np.float32).tobytes()))
    cur.executemany(
        "INSERT INTO nodos (concepto, estado, n_tokens, n_conv, vector) VALUES (?, ?, ?, ?, ?)",
        data_nodos,
    )
    cur.execute("COMMIT")


def meta_params(db: sqlite3.Connection, modelo: PPMISVD, metrics: dict) -> None:
    cur = db.cursor()
    cur.execute("BEGIN")
    params = {'dim': modelo.dim, 'min_count': modelo.min_count, 'alpha': modelo.alpha,
              'k_shift': modelo.k_shift, 'seed': modelo.seed, **metrics}
    for k, v in params.items():
        cur.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)", (k, str(v)))
    cur.execute("COMMIT")


# =============================================================================
# Recuperación
# =============================================================================

def _cargar_modelo(db: sqlite3.Connection) -> PPMISVD:
    filas = db.execute("SELECT token, vector FROM tokens").fetchall()
    modelo = PPMISVD()
    modelo.vocab = {t: i for i, (t, _) in enumerate(filas)}
    modelo.dim = len(np.frombuffer(filas[0][1], dtype=np.float32)) if filas else 0
    W = np.zeros((len(filas), modelo.dim), dtype=np.float32)
    freqs = {}
    for t, blob in filas:
        W[modelo.vocab[t]] = np.frombuffer(blob, dtype=np.float32)
        freqs[t] = 0
    modelo.W = W.astype(np.float64)
    modelo.freqs = freqs
    return modelo


def recuperar(db: sqlite3.Connection, query: str, top_n: int = 10,
              solo_activos: bool = True) -> list[dict]:
    modelo = _cargar_modelo(db)
    q_toks = _tokenizar(query)
    vq = modelo.vector_tokens(q_toks)
    n_conocidos = sum(1 for t in q_toks if t in modelo.vocab)

    cond = "WHERE estado='activo'" if solo_activos else ""
    filas = db.execute(f"SELECT concepto, vector FROM nodos {cond}").fetchall()
    scores = []
    for concepto, blob in filas:
        if not blob:
            continue
        vn = np.frombuffer(blob, dtype=np.float32)
        scores.append((concepto, modelo.coseno(vq, vn)))
    scores.sort(key=lambda x: -x[1])

    print(f"Query: {query!r} | tokens={len(q_toks)} conocidos={n_conocidos} "
          f"({(n_conocidos / len(q_toks) * 100) if q_toks else 0:.0f}%)")
    return [{'concepto': c, 'coseno': round(s, 4)} for c, s in scores[:top_n]]


# =============================================================================
# Evaluación contra los 35 fallos (mismos gates que word2vec_puro.py)
# =============================================================================

def evaluar(db: sqlite3.Connection, origen: Path, estados: list[str] | None = None) -> dict:
    modelo = _cargar_modelo(db)
    casos = json.loads(Path(DEFAULT_POOL).read_text(encoding='utf-8'))
    casos = [c for c in casos if c['id'] in FALLOS_ID]

    con_src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    cache_vec: dict = {}
    if estados is None:
        filas = con_src.execute("SELECT concepto, contenido FROM largo_plazo").fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con_src.execute(
            f"SELECT concepto, contenido FROM largo_plazo WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    for concepto, contenido in filas:
        toks = _tokenizar(contenido or '')
        v, _, _ = modelo.vector_documento(toks)
        cache_vec[concepto] = v
    con_src.close()

    resumen = {'por_tema': {'n': 0, 'top1': 0, 'top5': 0, 'top10': 0},
               'sinonimo': {'n': 0, 'top1': 0, 'top5': 0, 'top10': 0}}
    detalle = []
    for caso in casos:
        cat = 'por_tema' if caso['categoria'] == 'por_tema' else 'sinonimo'
        expected = caso['expected']
        q_toks = _tokenizar(caso['query'])
        vq = modelo.vector_tokens(q_toks)
        query_degenerada = sum(1 for t in q_toks if t in modelo.vocab) == 0
        scores = []
        for cand in caso['pool']:
            vn = cache_vec.get(cand['concepto'])
            if vn is None:
                vn = np.zeros(modelo.dim)
            scores.append((cand['concepto'], modelo.coseno(vq, vn)))
        scores.sort(key=lambda x: -x[1])
        rank = next((i + 1 for i, (c, _) in enumerate(scores) if c == expected),
                    len(scores) + 1)
        resumen[cat]['n'] += 1
        resumen[cat]['top1'] += rank == 1
        resumen[cat]['top5'] += rank <= 5
        resumen[cat]['top10'] += rank <= 10
        detalle.append({'id': caso['id'], 'categoria': cat, 'expected': expected,
                        'query': caso['query'], 'rank': rank, 'n_pool': len(scores),
                        'query_degenerada': query_degenerada})

    return {
        'resumen': resumen,
        'criterios': {
            'por_tema_esperado_top5': {'min': 10, 'obtenido': resumen['por_tema']['top5']},
            'sinonimo_esperado_top5': {'min': 6, 'obtenido': resumen['sinonimo']['top5']},
        },
        'detalle': detalle,
    }


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origen', default=str(DEFAULT_ORIGEN))
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--dim', type=int, default=100)
    parser.add_argument('--min-count', type=int, default=2)
    parser.add_argument('--alpha', type=float, default=0.75)
    parser.add_argument('--k-shift', type=float, default=1.0)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--window', type=int, default=5,
                         help='ventana deslizante palabra-contexto (hipotesis 7.1)')
    parser.add_argument('--incluir-dormidos', action='store_true', default=True,
                         help='Entrena también con nodos dormidos (default: sí, como word2vec_puro con --incluir-dormidos)')
    parser.add_argument('--solo-activos', dest='incluir_dormidos', action='store_false')
    parser.add_argument('--eval', action='store_true', help='evaluar los 35 fallos')
    parser.add_argument('--par', nargs=2, metavar=('TOKEN_A', 'TOKEN_B'),
                         help='coseno entre dos tokens ya stemmeados (control de cordura)')
    parser.add_argument('query', nargs='?', default=None,
                         help='si se da, solo recupera (requiere DB ya entrenada)')
    args = parser.parse_args()

    origen = Path(args.origen)
    db_path = Path(args.db)
    estados = None if args.incluir_dormidos else ['activo']

    if args.par:
        db = sqlite3.connect(db_path)
        modelo = _cargar_modelo(db)
        a, b = args.par
        va, vb = modelo.vector_token(a), modelo.vector_token(b)
        if va is None or vb is None:
            print(f"'{a}' en vocab: {va is not None} | '{b}' en vocab: {vb is not None}")
        else:
            print(f"coseno({a}, {b}) = {modelo.coseno(va, vb):.4f}")
        return

    if args.query:
        db = sqlite3.connect(db_path)
        resultados = recuperar(db, args.query)
        print("Top-10 por coseno:")
        for i, r in enumerate(resultados, 1):
            print(f"  {i:2}. {r['concepto']}  ({r['coseno']:.4f})")
        return

    # Entrenar
    print(f"Cargando contenidos de {origen} (incluir_dormidos={args.incluir_dormidos})...")
    corpus, conceptos, ests = cargar_contenidos(origen, estados)
    print(f"  {len(corpus)} nodos con contenido tokenizable.")

    modelo = PPMISVD(dim=args.dim, min_count=args.min_count, alpha=args.alpha,
                      k_shift=args.k_shift, seed=args.seed, window=args.window)
    print(f"Entrenando PPMI + SVD (matriz palabra-contexto, window={args.window})...")
    metricas = modelo.entrenar(corpus)
    print(f"  vocab={metricas['vocab']} dim_efectiva={metricas['dim_efectiva']} "
          f"varianza_explicada={metricas['varianza_explicada_top_k']} "
          f"({metricas['segundos']}s)")

    db = crear_db(db_path)
    guardar_vectores(db, modelo, corpus, conceptos, ests)
    meta_params(db, modelo, metricas)
    db.commit()
    print(f"Guardado en {db_path}")

    if args.eval:
        resultado = evaluar(db, origen, estados)
        print(json.dumps(resultado['resumen'], indent=2, ensure_ascii=False))
        print(json.dumps(resultado['criterios'], indent=2, ensure_ascii=False))
        out = db_path.parent / f'{db_path.stem}_eval.json'
        out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"Detalle guardado en {out}")


if __name__ == '__main__':
    main()
