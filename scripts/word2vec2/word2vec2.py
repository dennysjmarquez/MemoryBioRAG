#!/usr/bin/env python3
"""word2vec2.py — PPMI+SVD con expansion de corpus por sinonimos declarados.

POR QUE EXISTE:
v2_suave (scripts/ppmi_svd_puro_v2_suave.py) entrena PPMI+SVD usando SOLO el
contenido de cada nodo de BioRAG. Eso crea sinonimia distribucional nula
porque 71k tokens de corpus tecnico pequeno no contienen "perfil" co-ocurriendo
con el contenido de "dennys-identidad-profunda" — son nodos distintos.

Lo que el campo largo_plazo.sinonimos SI tiene: declaracion humana directa de
sinonimia (perfil,ingeniero,explorador). Esa declaracion es senal simbolica
perfecta — solo hay que inyectarla como co-ocurrencia en el corpus.

ESTE SCRIPT inyecta los sinonimos declarados de cada nodo como expansion de
su corpus ANTES de calcular PPMI. Asi, la palabra "perfil" co-ocurre
artificialmente con el contenido de "dennys-identidad-profunda" porque ambos
estan en el mismo documento (el documento expandido de ese nodo).

El resto del pipeline (PPMI con context smoothing alpha=0.75, SVD truncada,
pooling promedio de tokens del documento, evaluacion contra los 35 fallos)
es identico a v2_suave para que la comparacion sea limpia.

Si los vectores resultantes rankean los sinonimos en top-5, esta senal es
la palanca que faltaba — el siguiente paso es cablearla en
mcp_server.py (como capa adicional, no reemplazo, con feature flag).
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

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.pmi_semantico import _TOKEN_PATTERN, _TOKENS_CORTOS
from core.stopwords import STOPWORDS
from core.stemmer_es import stem as _stem

# Excepcion quirurgica para 'memoria', 'buscar', 'memory' (mismas que v2_suave)
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
DEFAULT_DB = ROOT / 'scripts' / 'word2vec2' / 'word2vec2_vectors.db'
DEFAULT_POOL = ROOT / 'scripts' / 'experimento_rr_pool.json'

FALLOS_POR_TEMA = ['0497', '0534', '0540', '0558', '0571', '0583', '0589', '0634',
                   '0640', '0652', '0670', '0706', '0730', '0736', '0765', '0783',
                   '0795', '0801', '0807', '0824', '0830']
FALLOS_SINONIMO = ['0514', '0520', '0532', '0563', '0625', '0734', '0740', '0757',
                   '0775', '0799', '0811', '0822', '0828', '0878']
FALLOS_ID = set(FALLOS_POR_TEMA + FALLOS_SINONIMO)


# =============================================================================
# PPMI + SVD (identico a v2_suave)
# =============================================================================

class PPMISVD:
    def __init__(self, dim: int = 100, min_count: int = 2, alpha: float = 0.75,
                 k_shift: float = 1.0, seed: int = 42):
        self.dim = dim
        self.min_count = min_count
        self.alpha = alpha
        self.k_shift = k_shift
        self.seed = seed
        self.vocab: dict[str, int] = {}
        self.freqs: dict[str, int] = {}
        self.W: np.ndarray | None = None

    def _construir_vocab(self, corpus: list[list[str]]) -> None:
        freqs_total: Counter = Counter()
        for doc in corpus:
            freqs_total.update(dict.fromkeys(doc, 1))
        self.freqs = {t: c for t, c in freqs_total.items() if c >= self.min_count}
        self.vocab = {t: i for i, t in enumerate(sorted(self.freqs))}

    def _matriz_termino_documento(self, corpus: list[list[str]]):
        from scipy.sparse import lil_matrix
        n_vocab = len(self.vocab)
        n_docs = len(corpus)
        M = lil_matrix((n_vocab, n_docs), dtype=np.float64)
        for j, doc in enumerate(corpus):
            c = Counter(t for t in doc if t in self.vocab)
            for t, cnt in c.items():
                M[self.vocab[t], j] = cnt
        return M.tocsr()

    def _ppmi(self, M):
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
        M = self._matriz_termino_documento(corpus)
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
# Persistencia
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
                       n_sinonimos INTEGER,
                       vector    BLOB
                   )""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_nodos_estado ON nodos(estado)")
    con.execute("CREATE TABLE data (clave TEXT PRIMARY KEY, valor TEXT)")
    return con


def cargar_contenidos(origen: Path, estados: list[str] | None = None):
    """Lee nodos Y sus sinonimos declarados; expande el corpus con sinonimos."""
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    if estados is None:
        filas = con.execute(
            "SELECT concepto, contenido, sinonimos, estado FROM largo_plazo"
        ).fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con.execute(
            f"SELECT concepto, contenido, sinonimos, estado FROM largo_plazo "
            f"WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    con.close()

    corpus, conceptos, ests = [], [], []
    for concepto, contenido, sinonimos, estado in filas:
        # Expansion: contenido + sinonimos declarados (separados por coma)
        texto_expandido = (contenido or '')
        if sinonimos:
            texto_expandido += ' ' + sinonimos.replace(',', ' ')
        toks = _tokenizar(texto_expandido)
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
        # Cuenta cuantos sinonimos aproximados hay (palabras que no estaban en contenido)
        # — solo metrica informativa, no afecta el vector
        n_sinonimos_aprox = n_tot - len(toks) // 2  # heuristica gruesa
        data_nodos.append((concepto, estado, n_tot, n_conv, n_sinonimos_aprox,
                           v.astype(np.float32).tobytes()))
    cur.executemany(
        "INSERT INTO nodos (concepto, estado, n_tokens, n_conv, n_sinonimos, vector) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        data_nodos,
    )
    cur.execute("COMMIT")


def meta_params(db: sqlite3.Connection, modelo: PPMISVD, metrics: dict) -> None:
    cur = db.cursor()
    cur.execute("BEGIN")
    params = {'metodo': 'word2vec2', 'expansion': 'sinonimos_declarados',
              'dim': modelo.dim, 'min_count': modelo.min_count, 'alpha': modelo.alpha,
              'k_shift': modelo.k_shift, 'seed': modelo.seed, **metrics}
    for k, v in params.items():
        cur.execute("INSERT OR REPLACE INTO data (clave, valor) VALUES (?, ?)", (k, str(v)))
    cur.execute("COMMIT")


# =============================================================================
# Recuperacion y evaluacion (identicas a v2_suave)
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


def evaluar(db: sqlite3.Connection, origen: Path, estados: list[str] | None = None) -> dict:
    modelo = _cargar_modelo(db)
    casos = json.loads(Path(DEFAULT_POOL).read_text(encoding='utf-8'))
    casos = [c for c in casos if c['id'] in FALLOS_ID]

    con_src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    cache_vec: dict = {}
    if estados is None:
        filas = con_src.execute(
            "SELECT concepto, contenido, sinonimos FROM largo_plazo"
        ).fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con_src.execute(
            f"SELECT concepto, contenido, sinonimos FROM largo_plazo "
            f"WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    for concepto, contenido, sinonimos in filas:
        # Para evaluacion, usa la MISMA expansion que en entrenamiento
        texto_expandido = (contenido or '')
        if sinonimos:
            texto_expandido += ' ' + sinonimos.replace(',', ' ')
        toks = _tokenizar(texto_expandido)
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
    parser.add_argument('--incluir-dormidos', action='store_true', default=True,
                        help='Entrena tambien con nodos dormidos (default: si)')
    parser.add_argument('--solo-activos', dest='incluir_dormidos', action='store_false')
    parser.add_argument('--eval', action='store_true', help='evaluar los 35 fallos')
    parser.add_argument('--par', nargs=2, metavar=('TOKEN_A', 'TOKEN_B'),
                        help='coseno entre dos tokens (control de cordura)')
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

    print(f"Cargando contenidos + sinonimos de {origen}...")
    corpus, conceptos, ests = cargar_contenidos(origen, estados)
    print(f"  {len(corpus)} nodos con contenido expandido tokenizable.")

    modelo = PPMISVD(dim=args.dim, min_count=args.min_count, alpha=args.alpha,
                      k_shift=args.k_shift, seed=args.seed)
    print("Entrenando PPMI+SVD con expansion por sinonimos...")
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
