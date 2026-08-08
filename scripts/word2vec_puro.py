#!/usr/bin/env python3
"""word2vec_puro.py — Word2Vec REAL, aislado del pipeline de BioRAG.

Qué es: implementación propia de skip-gram + negative sampling (SGNS),
la misma maquinaria de Mikolov et al. 2013 (word2vec de Google), en numpy puro.

Qué NO usa: NINGUNA capa del pipeline de BioRAG (sin sinónimos, sin paráfrasis,
sin dimensiones, sin fallbacks, sin sinapsis). Solo el contenido de los nodos.

Qué hace (3 etapas):
  1) CREA UNA BASE DE DATOS NUEVA (nunca toca la real):
     - Copia la tabla largo_plazo completa del snapshot.
     - Esta DB nueva es la dueña de los vectores.
  2) ENTRENA: el corpus son los tokens del CONTENIDO de cada nodo activo.
     Cada nodo es una "oración" = su contenido tokenizado. La ventana
     deslizante recorre el contenido y aprende los vecinos de cada token.
  3) GUARDA Y RECUPERA:
     - Tabla `tokens`:    token → vector (numpy float32, BLOB).
     - Tabla `nodos`:     concepto → vector del nodo = promedio de los
       vectores de los tokens de su contenido.
     - Recuperación: query → se tokeniza → promedio de vectores conocidos →
       coseno contra el vector de cada nodo → top-N.
     - Si ningún token del query es conocido → vector cero (score 0), y se
       reporta la cobertura de vocabulario (para no inventar).

Dónde se guarda todo: --db (default scripts/word2vec_puro/word2vec_vectors.db).
Cómo se recupera: python3 scripts/word2vec_puro.py "mi consulta"

Uso:
  python3 scripts/word2vec_puro.py                          # entrena y guarda
  python3 scripts/word2vec_puro.py "perfil de dennys"       # recupera top-10
  python3 scripts/word2vec_puro.py --eval                   # evalúa los 35 fallos
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pmi_semantico import _tokenizar  # la tokenización léxica del sistema

DEFAULT_SNAPSHOT = ROOT / 'snapshots' / 'word2vec_pre_fase0_20260806_235239.db'
DEFAULT_DB = ROOT / 'scripts' / 'word2vec_puro' / 'word2vec_vectors.db'
DEFAULT_POOL = ROOT / 'scripts' / 'experimento_rr_pool.json'

FALLOS_POR_TEMA = ['0497', '0534', '0540', '0558', '0571', '0583', '0589', '0634',
                   '0640', '0652', '0670', '0706', '0730', '0736', '0765', '0783',
                   '0795', '0801', '0807', '0824', '0830']
FALLOS_SINONIMO = ['0514', '0520', '0532', '0563', '0625', '0734', '0740', '0757',
                   '0775', '0799', '0811', '0822', '0828', '0878']
FALLOS_ID = set(FALLOS_POR_TEMA + FALLOS_SINONIMO)


# =============================================================================
# SGNS — skip-gram con negative sampling (word2vec real)
# =============================================================================

class SGNS:
    """Skip-gram + negative sampling (Levy & Goldberg 2014 = factoriza PMI − log k).

    Cada palabra tiene DOS vectores: input (v_w, el que queda) y output (v'_w,
    el contexto). La actualización es el gradiente de la pérdida sigmoide:
        g = σ(v_w · v'_x) − label   (label=1 positivo, 0 negativo)
        v_w  −= lr · g · v'_x
        v'_x −= lr · g · v_w
    """

    def __init__(self, dim: int = 100, window: int = 5, negative: int = 5,
                 min_count: int = 3, epochs: int = 8, lr: float = 0.05,
                 subsample: float = 1e-3, seed: int = 42):
        self.dim = dim
        self.window = window
        self.negative = negative
        self.min_count = min_count
        self.epochs = epochs
        self.lr = lr
        self.subsample = subsample
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.vocab: dict[str, int] = {}
        self.freqs: dict[str, int] = {}
        self.W: np.ndarray | None = None      # input  (V, dim)  ← se queda
        self.Wp: np.ndarray | None = None     # output (V, dim)  ← contexto

    # ------------------------------------------------------------------

    def _construir_vocab(self, corpus: list[list[str]]) -> None:
        """Frecuencias de tokens; descarta los que aparecen < min_count."""
        freqs_total: Counter = Counter()
        for doc in corpus:
            freqs_total.update(dict.fromkeys(doc, 1))  # cuenta 1 por documento
        self.freqs_total = dict(freqs_total)
        self.freqs = {t: c for t, c in freqs_total.items() if c >= self.min_count}
        self.vocab = {t: i for i, t in enumerate(sorted(self.freqs))}

    def _submuestrear(self, doc: list[str]) -> list[str]:
        """Descartar tokens ultra-frecuentes (Mikolov et al. 2013)."""
        if not self.subsample or self.subsample <= 0:
            return doc
        out = []
        t = self.subsample
        for tok in doc:
            f = self.freqs_total.get(tok, 0)
            if f <= 0:
                continue
            keep = 1.0 - np.sqrt(t / f)
            prob_keep = max(keep, 0.0) if f > t else 1.0
            if self.rng.random() < prob_keep:
                out.append(tok)
        return out

    def entrenar(self, corpus: list[list[str]]) -> dict:
        """Entrena SGNS sobre el corpus de contenidos. Retorna métricas."""
        self._construir_vocab(corpus)
        V = len(self.vocab)
        self.W = self.rng.uniform(-0.5 / self.dim, 0.5 / self.dim, (V, self.dim))
        self.Wp = np.zeros((V, self.dim), dtype=np.float64)

        # Distribución de ruido unigram^0.75 (Mikolov)
        probs = np.array([self.freqs[t] ** 0.75 for t in self.vocab], dtype=np.float64)
        probs /= probs.sum()

        total_pares = 0
        t0 = time.perf_counter()

        for epoch in range(self.epochs):
            lr = self.lr * (1.0 - epoch / max(1, self.epochs))  # decaimiento lineal
            n_pares = 0
            for doc in corpus:
                doc = self._submuestrear(doc)
                idx = [self.vocab[t] for t in doc if t in self.vocab]
                n = len(idx)
                if n < 2:
                    continue
                # por centro, contextos de la ventana
                for i, c in enumerate(idx):
                    lo = max(0, i - self.window)
                    hi = min(n, i + self.window + 1)
                    ctx = [idx[j] for j in range(lo, hi) if j != i]
                    if not ctx:
                        continue
                    self._actualizar(c, ctx, probs, lr)
                    n_pares += len(ctx)
            total_pares += n_pares
            print(f"    epoch {epoch+1}/{self.epochs}: {n_pares} pares, lr={lr:.4f}")

        return {
            'vocab': V,
            'pares_total': total_pares,
            'segundos': round(time.perf_counter() - t0, 1),
        }

    def _actualizar(self, c: int, ctx: list[int], probs: np.ndarray, lr: float) -> None:
        """Un centro c contra sus contextos + negativos muestreados."""
        w = self.W[c]
        for x in ctx:
            g = 1.0 / (1.0 + np.exp(-float(w @ self.Wp[x]))) - 1.0  # label=1
            self.W[c] -= lr * g * self.Wp[x]
            self.Wp[x] -= lr * g * w
        # negativos
        negs = self.rng.choice(len(self.vocab), size=self.negative, p=probs)
        for x in negs:
            if x == c:
                continue
            g = 1.0 / (1.0 + np.exp(-float(w @ self.Wp[x]))) - 0.0  # label=0
            self.W[c] -= lr * g * self.Wp[x]
            self.Wp[x] -= lr * g * w

    # ------------------------------------------------------------------

    def vector_token(self, tok: str) -> np.ndarray | None:
        i = self.vocab.get(tok)
        return self.W[i] if i is not None else None

    def vector_tokens(self, tokens: list[str]) -> np.ndarray:
        """Promedio de los vectores de los tokens conocidos. Cero si ninguno."""
        vs = [self.W[self.vocab[t]] for t in tokens if t in self.vocab]
        if not vs:
            return np.zeros(self.dim, dtype=np.float64)
        return np.mean(vs, axis=0)

    def vector_documento(self, tokens: list[str]) -> tuple[np.ndarray, int, int]:
        """Vector del documento = promedio de tokens conocidos.
        Retorna (vector, n_conocidos, n_total)."""
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
# Base de datos nueva (dueña de nodos copiados + vectores)
# =============================================================================

def crear_db(snapshot: Path, db: Path) -> sqlite3.Connection:
    """Copia largo_plazo del snapshot a la DB nueva y crea las tablas de vectores."""
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    src = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    dst = sqlite3.connect(db)
    cols = [r[1] for r in src.execute("PRAGMA table_info(largo_plazo)")]
    col_list = ", ".join(cols)
    dst.execute("BEGIN")
    dst.execute(f"CREATE TABLE largo_plazo ({col_list})")
    rows = src.execute("SELECT * FROM largo_plazo").fetchall()
    dst.executemany(f"INSERT INTO largo_plazo ({col_list}) VALUES ({', '.join(['?']*len(cols))})", rows)
    dst.execute("CREATE INDEX IF NOT EXISTS ix_concepto ON largo_plazo(concepto)")
    dst.execute("CREATE INDEX IF NOT EXISTS ix_estado ON largo_plazo(estado)")
    dst.execute(
        """CREATE TABLE tokens (
               token TEXT PRIMARY KEY,
               freq  INTEGER,
               vector BLOB
           )"""
    )
    dst.execute(
        """CREATE TABLE nodos (
               concepto  TEXT PRIMARY KEY,
               estado    TEXT,
               n_tokens  INTEGER,
               n_conv    INTEGER,
               vector    BLOB
           )"""
    )
    dst.execute("CREATE INDEX IF NOT EXISTS ix_nodos_estado ON nodos(estado)")
    dst.execute(
        """CREATE TABLE meta (
               clave TEXT PRIMARY KEY,
               valor TEXT
           )"""
    )
    dst.execute("COMMIT")
    src.close()
    return dst


# =============================================================================
# Entrenamiento
# =============================================================================

def cargar_contenidos(snapshot: Path, estados: list[str] | None = None) -> tuple[list[list[str]], list[str]]:
    """Corpus = contenido tokenizado de los nodos ACTIVOS (o todos si estados=None)."""
    con = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    if estados is None:
        filas = con.execute("SELECT concepto, contenido FROM largo_plazo").fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con.execute(
            f"SELECT concepto, contenido FROM largo_plazo WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    con.close()
    corpus, conceptos = [], []
    for concepto, contenido in filas:
        toks = _tokenizar(contenido or '')
        if len(toks) >= 2:
            corpus.append(toks)
            conceptos.append(concepto)
    return corpus, conceptos


def guardar_vectores(db: sqlite3.Connection, sgns: SGNS, snapshot: Path,
                     estados: list[str] | None = None) -> None:
    """Guarda los vectores de token y de nodo en la DB nueva."""
    cur = db.cursor()
    cur.execute("BEGIN")
    data_tok = [(tok, sgns.freqs[tok], sgns.W[i].astype(np.float32).tobytes())
                for tok, i in sgns.vocab.items()]
    cur.executemany("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", data_tok)

    # vectores de nodo: promedio de los tokens de su contenido
    con_src = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    if estados is None:
        filas = con_src.execute(
            "SELECT concepto, contenido, estado FROM largo_plazo"
        ).fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con_src.execute(
            f"SELECT concepto, contenido, estado FROM largo_plazo WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    con_src.close()
    data_nodos = []
    for concepto, contenido, estado in filas:
        toks = _tokenizar(contenido or '')
        v, n_conv, n_tot = sgns.vector_documento(toks)
        data_nodos.append((concepto, estado, n_tot, n_conv, v.astype(np.float32).tobytes()))
    cur.executemany(
        "INSERT INTO nodos (concepto, estado, n_tokens, n_conv, vector) VALUES (?, ?, ?, ?, ?)",
        data_nodos,
    )
    cur.execute("COMMIT")


def meta_params(db: sqlite3.Connection, sgns: SGNS, corpus_metrics: dict) -> None:
    cur = db.cursor()
    cur.execute("BEGIN")
    for k, v in {
        **sgns.__dict__,
        'rng': None,
        'W': None,
        'Wp': None,
        'corpus': json.dumps(corpus_metrics),
    }.items():
        cur.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)",
                    (k, str(v)))
    cur.execute("COMMIT")


# =============================================================================
# Recuperación
# =============================================================================

def recuperar(db: sqlite3.Connection, query: str, top_n: int = 10,
              solo_activos: bool = True) -> list[dict]:
    """Query → tokens → vector promedio → coseno contra todos los nodos."""
    sgns = _cargar_sgns(db)
    q_toks = _tokenizar(query)
    vq = sgns.vector_tokens(q_toks)
    n_conocidos = sum(1 for t in q_toks if t in sgns.vocab)

    cond = "WHERE estado='activo'" if solo_activos else ""
    filas = db.execute(f"SELECT concepto, vector FROM nodos {cond}").fetchall()
    scores = []
    for concepto, blob in filas:
        if not blob:
            continue
        vn = np.frombuffer(blob, dtype=np.float32)
        scores.append((concepto, sgns.coseno(vq, vn)))
    scores.sort(key=lambda x: -x[1])

    return [{'concepto': c, 'coseno': round(s, 4)} for c, s in scores[:top_n]]


def _cargar_sgns(db: sqlite3.Connection) -> SGNS:
    """Reconstruye SGNS con vocabulario y W desde la DB (para recuperar sin re-entrenar)."""
    filas = db.execute("SELECT token, vector FROM tokens").fetchall()
    sgns = SGNS()
    sgns.vocab = {t: i for i, (t, _) in enumerate(filas)}
    sgns.dim = len(np.frombuffer(filas[0][1], dtype=np.float32)) if filas else 0
    W = np.zeros((len(filas), sgns.dim), dtype=np.float32)
    freqs = {}
    for t, blob in filas:
        W[sgns.vocab[t]] = np.frombuffer(blob, dtype=np.float32)
        freqs[t] = 0
    sgns.W = W.astype(np.float64)
    sgns.Wp = np.zeros_like(W).astype(np.float64)
    sgns.freqs = freqs
    return sgns


# =============================================================================
# Evaluación contra los 35 fallos (comparación justa con los gates)
# =============================================================================

def evaluar(db: sqlite3.Connection, snapshot: Path,
            estados: list[str] | None = None) -> dict:
    sgns = _cargar_sgns(db)
    casos = json.loads(Path(DEFAULT_POOL).read_text(encoding='utf-8'))
    casos = [c for c in casos if c['id'] in FALLOS_ID]

    # vector por concepto (desde contenido del snapshot)
    con_src = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    cache_vec: dict = {}
    if estados is None:
        filas = con_src.execute(
            "SELECT concepto, contenido FROM largo_plazo"
        ).fetchall()
    else:
        marks = ", ".join(['?'] * len(estados))
        filas = con_src.execute(
            f"SELECT concepto, contenido FROM largo_plazo WHERE estado IN ({marks})",
            estados,
        ).fetchall()
    for concepto, contenido in filas:
        toks = _tokenizar(contenido or '')
        v, _, _ = sgns.vector_documento(toks)
        cache_vec[concepto] = v
    con_src.close()

    resumen = {'por_tema': {'n': 0, 'top1': 0, 'top5': 0, 'top10': 0},
               'sinonimo': {'n': 0, 'top1': 0, 'top5': 0, 'top10': 0}}
    detalle = []
    for caso in casos:
        cat = 'por_tema' if caso['categoria'] == 'por_tema' else 'sinonimo'
        expected = caso['expected']
        vq = sgns.vector_tokens(_tokenizar(caso['query']))
        scores = []
        for cand in caso['pool']:
            vn = cache_vec.get(cand['concepto'])
            if vn is None:
                vn = np.zeros(sgns.dim)
            scores.append((cand['concepto'], sgns.coseno(vq, vn)))
        scores.sort(key=lambda x: -x[1])
        rank = next((i + 1 for i, (c, _) in enumerate(scores) if c == expected),
                    len(scores) + 1)
        resumen[cat]['n'] += 1
        resumen[cat]['top1'] += rank == 1
        resumen[cat]['top5'] += rank <= 5
        resumen[cat]['top10'] += rank <= 10
        detalle.append({'id': caso['id'], 'categoria': cat, 'expected': expected,
                        'query': caso['query'], 'rank': rank, 'n_pool': len(scores)})

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
    parser.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--dim', type=int, default=100)
    parser.add_argument('--window', type=int, default=5)
    parser.add_argument('--negative', type=int, default=5)
    parser.add_argument('--min-count', type=int, default=3)
    parser.add_argument('--epochs', type=int, default=8)
    parser.add_argument('--lr', type=float, default=0.05)
    parser.add_argument('--subsample', type=float, default=1e-3)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--incluir-dormidos', action='store_true',
                        help='entrenar y vectorizar activos + dormidos (default: solo activos)')
    parser.add_argument('--eval', action='store_true', help='evaluar los 35 fallos')
    parser.add_argument('query', nargs='?', default=None,
                        help='consulta para recuperar (si se pasa, solo recupera)')
    args = parser.parse_args()

    snapshot = Path(args.snapshot)
    db_path = Path(args.db)
    estados = None if args.incluir_dormidos else ['activo']

    # ---- Solo recuperación --------------------------------------------
    if args.query:
        if not db_path.exists():
            print(f"[ERR] No existe la DB de vectores: {db_path}\n"
                  "      Corré primero: python3 scripts/word2vec_puro.py")
            sys.exit(1)
        con = sqlite3.connect(db_path)
        q_toks = _tokenizar(args.query)
        sgns = _cargar_sgns(con)
        n_conoc = sum(1 for t in q_toks if t in sgns.vocab)
        top = recuperar(con, args.query, top_n=10)
        print(f"Query: {args.query!r}   | tokens={len(q_toks)} conocidos={n_conoc} "
              f"({100*n_conoc//max(1,len(q_toks))}%)")
        print("Top-10 por coseno:")
        for i, r in enumerate(top, 1):
            print(f"  {i:2d}. {r['concepto']}  ({r['coseno']:.4f})")
        con.close()
        return

    # ---- Entrenar y guardar -------------------------------------------
    t0 = time.time()
    print(f"[1/4] Creando DB nueva: {db_path}")
    db = crear_db(snapshot, db_path)

    print("[2/4] Cargando corpus de contenidos (solo contenido, nada más)...")
    corpus, conceptos = cargar_contenidos(snapshot, estados)
    print(f"      {len(corpus)} nodos ({'todos' if estados is None else 'activos'}) "
          f"con contenido, {sum(len(d) for d in corpus)} tokens totales")

    print("[3/4] Entrenando SGNS (skip-gram + negative sampling)...")
    sgns = SGNS(dim=args.dim, window=args.window, negative=args.negative,
                min_count=args.min_count, epochs=args.epochs, lr=args.lr,
                subsample=args.subsample, seed=args.seed)
    metrics = sgns.entrenar(corpus)
    print(f"      vocabulario={metrics['vocab']} pares={metrics['pares_total']} "
          f"({metrics['segundos']}s)")

    print("[4/4] Guardando vectores en la DB nueva...")
    guardar_vectores(db, sgns, snapshot, estados)
    meta_params(db, sgns, metrics)

    if args.eval:
        print("\n[EVAL] Evaluando los 35 fallos (pool idéntico a los gates):")
        res = evaluar(db, snapshot, estados)
        r = res['resumen']
        print(f"  por_tema : top1={r['por_tema']['top1']}/{r['por_tema']['n']} "
              f"top5={r['por_tema']['top5']}/{r['por_tema']['n']} "
              f"top10={r['por_tema']['top10']}/{r['por_tema']['n']}")
        print(f"  sinonimo : top1={r['sinonimo']['top1']}/{r['sinonimo']['n']} "
              f"top5={r['sinonimo']['top5']}/{r['sinonimo']['n']} "
              f"top10={r['sinonimo']['top10']}/{r['sinonimo']['n']}")
        Path(db_path.parent / 'word2vec_puro_eval.json').write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n[OK] Listo. DB de vectores: {db_path}  ({round(time.time()-t0,1)}s)")
    print(f"     Recuperar: python3 scripts/word2vec_puro.py \"tu consulta\"")
    db.close()


if __name__ == '__main__':
    main()
