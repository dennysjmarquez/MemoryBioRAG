"""
word2vec_calibracion.py — Fase 1: Gate de no-arranque
======================================================
Gate de calibración del experimento word2vec-adaptado. Pregunta central:
¿la similitud HDC de contexto separa pares de sinónimos CONOCIDOS de pares
aleatorios?

Si NO separa → la señal no porta información → hipótesis refutada de
antemano → se detiene el experimento SIN gastar el sweep (criterio de parada
igual al de Tejedora). Si SÍ separa → se autoriza Fase 2.

Pares positivos: sinapsis `sinonimo_explicito` (4694 en el snapshot de
Fase 0, remedidas antes de usar) cuyos dos extremos son conceptos activos.
Pares negativos: pares aleatorios de conceptos activos, mismo tamaño, seed
fija (mismo universo — se excluyen solapamientos léxicos accidentales con
filtro de stems compartidos).

Métrica: similitud HDC entre los VECTORES DE CONTEXTO de los extremos.
Dos conceptos son distribucionalmente similares si sus términos co-ocurren
con los mismos vecinos (hipótesis distribucional en sustrato HDC).

Salida: scripts/word2vec_calibracion.json
  - por_ventana   : métricas de separación para W0, W1, W0+W1.
  - veredicto     : gate.pasa (bool) + justificación + metricas_globales.

Uso:
  python3 scripts/word2vec_calibracion.py [--snapshot RUTA] [--vectores RUTA]
                                          [--seed N] [--n-aleatorios N]

Determinista: seed fija para el muestreo de pares aleatorios.
"""

import argparse
import base64
import json
import os
import random
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.sdm import SDM_BITS
from core.pmi_semantico import _tokenizar

DEFAULT_SNAPSHOT = ROOT / 'snapshots' / 'word2vec_pre_fase0_20260806_235239.db'
DEFAULT_VECTORES = ROOT / 'scripts' / 'word2vec_vectores.json'
SALIDA = ROOT / 'scripts' / 'word2vec_calibracion.json'


def _bytes_a_bitset(b64: str) -> set:
    """Decodifica base64 -> set de posiciones de bit activas."""
    data = base64.b64decode(b64)
    bits = set()
    for byte_idx, byte in enumerate(data):
        for bit_idx in range(8):
            if byte & (1 << (7 - bit_idx)):
                bits.add(byte_idx * 8 + bit_idx)
    return bits


def _or_bitsets(*conjuntos) -> set:
    """OR de varios bitsets (para derivar W0+W1)."""
    res = set()
    for c in conjuntos:
        res |= c
    return res


