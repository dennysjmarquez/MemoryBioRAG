"""
word2vec_vectorizador.py — Fase 1: Vectores de contexto HDC por término
=======================================================================
Construye los vectores de contexto distribucional por término sobre el
snapshot de Fase 0, usando el sustrato HDC de core/sdm.py (multi-proyección
por hash md5 con seeds, sin embeddings ni dependencias nuevas).

El vector de contexto V(T) de un término T es la superposición de las
proyecciones de los tokens con los que T co-ocurre. Sigue la hipótesis
distribucional ("lo similar aparece en contextos similares") materializada
en el sustrato simbólico de BioRAG.

DISEÑO (v2 — corrección de saturación):
  - Espacio de contexto amplio (SDM_BITS_CONTEXTO=8192) para que el Jaccard
    discrimine. Con 2048 bits y OR binario, la densidad llegaba a 0.96
    (saturación) -> todo par tenía similitud ~1.0 -> señal indistinguible.
  - PONDERACIÓN POR FRECUENCIA: cada token co-ocurrente U activa
    k = clamp(round(16 * co_freq(U) / max_co_freq), 1, 16) proyecciones.
    Más co-ocurrencia = más bits compartidos = más peso en la similitud.
    Es count-based word2vec en HDC (la frecuencia NO se pierde en el OR).
  - Cap top-K co-ocurrentes por término (los más representativos), igual
    que el cap de 50 tokens de generar_vector_sdm.

Ventanas de co-ocurrencia (a barrer en Fase 2):
  - W0    : contexto = tokens que co-ocurren con T en el MISMO nodo
            (contexto léxico, mismo criterio que pmi_semantico).
  - W1    : contexto = tokens de los VECINOS SINÁPTICOS (1-hop) de los nodos
            donde T aparece (contexto estructural-distribucional, "la red
            define el contexto, no solo el texto").
  - W0+W1 : OR(W0, W1) — se deriva en calibración/sweep (no se duplica).

Filtros de corpus (mismo criterio que pmi_semantico): stems (core/stemmer_es),
stopwords fuera, frecuencia de documento >= UMBRAL_FREQ_MINIMA (3).

Salida: scripts/word2vec_vectores.json
  - meta       : snapshot usado, conteos, configuración.
  - frecuencias: stem -> frecuencia de documento.
  - vectores   : {ventana: {stem: base64(bytes)}}  (solo W0 y W1).

Uso:
  python3 scripts/word2vec_vectorizador.py [--snapshot RUTA] [--freq-min N]
                                           [--top-k N] [--bits N]

Determinista: misma entrada -> misma salida (hash md5 con seeds, sin azar).
"""

import argparse
import base64
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.sdm import _hash_token_a_bit
from core.pmi_semantico import UMBRAL_FREQ_MINIMA, _tokenizar

# Ruta por defecto: snapshot de Fase 0 (existe localmente, en .gitignore)
DEFAULT_SNAPSHOT = ROOT / 'snapshots' / 'word2vec_pre_fase0_20260806_235239.db'
SALIDA = ROOT / 'scripts' / 'word2vec_vectores.json'

# Espacio de contexto (bits). 8192 = 1KB/vector. Configurable via CLI/env.
SDM_BITS_CONTEXTO = int(os.environ.get('BIORAG_W2V_BITS', '8192'))
# Máx. proyecciones por token co-ocurrente (ponderación por frecuencia)
MAX_PROYECCIONES = 16
# Cap de co-ocurrentes por término (los más frecuentes)
TOP_K_DEFAULT = 100


