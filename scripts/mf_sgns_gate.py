#!/usr/bin/env python3
"""mf_sgns_gate.py — Gate de señal MF-SGNS sobre los 35 fallos (Plan 2, Fase 1)

Pregunta que responde (diseño, NO descripción):
¿El score de puente MF-SGNS (loss logística ponderada por co-ocurrencia real N_ij,
  w·c = PMI − log k) separa al nodo esperado del resto del pool, caso por caso,
  en los 35 fallos top-5 re-verificados (21 por_tema + 14 sinonimo)?

Señal por candidato del pool:
  score_sgns(Q, C) = promedio sobre q ∈ tokens(Q) de max_{c ∈ tokens(C)} N_qc · σ(PMI(q,c) − log k)

  PMI(q,c) = log(N · N_qc / (N_q · N_c))
  σ(x)     = 1 / (1 + e^{-x})
  k        = negativos de la loss SGNS (hiperparámetro, default 5)

Variantes de ponderación (las que el sweep Fase 2 barrerá):
  P1 = σ(PMI − log k)                      (sin peso por N_qc)
  P2 = N_qc · σ(PMI − log k)               (ponderada por co-ocurrencia real)
  P3 = score_pmi_nodo (referencia actual de BioRAG, ya existente)

Criterios de no-arranque (Plan 2, Sección 5):
  - por_tema:  < 10/21 expected en top-5 por score_sgns
  - sinonimo:  < 6/14 expected en top-5 por score_sgns
  → refutación temprana, no se gasta el sweep.

Salida: scripts/mf_sgns_gate.json

Uso:
  python3 scripts/mf_sgns_gate.py [--snapshot RUTA] [--k 5]
"""
import argparse
import json
import math
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pmi_semantico import _construir_corpus, _tokenizar

DEFAULT_SNAPSHOT = ROOT / 'snapshots' / 'word2vec_pre_fase0_20260806_235239.db'
DEFAULT_POOL = ROOT / 'scripts' / 'experimento_rr_pool.json'
SALIDA = ROOT / 'scripts' / 'mf_sgns_gate.json'

FALLOS_POR_TEMA = ['0497', '0534', '0540', '0558', '0571', '0583', '0589', '0634',
                   '0640', '0652', '0670', '0706', '0730', '0736', '0765', '0783',
                   '0795', '0801', '0807', '0824', '0830']
FALLOS_SINONIMO = ['0514', '0520', '0532', '0563', '0625', '0734', '0740', '0757',
                   '0775', '0799', '0811', '0822', '0828', '0878']
FALLOS_ID = set(FALLOS_POR_TEMA + FALLOS_SINONIMO)


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


class MF_SGNS:
    """Puente distribucional MF-SGNS sobre la matriz de co-ocurrencia real.

    count-based distributional semantics (HAL) con la loss logística de SGNS,
    computado al vuelo sobre co_freq/doc_freq/total del snapshot.
    """

    def __init__(self, cursor, k: int = 5):
        self.co_freq, self.doc_freq, self.total = _construir_corpus(cursor)
        self.k = k
        self._cache_par: dict = {}

    def _score_par(self, q: str, c: str) -> float:
        """score_sgns de un par de tokens: N_qc · σ(PMI(q,c) − log k)."""
        key = (q, c) if q <= c else (c, q)
        if key in self._cache_par:
            return self._cache_par[key]
        n_qc = self.co_freq.get(key, 0)
        n_q = self.doc_freq.get(q, 0)
        n_c = self.doc_freq.get(c, 0)
        N = max(1, self.total)
        if n_qc <= 0 or n_q <= 0 or n_c <= 0:
            self._cache_par[key] = 0.0
            return 0.0
        pmi = math.log((N * n_qc) / (n_q * n_c))
        shift = pmi - math.log(max(1, self.k))
        raw = _sigmoid(shift)
        self._cache_par[key] = (raw, n_qc)
        return (raw, n_qc)

    def score_nodo(self, tokens_q: list, tokens_c: list, peso: bool = True) -> float:
        """Promedio sobre tokens del query del mejor puente contra tokens del candidato."""
        if not tokens_q or not tokens_c:
            return 0.0
        suma = 0.0
        for q in tokens_q:
            best = 0.0
            for c in tokens_c:
                res = self._score_par(q, c)
                if res == 0.0:
                    continue
                raw, n_qc = res
                s = (n_qc * raw) if peso else raw
                if s > best:
                    best = s
            suma += best
        return suma / max(1, len(tokens_q))


def _cargar_casos(pool_path: str) -> list:
    casos = json.loads(Path(pool_path).read_text(encoding='utf-8'))
    return [c for c in casos if c['id'] in FALLOS_ID]


