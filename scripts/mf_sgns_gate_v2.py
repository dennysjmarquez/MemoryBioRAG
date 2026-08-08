#!/usr/bin/env python3
"""mf_sgns_gate_v2.py — Gate de señal MF-SGNS de SEGUNDO ORDEN (Plan 2, Fase 1, v2)

Por qué esta versión: el gate v1 medía co-ocurrencia DIRECTA query↔candidato
(score_sgns = N_qc·σ(PMI−log k)), que es nula por definición para sinonimos
léxicos puros ("perfil" nunca co-ocurre con "identidad-profunda"). Dio 0/14
en sinonimo — la señal correcta es de PRIMER orden y no puede resolver sinonimos.

La hipótesis distribucional de Firth es de SEGUNDO orden:
  "you shall know a word by the company it keeps"
  Dos palabras son intercambiables si su CONTEXTO (con quién co-ocurren) se parece.

Levy & Goldberg (2014): SGNS = factorización de la matriz M[i,j] = PMI(i,j) − log k.
La similitud entre dos targets i,j es el producto interno de sus filas en M —
contexto compartido ponderado, NO co-ocurrencia directa.

Señal de segundo orden (count-based, sin factorizar):
  vector_contexto(t) = fila de co-ocurrencia de t: {u: N_tu} para u≠t
  score_so(Q, C) = promedio sobre q ∈ tokens(Q) de max_{c ∈ tokens(C)}
                     coseno( vector_contexto(q), vector_contexto(c) )

Vectores de contexto ponderados por N_ij (frecuencia real de co-ocurrencia).
Esto es la diferencia con el HDC del Plan 1: HDC usaba bitsets binarios
(Hamming pierde magnitudes); aquí el coseno conserva la fuerza relativa.

Pregunta que responde: ¿el coseno ponderado de segundo orden separa al expected
del resto del pool en los 35 fallos? (en especial los 14 sinonimo, 0/14 en HDC)

Criterios de no-arranque (heredados del Plan 2):
  - por_tema: < 10/21 expected en top-5
  - sinonimo: < 6/14 expected en top-5
  → refutación temprana de la hipótesis distribucional sobre este corpus.

Salida: scripts/mf_sgns_gate_v2.json

Uso:
  python3 scripts/mf_sgns_gate_v2.py [--snapshot RUTA] [--peso PMI|NQ|BIN]
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
SALIDA = ROOT / 'scripts' / 'mf_sgns_gate_v2.json'

FALLOS_POR_TEMA = ['0497', '0534', '0540', '0558', '0571', '0583', '0589', '0634',
                   '0640', '0652', '0670', '0706', '0730', '0736', '0765', '0783',
                   '0795', '0801', '0807', '0824', '0830']
FALLOS_SINONIMO = ['0514', '0520', '0532', '0563', '0625', '0734', '0740', '0757',
                   '0775', '0799', '0811', '0822', '0828', '0878']
FALLOS_ID = set(FALLOS_POR_TEMA + FALLOS_SINONIMO)


class MF_SGNS_SO:
    """Puente distribucional MF-SGNS de segundo orden (coseno de vectores de contexto)."""

    def __init__(self, cursor, peso: str = 'NQ'):
        co_freq, doc_freq, total = _construir_corpus(cursor)
        self.co_freq = co_freq
        self.doc_freq = doc_freq
        self.total = max(1, total)
        self.peso = peso
        # vector de contexto por token: token → Counter{u: peso_tu}
        self.vectores = self._build_vectores()

    def _peso_par(self, tok: str, u: str, n_tu: int) -> float:
        if self.peso == 'BIN':
            return 1.0 if n_tu > 0 else 0.0
        if self.peso == 'NQ':
            return n_tu
        if self.peso == 'PMI':
            n_t = self.doc_freq.get(tok, 0)
            n_u = self.doc_freq.get(u, 0)
            if n_t <= 0 or n_u <= 0:
                return 0.0
            pmi = math.log((self.total * n_tu) / (n_t * n_u))
            return max(0.0, pmi)
        return n_tu

    def _build_vectores(self) -> dict:
        v: dict = {}
        for (a, b), n_ab in self.co_freq.items():
            pa = self._peso_par(a, b, n_ab)
            pb = self._peso_par(b, a, n_ab)
            v.setdefault(a, Counter())[b] += pa
            v.setdefault(b, Counter())[a] += pb
        return v

    def _coseno(self, a: Counter, b: Counter) -> float:
        if not a or not b:
            return 0.0
        dot = 0.0
        for tok, wa in a.items():
            wb = b.get(tok)
            if wb:
                dot += wa * wb
        if dot <= 0:
            return 0.0
        na = math.sqrt(sum(w * w for w in a.values()))
        nb = math.sqrt(sum(w * w for w in b.values()))
        if na <= 0 or nb <= 0:
            return 0.0
        return dot / (na * nb)

    def score_nodo(self, tokens_q: list, tokens_c: list) -> float:
        if not tokens_q or not tokens_c:
            return 0.0
        suma = 0.0
        for q in tokens_q:
            vq = self.vectores.get(q)
            if not vq:
                continue
            best = 0.0
            for c in tokens_c:
                vc = self.vectores.get(c)
                if not vc:
                    continue
                s = self._coseno(vq, vc)
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
    parser.add_argument('--peso', default='NQ', choices=['NQ', 'PMI', 'BIN'])
    parser.add_argument('--pool', default=str(DEFAULT_POOL))
    args = parser.parse_args()

    t0 = time.time()
    con = sqlite3.connect(args.snapshot)
    cursor = con.cursor()

    mf = MF_SGNS_SO(cursor, peso=args.peso)

    casos = _cargar_casos(args.pool)
    detalle = []
    resumen = {'por_tema': {'n': 0, 'top1': 0, 'top5': 0},
               'sinonimo': {'n': 0, 'top1': 0, 'top5': 0}}

    tokens_cache: dict = {}
    for caso in casos:
        for cand in caso['pool']:
            nom = cand['concepto']
            if nom not in tokens_cache:
                tokens_cache[nom] = _tokenizar(nom)

    for caso in casos:
        cat = caso['categoria']
        expected = caso['expected']
        tokens_q = _tokenizar(caso['query'])
        pool = caso['pool']
        scores = [mf.score_nodo(tokens_q, tokens_cache[c['concepto']]) for c in pool]
        r = _rank_expected(pool, scores, expected)

        cat_key = 'por_tema' if cat == 'por_tema' else 'sinonimo'
        resumen[cat_key]['n'] += 1
        if r == 1:
            resumen[cat_key]['top1'] += 1
        if r <= 5:
            resumen[cat_key]['top5'] += 1

        detalle.append({
            'id': caso['id'], 'categoria': cat, 'expected': expected, 'query': caso['query'],
            'n_pool': len(pool), 'rank_so': r,
        })

    con.close()

    pt_top5 = resumen['por_tema']['top5']
    sn_top5 = resumen['sinonimo']['top5']
    gate_pt = 'PASA' if pt_top5 >= 10 else 'FALLA'
    gate_sn = 'PASA' if sn_top5 >= 6 else 'FALLA'

    salida = {
        'fase': '1',
        'version': 'v2',
        'descripcion': 'Gate de señal MF-SGNS de SEGUNDO ORDEN: coseno ponderado entre '
                       'vectores de contexto (fila de co-ocurrencia). Levy-Goldberg 2014: '
                       'similitud = contexto compartido, no co-ocurrencia directa.',
        'snapshot': str(args.snapshot),
        'peso': args.peso,
        'n_fallos': len(casos),
        'resumen': resumen,
        'criterios_no_arranque': {
            'por_tema_esperado_top5': {'min': 10, 'obtenido': pt_top5, 'veredicto': gate_pt},
            'sinonimo_esperado_top5': {'min': 6, 'obtenido': sn_top5, 'veredicto': gate_sn},
        },
        'detalle': detalle,
        'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
        'segundos': round(time.time() - t0, 1),
    }
    Path(SALIDA).write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[OK] Gate v2 (segundo orden, peso={args.peso}) → {SALIDA}")
    print(f"     por_tema top5: {pt_top5}/21 ({gate_pt}) | sinonimo top5: {sn_top5}/14 ({gate_sn})")
    print(f"     {len(casos)} fallos, {round(time.time()-t0,1)}s")


if __name__ == '__main__':
    main()