def _bitset_a_bytes(bits: set, n_bits: int) -> bytes:
    """Convierte un set de posiciones de bit a bytes (big-endian)."""
    out = bytearray((n_bits + 7) // 8)
    for pos in bits:
        if 0 <= pos < n_bits:
            out[pos // 8] |= 1 << (7 - (pos % 8))
    return bytes(out)


def _posiciones_token(token: str, k: int, n_bits: int) -> set:
    """Posiciones de bit de un token con k proyecciones independientes."""
    return {_hash_token_a_bit(token, 0, n_bits, seed=s) for s in range(k)}


def _cargar_nodos(ruta_snapshot: str) -> dict:
    """Carga nodos activos del snapshot: concepto -> set de stems."""
    con = sqlite3.connect(ruta_snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT concepto, contenido, sinonimos FROM largo_plazo WHERE estado = 'activo'"
    )
    nodos_stems: dict = {}
    for row in cur.fetchall():
        texto = f"{row['concepto']} {row['contenido'] or ''} {row['sinonimos'] or ''}"
        stems = set(_tokenizar(texto))
        if len(stems) < 2:
            continue
        nodos_stems[row['concepto']] = stems
    con.close()
    return nodos_stems


def _cargar_vecinos(ruta_snapshot: str) -> dict:
    """Carga el grafo 1-hop: concepto -> set de vecinos sinápticos (todas las sinapsis)."""
    con = sqlite3.connect(ruta_snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT origen, destino FROM sinapsis")
    vecinos: dict = defaultdict(set)
    for row in cur.fetchall():
        a, b = row['origen'], row['destino']
        vecinos[a].add(b)
        vecinos[b].add(a)
    con.close()
    return dict(vecinos)


def _ventana_contexto(token, nodos_token, nodos_stems, vecinos, vocabulario, incluir_vecinos):
    """Counter de co-ocurrentes de `token` (ponderado por nº de nodos compartidos).

    incluir_vecinos=False -> W0 (solo el propio nodo).
    incluir_vecinos=True  -> W1 (propio nodo + vecinos sinápticos 1-hop).
    """
    co: Counter = Counter()
    for nodo in nodos_token:
        # Propio nodo (W0 y W1 lo incluyen — W1 añade la red encima)
        for u in nodos_stems[nodo]:
            if u != token and u in vocabulario:
                co[u] += 1
        if incluir_vecinos:
            for v in vecinos.get(nodo, ()):
                if v not in nodos_stems:
                    continue
                for u in nodos_stems[v]:
                    if u != token and u in vocabulario:
                        co[u] += 1
    return co


def _vector_desde_co(co: Counter, top_k: int, n_bits: int) -> bytes:
    """Convierte un Counter de co-ocurrencias en vector de contexto HDC."""
    if not co:
        return bytes((n_bits + 7) // 8)
    top = co.most_common(top_k)
    max_freq = top[0][1]
    bits: set = set()
    for u, freq in top:
        k = max(1, round(MAX_PROYECCIONES * freq / max_freq))
        bits |= _posiciones_token(u, k, n_bits)
    return _bitset_a_bytes(bits, n_bits)


def main():
    parser = argparse.ArgumentParser(description='Vectores de contexto HDC por término (Fase 1)')
    parser.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--freq-min', type=int, default=UMBRAL_FREQ_MINIMA)
    parser.add_argument('--top-k', type=int, default=TOP_K_DEFAULT)
    parser.add_argument('--bits', type=int, default=SDM_BITS_CONTEXTO)
    parser.add_argument('--salida', default=str(SALIDA))
    args = parser.parse_args()

    n_bits = args.bits
    t0 = time.time()
    if not os.path.exists(args.snapshot):
        sys.exit(f"[ERROR] Snapshot no encontrado: {args.snapshot}")

    nodos_stems = _cargar_nodos(args.snapshot)
    print(f"[1/5] Nodos activos tokenizados: {len(nodos_stems)} ({time.time()-t0:.1f}s)")

    stem_nodos: dict = defaultdict(set)
    for concepto, stems in nodos_stems.items():
        for s in stems:
            stem_nodos[s].add(concepto)

    vocabulario = {s for s, nodos in stem_nodos.items() if len(nodos) >= args.freq_min}
    print(f"[2/5] Vocabulario (freq>={args.freq_min}): {len(vocabulario)} stems")

    vecinos = _cargar_vecinos(args.snapshot)
    print(f"[3/5] Grafo sináptico cargado: {len(vecinos)} nodos con vecinos")

    vectores = {'W0': {}, 'W1': {}}
    for i, token in enumerate(sorted(vocabulario), 1):
        nodos_token = stem_nodos[token]
        co_w0 = _ventana_contexto(token, nodos_token, nodos_stems, vecinos, vocabulario, False)
        co_w1 = _ventana_contexto(token, nodos_token, nodos_stems, vecinos, vocabulario, True)
        vectores['W0'][token] = base64.b64encode(_vector_desde_co(co_w0, args.top_k, n_bits)).decode()
        vectores['W1'][token] = base64.b64encode(_vector_desde_co(co_w1, args.top_k, n_bits)).decode()
        if i % 500 == 0:
            print(f"    ... {i}/{len(vocabulario)} términos ({time.time()-t0:.1f}s)")

    for ventana in ('W0', 'W1'):
        densidades = []
        for v in vectores[ventana].values():
            data = base64.b64decode(v)
            n_activos = sum(bit_count for byte in data for bit_count in _bit_counts(byte))
            densidades.append(n_activos / n_bits)
        print(f"[4/5] Densidad promedio {ventana}: {sum(densidades)/max(1,len(densidades)):.4f}")

    salida = {
        'meta': {
            'script': 'word2vec_vectorizador.py',
            'version_diseno': 'v2 (espacio amplio + ponderación por frecuencia)',
            'snapshot': args.snapshot,
            'nodos_activos': len(nodos_stems),
            'terminos_con_vector': len(vocabulario),
            'freq_min': args.freq_min,
            'top_k': args.top_k,
            'sdm_bits_contexto': SDM_BITS_CONTEXTO,
            'max_proyecciones_por_token': MAX_PROYECCIONES,
            'ventanas': ['W0', 'W1', 'W0+W1 (OR derivado)'],
            'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
        },
        'frecuencias': {s: len(stem_nodos[s]) for s in sorted(vocabulario)},
        'vectores': vectores,
    }

    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False)
    print(f"[5/5] Salvado: {args.salida} ({time.time()-t0:.1f}s)")


def _bit_counts(byte):
    """Itera sobre los bits activos de un byte (para conteo de densidad)."""
    return [1 for i in range(8) if byte & (1 << (7 - i))]


if __name__ == '__main__':
    main()
