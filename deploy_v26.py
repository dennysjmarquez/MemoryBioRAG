#!/usr/bin/env python3
"""deploy_v26.py — Despliegue Autocontenido de BioRAG v26.0 (PPMI+SVD + Retrofitting)

Este script es 100% autocontenido. No depende de importaciones relativas de word2vec.
Copia los módulos y crea las tablas `tokens`, `nodos`, `meta` en la DB de producción.

Ejecutar DESDE /mnt/recursos_compartidos_y_otros/MemoryBioRAG/:
    python3 deploy_v26.py
"""
import sys
import shutil
import sqlite3
import math
import time
import re
import struct
from pathlib import Path

# ──────────────────────────────────────────────────
#  CONFIGURACIÓN
# ──────────────────────────────────────────────────
BIORAG_ROOT   = Path(__file__).resolve().parent
WORD2VEC_ROOT = BIORAG_ROOT.parent / 'word2vec'
DB_PATH       = BIORAG_ROOT / 'MemoryBioRAG_Data' / 'memory_biorag.db'

# ──────────────────────────────────────────────────
#  PASO 0: Copiar módulos al core de MemoryBioRAG
# ──────────────────────────────────────────────────
def paso_copiar_modulos():
    print("=== [1/4] COPIANDO MÓDULOS AL CORE DE MEMORYBIORAG ===")
    core_dir = BIORAG_ROOT / 'core'
    src1 = WORD2VEC_ROOT / 'integracion_biorag' / 'ppmi_vectorizer.py'
    src2 = WORD2VEC_ROOT / 'integracion_biorag' / 'ppmi_hybrid_search.py'
    for src in [src1, src2]:
        if not src.exists():
            print(f"  ✘ No encontrado: {src}")
            print("    Asegurate de tener /mnt/recursos_compartidos_y_otros/word2vec/integracion_biorag/")
            sys.exit(1)
        dst = core_dir / src.name
        shutil.copy(src, dst)
        print(f"  ✔ {src.name}  →  {dst}")

# ──────────────────────────────────────────────────
#  TOKENIZADOR AUTÓNOMO (sin imports de core/)
# ──────────────────────────────────────────────────
_TOKEN_PATTERN = re.compile(r"[a-záéíóúüñ]{3,}", re.UNICODE | re.IGNORECASE)

# Stopwords básicas ES + EN (subset suficiente para el corpus)
_STOPWORDS = {
    'que','de','la','el','en','y','a','los','del','se','las','por','un','para','con','una','su',
    'es','al','lo','como','más','pero','sus','le','ya','o','fue','este','ha','si','porque',
    'esta','son','entre','está','cuando','muy','sin','sobre','ser','tiene','le','lo','también',
    'hasta','hay','donde','quien','desde','todo','nos','durante','todos','uno','les','ni','contra',
    'otros','ese','eso','ante','ellos','e','esto','mí','antes','algunos','qué','unos','yo','otro',
    'otras','él','tanto','esa','estos','mucho','quienes','nada','muchos','cual','poco','ella',
    'estar','estas','alguna','algo','nosotros','mi','mis','tú','te','ti','tu','tus','vosotros',
    'vosotras','os','mío','mía','míos','mías','tuyo','tuya','tuyos','tuyas','suyo','suya','suyos',
    'suyos','suyas','nuestro','nuestra','nuestros','nuestras','vuestro','vuestra','vuestros',
    'the','of','and','to','in','is','it','for','on','are','that','this','with','be','as','at',
    'by','an','we','or','but','not','from','they','have','had','has','was','were','been','their',
    'its','our','which','do','did','will','would','could','should','may','might',
    # Stopwords funcionales frecuentes en el corpus
    'usar','hace','puede','debe','cada','bien','caso','tipo','vez','forma','parte','modo',
    'dentro','fuera','mismo','además','aunque','mientras','tanto','tal',
}
_EXCEPCIONES = {'memoria', 'buscar', 'memory'}
_STOPWORDS_SUAVE = _STOPWORDS - _EXCEPCIONES

# Stemmer superficial (suficiente para el corpus ES/EN sin dependencias)
_SUFIJOS = ['aciones','amiento','amiento','adores','adora','aciones','ación','ando','ando',
            'mente','istas','ista','ados','adas','ados','iendo','iente','ientes','idades',
            'idad','ados','adas','ado','ada','ados','ando','ando','ando',
            'ing','tion','ions','ness','ment','ments','ings','ers','ers','ed']

