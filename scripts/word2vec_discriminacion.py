#!/usr/bin/env python3
"""word2vec_discriminacion.py — Diagnóstico de discriminación del expected en los 35 fallos

Pregunta que responde (diseño, NO descripción): ¿qué señal separa al nodo esperado
del resto del pool, caso por caso, sobre los 35 fallos top-5 re-verificados
(21 por_tema + 14 sinonimo)?

Señales evaluadas por candidato del pool (para el caso):
  1. bridge_HDC_W0 / W1 / W0+W1 : promedio sobre tokens del query del mejor
     jaccard HDC de contexto contra los stems del candidato (misma forma que
     el sweep Fase 2, s/peso/umbral).
  2. sinonimo_explicito(dirigida): ¿el candidato tiene una sinapsis
     sinonimo_explicito con algún nodo que comparte tokens con el query?
  3. score_pmi_nodo               : el score PMI que produce hoy BioRAG.

Métricas por señal (por ventana si aplica):
  - rank_del_expected_por_señal  : posición del expected ordenando el pool por esa señal.
  - n_casos_donde_expected_top1  : casos donde el expected es el máximo de la señal.
  - n_casos_donde_expected_top5  : casos donde el expected está en el top-5 de la señal.
  - discriminacion (score top1 menos segundo mejor de la señal).

Salida: scripts/word2vec_discriminacion.json

Uso:
  python3 scripts/word2vec_discriminacion.py [--snapshot RUTA] [--vectores RUTA]
"""
import argparse
import base64
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pmi_semantico import _tokenizar, score_pmi_nodo

DEFAULT_SNAPSHOT = ROOT / 'snapshots' / 'word2vec_pre_fase0_20260806_235239.db'
DEFAULT_POOL = ROOT / 'scripts' / 'experimento_rr_pool.json'
DEFAULT_VECTORES = ROOT / 'scripts' / 'word2vec_vectores.json'
SALIDA = ROOT / 'scripts' / 'word2vec_discriminacion.json'

FALLOS_POR_TEMA = ['0497', '0534', '0540', '0558', '0571', '0583', '0589', '0634',
                   '0640', '0652', '0670', '0706', '0730', '0736', '0765', '0783',
                   '0795', '0801', '0807', '0824', '0830']
FALLOS_SINONIMO = ['0514', '0520', '0532', '0563', '0625', '0734', '0740', '0757',
                   '0775', '0799', '0811', '0822', '0828', '0878']
FALLOS_ID = set(FALLOS_POR_TEMA + FALLOS_SINONIMO)

VENTANAS = ['W0', 'W1', 'W0+W1']


def _bytes_a_bitset(b64: str) -> set:
    data = base64.b64decode(b64)
    bits = set()
    for byte_idx, byte in enumerate(data):
        for bit_idx in range(8):
            if byte & (1 << (7 - bit_idx)):
                bits.add(byte_idx * 8 + bit_idx)
    return bits


