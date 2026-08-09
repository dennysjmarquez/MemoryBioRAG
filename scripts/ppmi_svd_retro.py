#!/usr/bin/env python3
"""ppmi_svd_retro.py — PPMI+SVD + retrofitting con el grafo de sinapsis real.

POR QUÉ ESTE SCRIPT EXISTE:
ppmi_svd_puro_v2_suave.py (baseline) logró por_tema top5 15/21 pero sinonimo
top5 2/14 — el bloqueante. La hipótesis siguiente (2026-08-08): retrofitting
(Faruqui et al. 2015) usando la tabla `sinapsis` REAL de BioRAG como señal
relacional. Ningún experimento de la cadena usó el grafo, solo texto.

Retrofitting (Faruqui 2015) en una frase: refina vectores para que nodos
conectados en un grafo queden más cerca, sin alejarse demasiado del vector
original. Actualización iterativa:

    v̂_w^(t+1) = (1-α)·v_w + α · Σ_{n∈N(w)} w_wn · v̂_n^(t) / Σ_{n∈N(w)} w_wn

El grafo aquí es conceptos↔conceptos (sinapsis), así que se retrofitean los
VECTORES DE NODO (no los de token). Las queries se siguen calculando con
vectores de token (promedio) — igual que el baseline. Mecanismo esperado:
un concepto esperado que NO contiene la palabra del query en su contenido,
pero SÍ está sinápticamente conectado a un vecino que la contiene, se acerca
a ese vecino en el espacio → sube el coseno contra el query.

IMPORTANTE: evalúa los vectores retrofiteados tal como los usaría la
recuperación real (lee la tabla nodos de la DB de salida, no los recalcula
desde contenido), para que la medición sea fiel a lo que devolvería el sistema.

Qué NO usa: nada del pipeline de BioRAG (sin sinónimos, sin dimensiones, sin
fallbacks). Solo contenido de nodos + tabla sinapsis (lectura). No toca la DB
real. scipy + scikit-learn ya instalados.

Uso:
  python3 scripts/ppmi_svd_retro.py --eval                    # entrena + retrofitea + evalúa (default)
  python3 scripts/ppmi_svd_retro.py --alpha-retro 0.7 --it-retro 8 --eval
  python3 scripts/ppmi_svd_retro.py --solo-tipo sinonimo_explicito --eval
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ppmi_svd_puro_v2_suave import (  # noqa: E402  (baseline = fuente de verdad)
    DEFAULT_ORIGEN,
    DEFAULT_POOL,
    FALLOS_ID,
    PPMISVD,
    _tokenizar,
    cargar_contenidos,
)

DEFAULT_DB = ROOT / 'scripts' / 'ppmi_svd_puro' / 'ppmi_svd_vectors_retro.db'


# =============================================================================
# Grafo de sinapsis (solo lectura sobre memory_biorag.db)
# =============================================================================

def cargar_sinapsis(origen: Path, conceptos: set[str],
                    solo_tipo: str | None = None) -> dict[str, dict[str, float]]:
    """Devuelve {concepto: {vecino: peso}} restringido a conceptos entrenados."""
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    if solo_tipo:
        filas = con.execute(
            "SELECT origen, destino, peso FROM sinapsis WHERE tipo=?",
            (solo_tipo,),
        ).fetchall()
    else:
        filas = con.execute("SELECT origen, destino, peso FROM sinapsis").fetchall()
    con.close()

    adj: dict[str, dict[str, float]] = {}
    for o, d, p in filas:
        if o not in conceptos or d not in conceptos:
            continue
        so = adj.setdefault(o, {})
        so[d] = max(so.get(d, 0.0), p)
        sd = adj.setdefault(d, {})
        sd[o] = max(sd.get(o, 0.0), p)
    return adj


def _sinapsis_raw(origen: Path, solo_tipo: str | None) -> list[tuple]:
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    if solo_tipo:
        filas = con.execute(
            "SELECT origen, destino, peso FROM sinapsis WHERE tipo=?",
            (solo_tipo,),
        ).fetchall()
    else:
        filas = con.execute("SELECT origen, destino, peso FROM sinapsis").fetchall()
    con.close()
    return filas


def _retrofit_W(W_orig: np.ndarray, vocab: dict[str, int],
                adj_token: dict[str, dict[str, float]],
                alpha: float, iters: int, seed: int = 42) -> np.ndarray:
    """Retrofitting sobre la matriz de tokens W (cada token es un nodo)."""
    rng = np.random.default_rng(seed)
    Wh = W_orig.copy()
    con_neighbors = {t for t in adj_token if t in vocab and len(adj_token[t]) > 0}
    for _ in range(iters):
        nuevo = {}
        orden = list(con_neighbors)
        rng.shuffle(orden)
        for t in orden:
            vecinos = adj_token[t]
            total = sum(vecinos.values())
            if total <= 0:
                nuevo[t] = Wh[vocab[t]]
                continue
            prom = np.zeros_like(Wh[vocab[t]], dtype=np.float64)
            for n, p in vecinos.items():
                if n not in vocab:
                    continue
                prom += (p / total) * Wh[vocab[n]]
            nuevo[t] = (1 - alpha) * W_orig[vocab[t]] + alpha * prom
        for t, v in nuevo.items():
            Wh[vocab[t]] = v
    return Wh


def retrofitting(V: dict[str, np.ndarray], adj: dict[str, dict[str, float]],
                 alpha: float, iters: int, seed: int = 42) -> dict[str, np.ndarray]:
    """Vuelve a refinar vectores de nodo con el grafo (Faruqui 2015).

    V: {concepto: vector}. Solo se actualizan conceptos con vecinos en el
    grafo (los demás quedan con su vector original — igual que en Faruqui,
    donde solo se retrofitean palabras presentes en el léxico).
    """
    rng = np.random.default_rng(seed)
    Vh = {k: v.copy() for k, v in V.items()}
    con_neighbors = {k for k in adj if len(adj[k]) > 0}

    for _ in range(iters):
        nuevo: dict[str, np.ndarray] = {}
        orden = list(con_neighbors)
        rng.shuffle(orden)  # orden aleatorio (estándar en retrofitting)
        for w in orden:
            vecinos = adj[w]
            total = sum(vecinos.values())
            if total <= 0:
                nuevo[w] = Vh[w]
                continue
            prom = np.zeros_like(Vh[w], dtype=np.float64)
            for n, p in vecinos.items():
                prom += (p / total) * Vh[n]
            nuevo[w] = (1 - alpha) * V[w] + alpha * prom
        Vh.update(nuevo)
    return Vh


def grafo_tokens_desde_sinapsis(sinapsis, corpus_tokens: dict[str, list[str]],
                                top_k: int) -> dict[str, dict[str, float]]:
    """Expande el grafo concepto→concepto a token→token (modo 'tokens').

    Para cada arista (A, B) de sinapsis, conecta los tokens de A con los de B.
    Cada par (t_a, t_b) acumula el peso de la arista; al final se queda con los
    top_k vecinos más fuertes por token para limitar el tamaño del grafo.
    """
    adj_token: dict[str, dict[str, float]] = {}
    for a, b, peso in sinapsis:
        ta = corpus_tokens.get(a)
        tb = corpus_tokens.get(b)
        if not ta or not tb:
            continue
        for x in ta:
            ax = adj_token.setdefault(x, {})
            for y in tb:
                if x == y:
                    continue
                ax[y] = ax.get(y, 0.0) + peso
    for x, vecinos in adj_token.items():
        if len(vecinos) > top_k:
            top = sorted(vecinos.items(), key=lambda kv: -kv[1])[:top_k]
            adj_token[x] = dict(top)
    return adj_token


def retrofitting_tokens(W_orig: np.ndarray, V_orig: dict[str, np.ndarray],
                        Vh: dict[str, np.ndarray], corpus, conceptos,
                        vocab: dict[str, int], lam: float) -> np.ndarray:
    """Propaga el desplazamiento de los conceptos hacia sus tokens.

    Cada token se mueve en la dirección del desplazamiento promedio de los
    conceptos que lo contienen: si el concepto A quedó más cerca de B por
    retrofitting, los tokens de A (incluido el término de la query) se
    acercan a B. Así la señal del grafo llega al lado de la QUERY, que en el
    baseline nunca se movía.

    W_orig: matriz token×dim original (se copia).
    V_orig/Vh: vectores de concepto antes/después del retrofitting.
    Returns: matriz W' (no modifica la original).
    """
    disp: dict[str, np.ndarray] = {}
    for concepto, v_orig in V_orig.items():
        v_new = Vh[concepto]
        disp[concepto] = v_new - v_orig

    # acumulador por token: suma de desplazamientos de conceptos que lo contienen
    acum: dict[str, np.ndarray] = {}
    n_con: dict[str, int] = {}
    for toks, concepto in zip(corpus, conceptos):
        d = disp.get(concepto)
        if d is None:
            continue
        for t in set(toks):
            if t in vocab:
                acc = acum.setdefault(t, np.zeros_like(d))
                acc += d
                n_con[t] = n_con.get(t, 0) + 1

    Wp = W_orig.copy()
    for t, d in acum.items():
        if n_con[t] == 0:
            continue
        Wp[vocab[t]] += lam * (d / n_con[t])
    return Wp


# =============================================================================
# Evaluación (lee vectores de la DB de salida, como la recuperación real)
# =============================================================================

def evaluar_retro(db: sqlite3.Connection, origen: Path) -> dict:
    modelo = PPMISVD()

    filas_v = db.execute("SELECT token, vector FROM tokens").fetchall()
    modelo.vocab = {t: i for i, (t, _) in enumerate(filas_v)}
    modelo.dim = len(np.frombuffer(filas_v[0][1], dtype=np.float32)) if filas_v else 0
    W = np.zeros((len(filas_v), modelo.dim), dtype=np.float32)
    for t, blob in filas_v:
        W[modelo.vocab[t]] = np.frombuffer(blob, dtype=np.float32)
    modelo.W = W.astype(np.float64)
    modelo.freqs = {t: 0 for t, _ in filas_v}

    nodos = {r[0]: np.frombuffer(r[1], dtype=np.float32)
             for r in db.execute("SELECT concepto, vector FROM nodos").fetchall()}

    casos = json.loads(Path(DEFAULT_POOL).read_text(encoding='utf-8'))
    casos = [c for c in casos if c['id'] in FALLOS_ID]

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
            vn = nodos.get(cand['concepto'])
            if vn is None:
                vn = np.zeros(modelo.dim, dtype=np.float64)
            scores.append((cand['concepto'], modelo.coseno(vq, vn)))
        scores.sort(key=lambda x: -x[1])
        rank = next((i + 1 for i, (c, _) in enumerate(scores) if c == expected),
                    len(scores) + 1)
        top = [c for c, _ in scores[:5]]
        resumen[cat]['n'] += 1
        resumen[cat]['top1'] += rank == 1
        resumen[cat]['top5'] += rank <= 5
        resumen[cat]['top10'] += rank <= 10
        detalle.append({'id': caso['id'], 'categoria': cat, 'expected': expected,
                        'query': caso['query'], 'rank': rank, 'n_pool': len(scores),
                        'top5': top, 'query_degenerada': query_degenerada})

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
    parser.add_argument('--modo', type=str, default='concepto',
                        choices=['concepto', 'tokens'],
                        help='concepto: retrofitea vectores de nodo. '
                             'tokens: construye grafo de tokens desde sinapsis y '
                             'retrofitea la matriz W directamente (Faruqui sobre '
                             'la entidad que la query compara)')
    parser.add_argument('--top-tokens', type=int, default=40,
                        help='solo en modo tokens: máx vecinos por token al expandir '
                             'el grafo concepto→concepto a token→token')
    parser.add_argument('--alpha-retro', type=float, default=0.7)
    parser.add_argument('--it-retro', type=int, default=5)
    parser.add_argument('--lam-tokens', type=float, default=0.0,
                        help='propagar el desplazamiento de conceptos a sus tokens '
                             '(0 = solo retrofitting de conceptos)')
    parser.add_argument('--solo-tipo', type=str, default=None,
                        help='solo sinapsis de un tipo (ej: sinonimo_explicito)')
    parser.add_argument('--no-dormidos', dest='incluir_dormidos', action='store_false',
                        default=True)
    parser.add_argument('--eval', action='store_true', default=True,
                        help='evaluar los 35 fallos (default: sí)')
    args = parser.parse_args()

    origen = Path(args.origen)
    db_path = Path(args.db)
    estados = None if args.incluir_dormidos else ['activo']

    t0 = time.perf_counter()
    corpus, conceptos, ests = cargar_contenidos(origen, estados)
    conceptos_set = set(conceptos)
    print(f"  {len(corpus)} nodos tokenizables | {len(conceptos_set)} conceptos")

    modelo = PPMISVD(dim=args.dim, min_count=args.min_count, alpha=args.alpha,
                     k_shift=args.k_shift, seed=args.seed)
    metricas = modelo.entrenar(corpus)
    print(f"  entrenado: vocab={metricas['vocab']} dim={metricas['dim_efectiva']} "
          f"varianza={metricas['varianza_explicada_top_k']} ({metricas['segundos']}s)")

    V = {}
    for toks, concepto in zip(corpus, conceptos):
        v, _, _ = modelo.vector_documento(toks)
        V[concepto] = v

    print("  cargando sinapsis...")
    adj = cargar_sinapsis(origen, conceptos_set, solo_tipo=args.solo_tipo)
    n_edges = sum(len(ns) for ns in adj.values()) // 2
    print(f"  grafo: {len(adj)} conceptos con vecinos | {n_edges} aristas "
          f"{'(solo ' + args.solo_tipo + ')' if args.solo_tipo else ''}")

    t1 = time.perf_counter()
    if args.modo == 'concepto':
        Vh = retrofitting(V, adj, alpha=args.alpha_retro, iters=args.it_retro,
                          seed=args.seed)
        print(f"  retrofitting de conceptos α={args.alpha_retro} "
              f"it={args.it_retro} ({time.perf_counter() - t1:.1f}s)")
    else:  # modo tokens: retrofitting sobre la matriz W directamente
        corpus_tokens = {c: toks for c, toks in zip(conceptos, corpus)}
        sinapsis_raw = _sinapsis_raw(origen, args.solo_tipo)
        adj_token = grafo_tokens_desde_sinapsis(sinapsis_raw, corpus_tokens,
                                                args.top_tokens)
        n_edges_t = sum(len(ns) for ns in adj_token.values()) // 2
        print(f"  grafo de tokens: {len(adj_token)} tokens con vecinos | "
              f"{n_edges_t} aristas (top {args.top_tokens}/token)")
        Vh = {c: modelo.vector_documento(toks)[0]
              for toks, c in zip(corpus, conceptos)}
        W_orig = modelo.W.copy()
        # cada token es un nodo; retrofitting puro Faruqui sobre W
        modelo.W = _retrofit_W(W_orig, modelo.vocab, adj_token,
                               alpha=args.alpha_retro,
                               iters=args.it_retro, seed=args.seed)
        Vh = {c: modelo.vector_documento(toks)[0]
              for toks, c in zip(corpus, conceptos)}
        print(f"  retrofitting de tokens α={args.alpha_retro} "
              f"it={args.it_retro} ({time.perf_counter() - t1:.1f}s)")

    if args.lam_tokens > 0 and args.modo == 'concepto':
        t2 = time.perf_counter()
        modelo.W = retrofitting_tokens(
            modelo.W, V, Vh, corpus, conceptos, modelo.vocab,
            lam=args.lam_tokens)
        print(f"  propagación a tokens λ={args.lam_tokens} "
              f"({time.perf_counter() - t2:.1f}s)")

    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE tokens (token TEXT PRIMARY KEY, freq INTEGER, vector BLOB)")
    db.execute("""CREATE TABLE nodos (
                     concepto  TEXT PRIMARY KEY,
                     estado    TEXT,
                     n_tokens  INTEGER,
                     n_conv    INTEGER,
                     vector    BLOB
                 )""")
    db.execute("CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT)")
    db.execute("BEGIN")
    db.executemany("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)",
                   [(tok, modelo.freqs[tok], modelo.W[i].astype(np.float32).tobytes())
                    for tok, i in modelo.vocab.items()])
    for toks, concepto, estado in zip(corpus, conceptos, ests):
        v, n_conv, n_tot = modelo.vector_documento(toks)
        db.execute("INSERT INTO nodos (concepto, estado, n_tokens, n_conv, vector) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (concepto, estado, n_tot, n_conv, Vh[concepto].astype(np.float32).tobytes()))
    params = {'dim': modelo.dim, 'min_count': modelo.min_count, 'alpha': modelo.alpha,
              'k_shift': modelo.k_shift, 'seed': modelo.seed,
              'modo': args.modo, 'alpha_retro': args.alpha_retro,
              'it_retro': args.it_retro, 'lam_tokens': args.lam_tokens,
              'solo_tipo': args.solo_tipo or '', 'top_tokens': args.top_tokens,
              'n_edges': n_edges, **metricas}
    for k, v in params.items():
        db.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)", (k, str(v)))
    db.execute("COMMIT")
    print(f"  guardado en {db_path}")

    if args.eval:
        resultado = evaluar_retro(db, origen)
        print(json.dumps(resultado['resumen'], indent=2, ensure_ascii=False))
        print(json.dumps(resultado['criterios'], indent=2, ensure_ascii=False))
        out = db_path.parent / f'{db_path.stem}_eval.json'
        out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"Detalle guardado en {out}")
    db.close()


if __name__ == '__main__':
    main()