def _stem(w):
    """Stemmer superficial por sufijos — suficiente para el corpus."""
    w = w.lower()
    for suf in sorted(_SUFIJOS, key=len, reverse=True):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w

def _tokenizar(texto):
    if not texto:
        return []
    texto = texto.replace('_', ' ').replace('-', ' ')
    tokens = _TOKEN_PATTERN.findall(texto.lower())
    resultado = [t for t in tokens if t not in _STOPWORDS_SUAVE]
    return [_stem(t) for t in resultado]

# ──────────────────────────────────────────────────
#  MOTOR PPMI + SVD (autocontenido, sólo numpy)
# ──────────────────────────────────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

def _ppmi_svd(corpus, conceptos, dim=100, alpha=0.75, k_shift=1.0, seed=42):
    """Factorización PPMI+SVD puramente con numpy."""
    # Vocabulario
    counts = {}
    for doc in corpus:
        for t in doc:
            counts[t] = counts.get(t, 0) + 1
    vocab_list = sorted([t for t, c in counts.items() if c >= 1])
    vocab = {t: i for i, t in enumerate(vocab_list)}
    V = len(vocab_list)
    D = len(corpus)

    if V == 0 or D == 0:
        return {}, {}, np.array([]), vocab, vocab_list

    doc_counts = np.zeros((V, D), dtype='float64')
    for d_idx, doc in enumerate(corpus):
        for t in doc:
            if t in vocab:
                doc_counts[vocab[t], d_idx] += 1.0

    tf = np.log1p(doc_counts)
    p_td = tf / (tf.sum() + 1e-12)
    p_t = p_td.sum(axis=1, keepdims=True)
    p_d = p_td.sum(axis=0, keepdims=True)
    p_t_alpha = p_t ** alpha
    p_t_alpha /= (p_t_alpha.sum() + 1e-12)
    den = p_t_alpha @ p_d
    pmi = np.log(np.maximum(p_td, 1e-12) / np.maximum(den, 1e-12))
    ppmi = np.maximum(pmi - math.log(k_shift), 0.0)

    dim_real = min(dim, V, D)
    np.random.seed(seed)
    try:
        U, S, Vt = np.linalg.svd(ppmi, full_matrices=False)
        U = U[:, :dim_real]
        S = S[:dim_real]
    except np.linalg.LinAlgError:
        U = np.eye(V, dim_real)
        S = np.ones(dim_real)

    W = U * np.power(S, 0.5)                       # [V, dim]

    # IDF de palabras (para pooling)
    df = (doc_counts > 0).sum(axis=1)
    idf = np.log((D + 1.0) / (df + 1.0)) + 1.0     # [V]

    # Vectores de token
    tok_vecs = {vocab_list[i]: W[i] for i in range(V)}

    # Vectores de nodo (IDF-weighted pooling)
    nodo_vecs = {}
    for toks, c in zip(corpus, conceptos):
        idxs = [vocab[t] for t in toks if t in vocab]
        if not idxs:
            nodo_vecs[c] = np.zeros(dim_real)
        else:
            w_idf = idf[idxs, np.newaxis]
            nodo_vecs[c] = (W[idxs] * w_idf).sum(axis=0) / (w_idf.sum() + 1e-12)

    return tok_vecs, nodo_vecs, idf, vocab, vocab_list, W, V, dim_real


def _retrofit(nodo_vecs, adj, iters=5, lam=0.2):
    orig = {k: v.copy() for k, v in nodo_vecs.items()}
    new_vecs = {k: v.copy() for k, v in orig.items()}
    for _ in range(iters):
        for node in new_vecs:
            vecinos = adj.get(node, [])
            if not vecinos:
                continue
            num = np.zeros_like(new_vecs[node])
            den = 0.0
            for vec_id, weight in vecinos:
                if vec_id in new_vecs:
                    num += weight * new_vecs[vec_id]
                    den += weight
            if den > 0:
                new_vecs[node] = (1.0 - lam) * orig[node] + lam * (num / den)
    return new_vecs