def _rank_expected(pool: list, scores: list, expected: str) -> int:
    orden = sorted(range(len(pool)), key=lambda i: (-scores[i], i))
    for pos, idx in enumerate(orden, start=1):
        if pool[idx]['concepto'] == expected:
            return pos
    return len(pool) + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--k', type=int, default=5, help='negativos de la loss SGNS')
    parser.add_argument('--pool', default=str(DEFAULT_POOL))
    args = parser.parse_args()

    t0 = time.time()
    con = sqlite3.connect(args.snapshot)
    cursor = con.cursor()

    # Matriz de co-ocurrencia real del snapshot
    mf = MF_SGNS(cursor, k=args.k)

    casos = _cargar_casos(args.pool)
    detalle = []
    resumen = {'por_tema': {'n': 0, 'top1': {k: 0 for k in ('P1', 'P2', 'P3')},
                            'top5': {k: 0 for k in ('P1', 'P2', 'P3')}},
               'sinonimo': {'n': 0, 'top1': {k: 0 for k in ('P1', 'P2', 'P3')},
                            'top5': {k: 0 for k in ('P1', 'P2', 'P3')}}}

    # Pre-tokenizar todos los candidatos del pool (cache por concepto)
    tokens_cache: dict = {}
    for caso in casos:
        for cand in caso['pool']:
            nom = cand['concepto']
            if nom not in tokens_cache:
                tokens_cache[nom] = _tokenizar(nom)

    for caso in casos:
        cat = caso['categoria']
        expected = caso['expected']
        query = caso['query']
        tokens_q = _tokenizar(query)
        pool = caso['pool']

        s_p1 = [mf.score_nodo(tokens_q, tokens_cache[c['concepto']], peso=False) for c in pool]
        s_p2 = [mf.score_nodo(tokens_q, tokens_cache[c['concepto']], peso=True) for c in pool]

        # Referencia: score_pmi_nodo existente (sin puente)
        from core.pmi_semantico import score_pmi_nodo
        s_p3 = [score_pmi_nodo(cursor, query, c['concepto']) for c in pool]

        r_p1 = _rank_expected(pool, s_p1, expected)
        r_p2 = _rank_expected(pool, s_p2, expected)
        r_p3 = _rank_expected(pool, s_p3, expected)

        cat_key = 'por_tema' if cat == 'por_tema' else 'sinonimo'
        resumen[cat_key]['n'] += 1
        for nombre, r in (('P1', r_p1), ('P2', r_p2), ('P3', r_p3)):
            if r == 1:
                resumen[cat_key]['top1'][nombre] += 1
            if r <= 5:
                resumen[cat_key]['top5'][nombre] += 1

        detalle.append({
            'id': caso['id'], 'categoria': cat, 'expected': expected, 'query': query,
            'n_pool': len(pool),
            'rank_sgns_P1': r_p1, 'rank_sgns_P2': r_p2, 'rank_pmi_nodo': r_p3,
        })

    con.close()

    # Criterios de no-arranque
    pt_top5 = resumen['por_tema']['top5']['P2']
    sn_top5 = resumen['sinonimo']['top5']['P2']
    gate_pt = 'PASA' if pt_top5 >= 10 else 'FALLA'
    gate_sn = 'PASA' if sn_top5 >= 6 else 'FALLA'

    salida = {
        'fase': '1',
        'descripcion': 'Gate de señal MF-SGNS sobre los 35 fallos (Plan 2). '
                       'score_sgns = promedio sobre tokens del query de max N_qc·σ(PMI−log k). '
                       'P1 sin peso, P2 ponderada por N_qc, P3 = score_pmi_nodo actual.',
        'snapshot': str(args.snapshot),
        'k': args.k,
        'n_fallos': len(casos),
        'resumen': resumen,
        'criterios_no_arranque': {
            'por_tema_esperado_top5_P2': {'min': 10, 'obtenido': pt_top5, 'veredicto': gate_pt},
            'sinonimo_esperado_top5_P2': {'min': 6, 'obtenido': sn_top5, 'veredicto': gate_sn},
        },
        'detalle': detalle,
        'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
        'segundos': round(time.time() - t0, 1),
    }
    Path(SALIDA).write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[OK] Gate MF-SGNS → {SALIDA}")
    print(f"     por_tema top5 P2: {pt_top5}/21 ({gate_pt}) | sinonimo top5 P2: {sn_top5}/14 ({gate_sn})")
    print(f"     {len(casos)} fallos, {round(time.time()-t0,1)}s")


if __name__ == '__main__':
    main()