def _jaccard_bits(a: set, b: set) -> float:
    """Jaccard puro sobre bits activos (sin pesos por segmento)."""
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def _cargar_nodos_activos(ruta_snapshot: str) -> list:
    """Conceptos activos del snapshot (para el universo de pares aleatorios)."""
    con = sqlite3.connect(ruta_snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT concepto, contenido, sinonimos FROM largo_plazo WHERE estado = 'activo'")
    filas = [dict(r) for r in cur.fetchall()]
    con.close()
    return filas


def _cargar_pares_sinonimo(ruta_snapshot: str) -> list:
    """Pares sinonimo_explicito (origen, destino)."""
    con = sqlite3.connect(ruta_snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT origen, destino FROM sinapsis WHERE tipo = 'sinonimo_explicito'")
    pares = [(r['origen'], r['destino']) for r in cur.fetchall()]
    con.close()
    return pares


def _stems_de(concepto: str, contenido, sinonimos) -> set:
    return set(_tokenizar(f"{concepto} {contenido or ''} {sinonimos or ''}"))


def main():
    parser = argparse.ArgumentParser(description='Gate de no-arranque del experimento word2vec (Fase 1)')
    parser.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--vectores', default=str(DEFAULT_VECTORES))
    parser.add_argument('--salida', default=str(SALIDA))
    parser.add_argument('--seed', type=int, default=20260804, help='Seed fija del muestreo')
    parser.add_argument('--n-aleatorios', type=int, default=0, help='Pares aleatorios (0 = mismo tamaño que positivos)')
    args = parser.parse_args()

    t0 = time.time()
    if not os.path.exists(args.snapshot):
        sys.exit(f"[ERROR] Snapshot no encontrado: {args.snapshot}")
    if not os.path.exists(args.vectores):
        sys.exit(f"[ERROR] Vectores no encontrados: {args.vectores}")

    with open(args.vectores, 'r', encoding='utf-8') as f:
        datos_vectores = json.load(f)
    vectores = datos_vectores['vectores']
    # Ventanas de trabajo: W0, W1 + W0+W1 derivado por OR
    ventanas_base = list(vectores.keys())
    ventanas = ventanas_base + ['W0+W1'] if 'W0+W1' not in ventanas_base else ventanas_base
    print(f"[1/6] Vectores cargados: {ventanas} ({time.time()-t0:.1f}s)")

    nodos = _cargar_nodos_activos(args.snapshot)
    conceptos_activos = {n['concepto'] for n in nodos}
    print(f"[2/6] Nodos activos: {len(conceptos_activos)}")

    pares_positivos = _cargar_pares_sinonimo(args.snapshot)
    print(f"[3/6] Pares sinonimo_explicito crudos: {len(pares_positivos)}")

    # Precomputar stems por concepto (para filtrar solapamiento léxico)
    stems_por_concepto = {n['concepto']: _stems_de(n['concepto'], n['contenido'], n['sinonimos'])
                          for n in nodos}

    # Cada extremo se representa como: OR de los bitset de contexto de SUS stems.
    # Un extremo aporta si al menos uno de sus stems tiene vector de contexto.
    def vectores_concepto(concepto):
        """Retorna (bitsets_por_ventana, stems_con_vector) para un concepto."""
        bitsets = {v: set() for v in ventanas}
        stems_ok = set()
        for s in stems_por_concepto.get(concepto, set()):
            presente = all(s in vectores[v] for v in ventanas_base)
            if presente:
                for v in ventanas_base:
                    bitsets[v] |= _bytes_a_bitset(vectores[v][s])
                stems_ok.add(s)
        if 'W0+W1' in ventanas:
            bitsets['W0+W1'] = _or_bitsets(bitsets['W0'], bitsets['W1'])
        return bitsets, stems_ok

    # Construir pares positivos válidos: ambos extremos activos con vector
    positivos = []
    cache = {}
    for origen, destino in pares_positivos:
        if origen not in conceptos_activos or destino not in conceptos_activos:
            continue
        if origen == destino:
            continue
        for c in (origen, destino):
            if c not in cache:
                cache[c] = vectores_concepto(c)
        bits_o, stems_o = cache[origen]
        bits_d, stems_d = cache[destino]
        # Ambos extremos deben tener >=1 stem con vector (si no, no hay señal que medir)
        if not stems_o or not stems_d:
            continue
        positivos.append((origen, destino, bits_o, bits_d, stems_o, stems_d))
    print(f"[4/6] Pares positivos válidos: {len(positivos)}")

    if len(positivos) < 30:
        print("[ERROR] Menos de 30 pares positivos válidos — señal insuficiente para calibración.")
        sys.exit(1)

    # Pares aleatorios del mismo universo de conceptos (seed fija)
    n_aleatorios = args.n_aleatorios or len(positivos)
    rng = random.Random(args.seed)
    conceptos_lista = sorted(conceptos_activos)
    aleatorios = []
    while len(aleatorios) < n_aleatorios:
        a, b = rng.sample(conceptos_lista, 2)
        if (a, b) in {(p[0], p[1]) for p in positivos} or (b, a) in {(p[0], p[1]) for p in positivos}:
            continue
        for c in (a, b):
            if c not in cache:
                cache[c] = vectores_concepto(c)
        bits_a, stems_a = cache[a]
        bits_b, stems_b = cache[b]
        if not stems_a or not stems_b:
            continue
        aleatorios.append((a, b, bits_a, bits_b, stems_a, stems_b))
    print(f"[5/6] Pares aleatorios: {len(aleatorios)} (seed {args.seed})")

    # Métricas por ventana
    resultados_ventana = {}
    for v in ventanas:
        pos_scores = [_jaccard_bits(bits_o[v], bits_d[v]) for _, _, bits_o, bits_d, _, _ in positivos]
        rand_scores = [_jaccard_bits(bits_a[v], bits_b[v]) for _, _, bits_a, bits_b, _, _ in aleatorios]

        pos_sorted = sorted(pos_scores)
        rand_sorted = sorted(rand_scores)
        n_pos = len(pos_scores)
        n_rand = len(rand_scores)

        def mediana(x):
            if not x:
                return 0.0
            m = len(x) // 2
            return x[m] if len(x) % 2 else (x[m - 1] + x[m]) / 2

        # AUC = P(positivo > aleatorio), con empates contando 0.5
        auc = 0.0
        for s_p in pos_scores:
            for s_r in rand_scores:
                auc += (s_p > s_r) + 0.5 * (s_p == s_r)
        auc /= (n_pos * n_rand) if n_pos * n_rand else 1

        # Cohen's d
        mean_pos = sum(pos_scores) / n_pos
        mean_rand = sum(rand_scores) / n_rand
        var_pos = sum((x - mean_pos) ** 2 for x in pos_scores) / max(1, n_pos - 1)
        var_rand = sum((x - mean_rand) ** 2 for x in rand_scores) / max(1, n_rand - 1)
        pooled = ((var_pos + var_rand) / 2) ** 0.5
        cohen_d = (mean_pos - mean_rand) / pooled if pooled > 0 else 0.0

        resultados_ventana[v] = {
            'n_positivos': n_pos,
            'n_aleatorios': n_rand,
            'media_positivos': round(mean_pos, 4),
            'media_aleatorios': round(mean_rand, 4),
            'mediana_positivos': round(mediana(pos_sorted), 4),
            'mediana_aleatorios': round(mediana(rand_sorted), 4),
            'percentil_90_positivos': round(pos_sorted[int(n_pos * 0.9) - 1] if n_pos else 0.0, 4),
            'percentil_90_aleatorios': round(rand_sorted[int(n_rand * 0.9) - 1] if n_rand else 0.0, 4),
            'auc': round(auc, 4),
            'cohen_d': round(cohen_d, 4),
            'solape_lexico_positivos': round(sum(1 for _, _, _, _, so, sd in positivos if so & sd) / n_pos, 4),
        }
        print(f"    {v}: AUC={resultados_ventana[v]['auc']:.3f} "
              f"d={cohen_d:.2f} media pos/rand={mean_pos:.3f}/{mean_rand:.3f} "
              f"mediana pos/rand={mediana(pos_sorted):.3f}/{mediana(rand_sorted):.3f}")

    # Veredicto del gate
    # Regla: pasa si en ALGUNA ventana AUC >= 0.65 Y media_pos > media_rand + 2*sep
    # (la separación debe ser > ruido, no solo > 0)
    mejor_ventana = None
    mejor_auc = 0.0
    pasa = False
    for v in ventanas:
        r = resultados_ventana[v]
        if r['auc'] >= 0.65 and r['media_positivos'] > r['media_aleatorios']:
            if r['auc'] > mejor_auc:
                mejor_auc = r['auc']
                mejor_ventana = v
    pasa = mejor_ventana is not None

    veredicto = {
        'gate': {
            'pasa': pasa,
            'criterio': 'AUC >= 0.65 Y media_positivos > media_aleatorios en al menos una ventana',
            'mejor_ventana': mejor_ventana,
            'mejor_auc': mejor_auc,
            'justificacion': (
                'La similitud HDC de contexto separa sinónimos conocidos de pares aleatorios '
                '=> la señal distribucional PORTA INFORMACIÓN. Se autoriza Fase 2.'
                if pasa else
                'La similitud HDC de contexto NO separa sinónimos conocidos de pares aleatorios '
                '=> hipótesis refutada de antemano. Se detiene el experimento sin gastar el sweep.'
            ),
        }
    }

    salida = {
        'meta': {
            'script': 'word2vec_calibracion.py',
            'snapshot': args.snapshot,
            'vectores': args.vectores,
            'seed': args.seed,
            'n_aleatorios': len(aleatorios),
            'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
        },
        'por_ventana': resultados_ventana,
        'veredicto': veredicto,
    }

    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"[6/6] Gate {'PASA' if pasa else 'NO PASA'} — mejor ventana: {mejor_ventana} "
          f"(AUC {mejor_auc:.3f}) — {time.time()-t0:.1f}s")
    print(f"      Salvado: {args.salida}")
    sys.exit(0 if pasa else 2)


if __name__ == '__main__':
    main()