# ──────────────────────────────────────────────────
#  PASO 1: REINDEXAR LA DB
# ──────────────────────────────────────────────────
def paso_reindexar(db_path):
    print(f"\n=== [2/4] REINDEXANDO CORTEZA EN: {db_path} ===")
    if not HAS_NUMPY:
        sys.exit("numpy no disponible. Instala: pip install numpy")

    t0 = time.perf_counter()
    con = sqlite3.connect(db_path)

    # --- Crear tablas ---
    con.execute("CREATE TABLE IF NOT EXISTS tokens (token TEXT PRIMARY KEY, freq INTEGER, vector BLOB)")
    con.execute("""CREATE TABLE IF NOT EXISTS nodos (
                       concepto  TEXT PRIMARY KEY,
                       estado    TEXT,
                       n_tokens  INTEGER,
                       n_conv    INTEGER,
                       vector    BLOB
                   )""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_nodos_estado ON nodos(estado)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT)")

    # --- Cargar corpus ---
    filas = con.execute("SELECT concepto, contenido, sinonimos, estado FROM largo_plazo").fetchall()
    corpus, conceptos, ests = [], [], []
    for concepto, contenido, sinonimos, estado in filas:
        concepto_clean = concepto.replace('_', ' ').replace('-', ' ')
        texto = f"{concepto_clean} {sinonimos or ''} {contenido or ''}"
        toks = _tokenizar(texto)
        if len(toks) >= 1:
            corpus.append(toks)
            conceptos.append(concepto)
            ests.append(estado)

    print(f"  Corpus: {len(corpus)} nodos, {sum(len(d) for d in corpus)} tokens")

    # --- Entrenar PPMI+SVD ---
    result = _ppmi_svd(corpus, conceptos)
    tok_vecs, nodo_vecs_raw, idf, vocab, vocab_list, W, V, dim_real = result

    print(f"  Vocabulario: {V} terms | Dimensión SVD: {dim_real}")

    # --- Cargar sinapsis para retrofitting ---
    tipos_syn = ('sinonimo_explicito', 'pmi_hebbiano', 'co_semantica', 'manual')
    ph = ",".join("?" for _ in tipos_syn)
    rows_syn = con.execute(f"SELECT origen, destino, peso FROM sinapsis WHERE tipo IN ({ph})", tipos_syn).fetchall()
    adj = {}
    for o, d, w in rows_syn:
        weight = float(w or 0.5)
        adj.setdefault(o, []).append((d, weight))
        adj.setdefault(d, []).append((o, weight))
    print(f"  Sinapsis para retrofitting: {len(rows_syn)} aristas")

    # --- Retrofitting ---
    nodo_vecs = _retrofit(nodo_vecs_raw, adj, iters=5, lam=0.2)

    # --- Guardar tokens ---
    freq_map = {}
    for doc in corpus:
        for t in doc:
            freq_map[t] = freq_map.get(t, 0) + 1
    con.execute("DELETE FROM tokens")
    con.executemany(
        "INSERT INTO tokens VALUES (?, ?, ?)",
        [(t, freq_map.get(t, 0), v.astype('float32').tobytes()) for t, v in tok_vecs.items()]
    )
    print(f"  ✔ {len(tok_vecs)} vectores de token guardados en tabla `tokens`")

    # --- Guardar nodos ---
    con.execute("DELETE FROM nodos")
    nodos_rows = []
    for toks, c, e in zip(corpus, conceptos, ests):
        v = nodo_vecs.get(c, np.zeros(dim_real))
        nodos_rows.append((c, e, len(toks), len([t for t in toks if t in vocab]), v.astype('float32').tobytes()))
    con.executemany("INSERT INTO nodos VALUES (?, ?, ?, ?, ?)", nodos_rows)
    print(f"  ✔ {len(nodos_rows)} vectores de nodo guardados en tabla `nodos` (con retrofitting)")

    # --- Metadatos ---
    for k, v in [
        ('motor', 'PPMI+SVD+Retrofit_v26.0'),
        ('dim', str(dim_real)),
        ('vocab', str(V)),
        ('nodos', str(len(nodos_rows))),
        ('tokens', str(len(tok_vecs))),
        ('retrofit_iters', '5'),
        ('retrofit_lam', '0.2'),
        ('actualizado_en', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())),
        ('version', 'v26.0'),
    ]:
        con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, v))

    con.commit()
    con.close()
    dt = time.perf_counter() - t0
    print(f"\n  ✔ REINDEXACIÓN COMPLETA en {dt:.2f}s")
    return len(nodos_rows), V, dim_real


# ──────────────────────────────────────────────────
#  PASO 2: VERIFICAR EN LA DB
# ──────────────────────────────────────────────────
def paso_verificar(db_path):
    print(f"\n=== [3/4] VERIFICANDO TABLAS EN: {db_path} ===")
    con = sqlite3.connect(db_path)

    n_tokens = con.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
    n_nodos  = con.execute("SELECT COUNT(*) FROM nodos").fetchone()[0]
    meta     = dict(con.execute("SELECT clave, valor FROM meta").fetchall())

    print(f"  tabla `tokens`: {n_tokens} filas")
    print(f"  tabla `nodos`:  {n_nodos} filas")
    print(f"  tabla `meta`:   motor={meta.get('motor')}, dim={meta.get('dim')}, "
          f"actualizado={meta.get('actualizado_en')}")

    # Verificar que los vectores son válidos (primer nodo)
    row = con.execute("SELECT concepto, vector FROM nodos LIMIT 1").fetchone()
    if row:
        import numpy as np
        nombre, blob = row
        vec = np.frombuffer(blob, dtype='float32')
        print(f"  ✔ Vector muestra: nodo='{nombre}' | dim={len(vec)} | norma={float(np.linalg.norm(vec)):.4f}")
    else:
        print("  ✘ No hay vectores en la tabla `nodos`")

    con.close()


# ──────────────────────────────────────────────────
#  PASO 3: QUICK SEARCH TEST
# ──────────────────────────────────────────────────
def paso_test_busqueda(db_path):
    print(f"\n=== [4/4] PRUEBA RÁPIDA DE BÚSQUEDA ===")
    import numpy as np
    con = sqlite3.connect(db_path)

    # Cargar todos los vectores de nodos
    rows = con.execute("SELECT concepto, vector FROM nodos").fetchall()
    nodos = {c: np.frombuffer(v, dtype='float32') for c, v in rows}

    def buscar(query, top=5):
        toks = _tokenizar(query)
        if not toks:
            return []
        # Cargar vectores de tokens para la query
        tok_rows = con.execute(
            f"SELECT token, vector FROM tokens WHERE token IN ({','.join('?'*len(toks))})", toks
        ).fetchall()
        if not tok_rows:
            return []
        tok_vecs = {t: np.frombuffer(v, dtype='float32') for t, v in tok_rows}
        q_vec = np.mean([tok_vecs[t] for t in toks if t in tok_vecs], axis=0)
        norm_q = np.linalg.norm(q_vec)
        if norm_q < 1e-8:
            return []
        scores = []
        for c, v in nodos.items():
            norm_v = np.linalg.norm(v)
            if norm_v < 1e-8:
                continue
            scores.append((c, float(np.dot(q_vec, v) / (norm_q * norm_v))))
        return sorted(scores, key=lambda x: -x[1])[:top]

    test_queries = [
        ("perfil", "dennys-identidad-profunda"),
        ("biorag", "auto-consulta-permanente-biorag"),
        ("identidad", "por_que_me_molesta_decir_soy_una_maquina"),
        ("paráfrasis vectores búsqueda", "arquitectura_dos_niveles_biorag"),
    ]

    for q, expected in test_queries:
        results = buscar(q)
        ranks = [i+1 for i, (c, _) in enumerate(results) if c == expected]
        rank = ranks[0] if ranks else '?'
        top_name = results[0][0] if results else 'N/A'
        estado = "✔" if rank != '?' and rank <= 5 else "✘"
        print(f"  [{estado}] '{q}' → #{rank} (esperado: {expected})")
        print(f"        Top1: {top_name}")

    con.close()


# ──────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("  BIORAG v26.0 — DESPLIEGUE DEL MOTOR PPMI+SVD+RETROFIT")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"ERROR: DB no encontrada en {DB_PATH}")
        sys.exit(1)

    paso_copiar_modulos()
    n_nodos, V, dim = paso_reindexar(DB_PATH)
    paso_verificar(DB_PATH)
    paso_test_busqueda(DB_PATH)

    print("\n" + "=" * 60)
    print(f"  ✔ DESPLIEGUE COMPLETADO")
    print(f"  ✔ {n_nodos} nodos vectorizados | vocab={V} | dim={dim}")
    print(f"  ✔ Tablas: tokens, nodos, meta → en {DB_PATH.name}")
    print("=" * 60)