def _jaccard_bits(a: set, b: set) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _cargar_vectores(ruta_vectores: str) -> dict:
    with open(ruta_vectores, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    vectores = datos['vectores']
    bitsets = {v: {s: _bytes_a_bitset(b64) for s, b64 in vectores[v].items()}
               for v in vectores}
    bitsets['W0+W1'] = {s: bitsets['W0'][s] | bitsets['W1'][s]
                        for s in bitsets['W0']}
    return bitsets


def _cargar_stems_y_sinonimos(ruta_snapshot: str):
    """concepto -> (stems, lista_sinonimos_cadena)."""
    con = sqlite3.connect(ruta_snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT concepto, contenido, sinonimos FROM largo_plazo")
    out = {}
    for row in cur.fetchall():
        stems = set(_tokenizar(f"{row['concepto']} {row['contenido'] or ''} {row['sinonimos'] or ''}"))
        if stems:
            out[row['concepto']] = stems
    con.close()
    return out


def _cargar_sinapsis_sinonimo(ruta_snapshot: str) -> dict:
    """concepto -> set de conceptos con sinapsis sinonimo_explicito."""
    con = sqlite3.connect(ruta_snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT origen, destino FROM sinapsis WHERE tipo = 'sinonimo_explicito'")
    sinon = {}
    for row in cur.fetchall():
        a, b = row['origen'], row['destino']
        sinon.setdefault(a, set()).add(b)
        sinon.setdefault(b, set()).add(a)
    con.close()
    return sinon


def _bridge_score(stems_query, stems_cand, qbits, cand_stems):
    """Promedio sobre tokens del query del mejor jaccard HDC (forma sweep F2)."""
    if not qbits:
        return 0.0
    if not cand_stems:
        return 0.0
    total = 0.0
    n = 0
    for qt in stems_query:
        qb = qbits.get(qt)
        if qb is None:
            continue
        best = 0.0
        for cs in cand_stems:
            cb = qbits.get(cs)
            if cb is None:
                continue
            j = _jaccard_bits(qb, cb)
            if j > best:
                best = j
        total += best
        n += 1
    return total / n if n else 0.0


def main():
    parser = argparse.ArgumentParser(description='Diagnóstico de discriminación de señales (fallos)')
    parser.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--pool', default=str(DEFAULT_POOL))
    parser.add_argument('--vectores', default=str(DEFAULT_VECTORES))
    parser.add_argument('--salida', default=str(SALIDA))
    args = parser.parse_args()

    t0 = time.time()
    with open(args.pool, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    bitsets = _cargar_vectores(args.vectores)
    stems_por_concepto = _cargar_stems_y_sinonimos(args.snapshot)
    sinon = _cargar_sinapsis_sinonimo(args.snapshot)
    print(f"[1/4] Pool={len(pool)} | vectores={len(bitsets['W0'])} stems | sinonimo_explicito={sum(len(v) for v in sinon)} aristas ({time.time()-t0:.1f}s)")

    casos = [c for c in pool if c['id'] in FALLOS_ID]
    print(f"[2/4] Fallos analizados: {len(casos)} (21 por_tema + 14 sinonimo)")

    con = sqlite3.connect(args.snapshot)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    resumen = {
        'por_tema': {'n': 0, 'top1': {}, 'top5': {}},
        'sinonimo': {'n': 0, 'top1': {}, 'top5': {}},
    }
    detalle = []
    for caso in casos:
        exp = caso['expected']
        q_tokens = set(_tokenizar(caso['query']))
        exp_stems = stems_por_concepto.get(exp, set())
        exp_sin = sinon.get(exp, set())

        # Señales por candidato del pool
        row_por_cand = []
        for p in caso['pool']:
            cand = p['concepto']
            cs = stems_por_concepto.get(cand, set())
            s = {
                'concepto': cand,
                'score_base': p['score'],
                'pmi': score_pmi_nodo(cur, caso['query'], cand),
            }
            for v in VENTANAS:
                s[f'bridge_{v}'] = _bridge_score(q_tokens, cs, bitsets[v], cs)
            # señal dirigida sinonimo: ¿el candidato comparte sinonimo_explicito
            # con algún nodo cuyos stems tocan el query?
            s['sinonimo_dirigido'] = 0.0
            cand_sin = sinon.get(cand, set())
            for vecino in cand_sin:
                vstems = stems_por_concepto.get(vecino, set())
                if vstems & q_tokens:
                    s['sinonimo_dirigido'] = 1.0
                    break
            row_por_cand.append(s)

        cat = caso['categoria']
        r = resumen[cat]
        r['n'] += 1
        d = {'id': caso['id'], 'categoria': cat, 'expected': exp, 'query': caso['query']}

        for v in VENTANAS:
            orden = sorted(row_por_cand, key=lambda x: x[f'bridge_{v}'], reverse=True)
            ranked = [x['concepto'] for x in orden]
            if exp in ranked:
                rank = ranked.index(exp) + 1
                r['top1'][v] = r['top1'].get(v, 0) + (1 if rank == 1 else 0)
                r['top5'][v] = r['top5'].get(v, 0) + (1 if rank <= 5 else 0)
            else:
                rank = None
            d[f'rank_bridge_{v}'] = rank

        orden = sorted(row_por_cand, key=lambda x: x['sinonimo_dirigido'], reverse=True)
        ranked = [x['concepto'] for x in orden]
        r_rank = ranked.index(exp) + 1 if exp in ranked else None
        r['top1']['sinonimo_dirigido'] = r['top1'].get('sinonimo_dirigido', 0) + (1 if r_rank == 1 else 0)
        r['top5']['sinonimo_dirigido'] = r['top5'].get('sinonimo_dirigido', 0) + (1 if r_rank is not None and r_rank <= 5 else 0)
        d['rank_sinonimo_dirigido'] = r_rank

        d['n_pool'] = len(caso['pool'])
        detalle.append(d)

    con.close()
    print(f"[3/4] Cálculo de señales completado ({time.time()-t0:.1f}s)")

    salida = {
        'descripcion': 'Diagnóstico: rank del expected ordenando el pool por cada señal (1 = la señal lo pone primero).',
        'fallos': {'por_tema': FALLOS_POR_TEMA, 'sinonimo': FALLOS_SINONIMO, 'total': 35},
        'resumen': resumen,
        'detalle': detalle,
        'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"[4/4] Guardado: {args.salida} ({time.time()-t0:.1f}s)")


if __name__ == '__main__':
    main()
