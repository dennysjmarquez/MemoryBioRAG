#!/usr/bin/env python3
"""word2vec_sweep.py — Fase 2: Barrido de parámetros del puente HDC condicional

Mide el delta de recall@5 por inyección del puente distribucional HDC sobre
la pipeline REAL de búsqueda, sobre mitad A del holdout (seed 20260804).

Metodología (fidelidad = pipeline real sobre snapshot, lección de fidelidad):
1. Copia del snapshot de Fase 0 por worker (sqlite3.backup) — MISMO snapshot
   que construyó los vectores (`word2vec_pre_fase0_20260806_235239.db`).
2. Por caso: estado del expected (dormido/activo) + `buscar_por_frase(limite=100)`
   real (misma pipeline que generó experimento_rr_pool.json, ignore_peso_sinaptico).
3. Trigger condicional (plan §4.2): el puente SOLO se aplica a candidatos que
   (a) NO están en top-5 base y (b) tienen score_pmi_nodo(query, candidato) == 0.
   A esos candidatos se les suma peso × bridge_score y se re-ordena el pool.
4. Barrido de configs (plan §4.3): ventana × top-K × peso × umbral.
   - Ventana: W1 (protagonista, dictamen del auditor), W0 (control), W0+W1.
   - Top-K puentes por token de query: 5, 10, 20.
   - Peso del puente: 0.10, 0.15, 0.20.
   - Umbral de similitud HDC: sin umbral (top-K relativo), >=0.50, >=0.60.

Bridge_score(query, candidato) [interpretación operativa de §4.3]:
  por cada token del query, el mejor candidato-token del concepto que esté
  dentro de los top-K más similares (HDC jaccard sobre vectores de contexto)
  y pase el umbral; promedio sobre los tokens del query (misma forma que
  score_pmi_nodo). Reemplaza el término NPMI (0.15) en el fallback.

Salida: scripts/word2vec_sweep_resultado.json
  - baseline : métricas SIN puente (re-corridas sobre el snapshot).
  - configs  : lista de configs con R@5 global / por_tema / sinonimo /
               rescate / regresión / FP_negativo.
  - mejor_config : mayor rescate sin regresión >1 caso por categoría.

Uso:
  python3 scripts/word2vec_sweep.py [--snapshot RUTA] [--workers N]
                                    [--mitad A|B] [--salida RUTA]
"""
import argparse
import base64
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from multiprocessing import Process, Queue
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.memory_store import SQLiteMemoryBioRAG
from core.pmi_semantico import _tokenizar, score_pmi_nodo

DEFAULT_SNAPSHOT = ROOT / 'snapshots' / 'word2vec_pre_fase0_20260806_235239.db'
DEFAULT_SPLIT = ROOT / 'scripts' / 'tejedora_split_50_50.json'
DEFAULT_VECTORES = ROOT / 'scripts' / 'word2vec_vectores.json'
DEFAULT_CASOS = ROOT / 'scripts' / 'casos_qa_baseline_v1.jsonl'
SALIDA = ROOT / 'scripts' / 'word2vec_sweep_resultado.json'

VENTANAS = ['W1', 'W0', 'W0+W1']   # W1 primero (dictamen del auditor)
TOPK_VALORES = [5, 10, 20]
PESO_VALORES = [0.10, 0.15, 0.20]
UMBRAL_VALORES = [None, 0.50, 0.60]  # None = sin umbral (top-K relativo)


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
    if union == 0:
        return 0.0
    return len(a & b) / union


def _cargar_vectores(ruta_vectores: str) -> dict:
    """bitsets[ventana][stem] -> set de posiciones. Deriva W0+W1 por OR."""
    with open(ruta_vectores, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    vectores = datos['vectores']
    bitsets = {v: {s: _bytes_a_bitset(b64) for s, b64 in vectores[v].items()}
               for v in vectores}
    bitsets['W0+W1'] = {s: bitsets['W0'][s] | bitsets['W1'][s]
                        for s in bitsets['W0']}
    return bitsets


def _cargar_stems_por_concepto(ruta_snapshot: str) -> dict:
    """concepto -> set de stems (concepto + contenido + sinonimos)."""
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


def _precomputar_tablas_sim(query_tokens_unicos, bitsets):
    """Por (ventana, token_query) -> {stem: (rank, sim)} del top-60, ordenado."""
    tablas = {}
    for ventana in VENTANAS:
        vb = bitsets[ventana]
        tablas[ventana] = {}
        for qt in query_tokens_unicos:
            qbits = vb.get(qt)
            if qbits is None:
                continue
            ranked = sorted(
                ((stem, _jaccard_bits(qbits, sbits)) for stem, sbits in vb.items()),
                key=lambda x: x[1], reverse=True)
            tablas[ventana][qt] = {s: (r, sim) for r, (s, sim) in
                                   enumerate(ranked[:60], 1) if sim > 0.0}
    return tablas


def _precomputar_bridges(casos, ventana, tabla, stems_por_concepto):
    """Por caso, lista de dicts por candidato: {qt: [(rank, sim)]}.

    Las intersecciones candidato-stems vs top-60 del query se calculan UNA vez
    por (ventana, caso) y se reutilizan en las 27 configs de esa ventana.
    """
    bridges = []
    for caso in casos:
        q_tokens = set(_tokenizar(caso['query']))
        cand_bridges = []
        for cand in caso['pool']:
            cand_stems = stems_por_concepto.get(cand['concepto'], set())
            if not cand_stems:
                cand_bridges.append({})
                continue
            por_qt = {}
            for qt in q_tokens:
                qt_map = tabla.get(qt)
                if qt_map:
                    entradas = []
                    for stem in cand_stems:
                        entrada = qt_map.get(stem)
                        if entrada is not None:
                            entradas.append(entrada)
                    por_qt[qt] = sorted(entradas, key=lambda x: x[1], reverse=True)
            cand_bridges.append(por_qt)
        bridges.append(cand_bridges)
    return bridges


def _bridge_score_desde_estructura(por_qt, top_k, umbral):
    """Promedio sobre tokens del query del mejor puente (estructura precomputada)."""
    if not por_qt:
        return 0.0
    suma = 0.0
    for qt, entradas in por_qt.items():
        best = 0.0
        for rank, sim in entradas:
            if rank > top_k:
                continue
            if umbral is not None and sim < umbral:
                continue
            if sim > best:
                best = sim
        suma += best
    return suma / max(1, len(por_qt))


def _merge_deep(casos_split, ruta_casos):
    """Fusiona el flag deep (casos originales) en los casos del split por id."""
    deep_map = {}
    if os.path.exists(ruta_casos):
        with open(ruta_casos, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    deep_map[c['id']] = c.get('deep', False)
    for c in casos_split:
        c['deep'] = deep_map.get(c['id'], False)
    return casos_split


def worker(worker_id, chunk, src_db, out_queue):
    temp_db = os.path.join(ROOT, "MemoryBioRAG_Data", f"_exp_w2v_{worker_id}.db")
    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    results = []
    for case in chunk:
        categoria = case['categoria']
        expected = case['expected']
        query = case['query']
        deep = case.get('deep', False)
        if categoria == 'dormido' and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
        profundidad = "profundo" if (deep or categoria == "dormido" or categoria == "negativo") else "activos"
        r, _ = db.buscar_por_frase(query, profundidad=profundidad, limite=100,
                                   ignore_peso_sinaptico=True)
        pool = [{'concepto': item[0], 'score': item[4]} for item in r]
        # Trigger condicional: score_pmi_nodo(query, candidato) == 0 (producción usa el nombre)
        pmi_zero = []
        for cand in pool:
            pmi = score_pmi_nodo(db.cursor, query, cand['concepto'])
            pmi_zero.append(pmi == 0.0)
        results.append({
            'id': case['id'],
            'categoria': categoria,
            'expected': expected,
            'query': query,
            'deep': deep,
            'pool': pool,
            'pmi_zero': pmi_zero,
        })
    db.conn.close()
    os.remove(temp_db)
    out_queue.put((worker_id, results))


def _metricas_caso(caso, cand_bridges, top_k, peso, umbral):
    """Re-ordena el pool del caso con el puente y devuelve métricas locales."""
    pool = caso['pool']
    expected = caso['expected']
    n = len(pool)
    base_top5 = pool[:5]
    scores_aj = []
    for i, cand in enumerate(pool):
        score = cand['score']
        if i >= 5 and caso['pmi_zero'][i]:
            bridge = _bridge_score_desde_estructura(cand_bridges[i], top_k, umbral)
            score = score + peso * bridge
        scores_aj.append(score)
    order = sorted(range(n), key=lambda i: (-scores_aj[i], i))
    new_top5 = [pool[i]['concepto'] for i in order[:5]]

    base_hit = expected in [c['concepto'] for c in base_top5]
    new_hit = expected in new_top5

    fp_base = 0
    fp_new = 0
    if expected is None:
        if any(c['score'] >= 0.25 for c in base_top5):
            fp_base = 1
        if any(scores_aj[i] >= 0.25 for i in order[:5]):
            fp_new = 1
    return {
        'base_hit': base_hit,
        'new_hit': new_hit,
        'fp_base': fp_base,
        'fp_new': fp_new,
    }


def _evaluar_config(casos, bridges, top_k, peso, umbral):
    tabla_por_caso = bridges
    stats = defaultdict(lambda: {'total': 0, 'base_hits': 0, 'new_hits': 0,
                                 'rescatados': 0, 'regresiones': 0, 'fp': 0})
    for idx, caso in enumerate(casos):
        m = _metricas_caso(caso, tabla_por_caso[idx], top_k, peso, umbral)
        cat = caso['categoria']
        stats[cat]['total'] += 1
        if caso['expected'] is None:
            stats[cat]['fp'] += m['fp_new']
        else:
            stats[cat]['base_hits'] += m['base_hit']
            stats[cat]['new_hits'] += m['new_hit']
            if m['new_hit'] and not m['base_hit']:
                stats[cat]['rescatados'] += 1
            if m['base_hit'] and not m['new_hit']:
                stats[cat]['regresiones'] += 1
    # GLOBAL: todas las categorías con expected (excluye negativo)
    cats_ret = [c for c in stats if c != 'negativo']
    n_ret = sum(stats[c]['total'] for c in cats_ret)
    base_h = sum(stats[c]['base_hits'] for c in cats_ret)
    new_h = sum(stats[c]['new_hits'] for c in cats_ret)
    rescate = sum(stats[c]['rescatados'] for c in cats_ret)
    regresion = sum(stats[c]['regresiones'] for c in cats_ret)
    return {
        'top_k': top_k,
        'peso': peso,
        'umbral': umbral,
        'r5_base_global': round(100.0 * base_h / n_ret, 2) if n_ret else 0.0,
        'r5_new_global': round(100.0 * new_h / n_ret, 2) if n_ret else 0.0,
        'delta_global': round(100.0 * (new_h - base_h) / n_ret, 2) if n_ret else 0.0,
        'rescatados': rescate,
        'regresiones': regresion,
        'por_tema': {
            'base': round(100.0 * stats['por_tema']['base_hits'] / stats['por_tema']['total'], 2),
            'new': round(100.0 * stats['por_tema']['new_hits'] / stats['por_tema']['total'], 2),
            'rescatados': stats['por_tema']['rescatados'],
            'regresiones': stats['por_tema']['regresiones'],
        },
        'sinonimo': {
            'base': round(100.0 * stats['sinonimo']['base_hits'] / stats['sinonimo']['total'], 2),
            'new': round(100.0 * stats['sinonimo']['new_hits'] / stats['sinonimo']['total'], 2),
            'rescatados': stats['sinonimo']['rescatados'],
            'regresiones': stats['sinonimo']['regresiones'],
        },
        'fp_negativo': stats['negativo']['fp'],
        'max_regresion_por_categoria': max((stats[c]['regresiones'] for c in cats_ret), default=0),
    }


def _baseline_metrics(casos):
    stats = defaultdict(lambda: {'total': 0, 'hits': 0, 'fp': 0})
    for caso in casos:
        cat = caso['categoria']
        stats[cat]['total'] += 1
        if caso['expected'] is None:
            if any(c['score'] >= 0.25 for c in caso['pool'][:5]):
                stats[cat]['fp'] += 1
        else:
            if caso['expected'] in [c['concepto'] for c in caso['pool'][:5]]:
                stats[cat]['hits'] += 1
    return stats


def main():
    parser = argparse.ArgumentParser(description='Sweep del puente HDC condicional (Fase 2)')
    parser.add_argument('--snapshot', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--split', default=str(DEFAULT_SPLIT))
    parser.add_argument('--vectores', default=str(DEFAULT_VECTORES))
    parser.add_argument('--casos', default=str(DEFAULT_CASOS))
    parser.add_argument('--mitad', default='A', choices=['A', 'B'])
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--salida', default=str(SALIDA))
    args = parser.parse_args()

    t0 = time.time()
    if not os.path.exists(args.snapshot):
        sys.exit(f"[ERROR] Snapshot no encontrado: {args.snapshot}")
    if not os.path.exists(args.split):
        sys.exit(f"[ERROR] Split no encontrado: {args.split}")
    if not os.path.exists(args.vectores):
        sys.exit(f"[ERROR] Vectores no encontrados: {args.vectores}")

    with open(args.split, 'r', encoding='utf-8') as f:
        split = json.load(f)
    casos = _merge_deep(split[f'mitad_{args.mitad}'], args.casos)
    print(f"[1/7] Casos mitad {args.mitad}: {len(casos)}")

    # Vectores + stems por concepto (solo los necesarios del snapshot)
    bitsets = _cargar_vectores(args.vectores)
    print(f"[2/7] Vectores cargados: {[f'{v}={len(b)}' for v, b in bitsets.items()]}")

    stems_por_concepto = _cargar_stems_por_concepto(args.snapshot)
    print(f"[3/7] Stems por concepto: {len(stems_por_concepto)}")

    # Tokens únicos de query para precomputar tablas de similitud
    query_tokens_unicos = set()
    for c in casos:
        query_tokens_unicos |= set(_tokenizar(c['query']))
    print(f"[4/7] Tokens de query únicos: {len(query_tokens_unicos)}")

    tablas = _precomputar_tablas_sim(query_tokens_unicos, bitsets)
    print(f"[5/7] Tablas de similitud precomputadas ({time.time()-t0:.1f}s)")

    # Pipeline real sobre snapshot (workers)
    n_workers = min(args.workers, max(1, len(casos)))
    chunks = [casos[i::n_workers] for i in range(n_workers)]
    q = Queue()
    procs = []
    for i, ch in enumerate(chunks):
        p = Process(target=worker, args=(i, ch, args.snapshot, q))
        p.start()
        procs.append(p)
    all_results = []
    for _ in procs:
        wid, res = q.get()
        all_results.extend(res)
    for p in procs:
        p.join()
    all_results.sort(key=lambda c: c['id'])
    print(f"[6/7] Pipeline real completada: {len(all_results)} casos ({time.time()-t0:.1f}s)")

    # Baseline (sin puente) sobre el pool re-corrido
    stats_base = _baseline_metrics(all_results)
    cats_ret = [c for c in stats_base if c != 'negativo']
    n_ret = sum(stats_base[c]['total'] for c in cats_ret)
    h_ret = sum(stats_base[c]['hits'] for c in cats_ret)
    baseline = {
        'n_retrieval': n_ret,
        'R5_global': round(100.0 * h_ret / n_ret, 2),
        'por_categoria': {c: {
            'n': stats_base[c]['total'],
            'R5': round(100.0 * stats_base[c]['hits'] / stats_base[c]['total'], 2) if stats_base[c]['total'] else 0.0,
        } for c in stats_base},
        'fp_negativo': stats_base['negativo']['fp'],
        'n_negativo': stats_base['negativo']['total'],
    }
    print(f"      Baseline: R@5 global {baseline['R5_global']}% | FP negativo {baseline['fp_negativo']}")

    # Barrido de configs (bridges precomputados por ventana)
    configs = []
    for ventana in VENTANAS:
        bridges = _precomputar_bridges(all_results, ventana, tablas[ventana],
                                       stems_por_concepto)
        print(f"      Ventana {ventana}: bridges precomputados ({time.time()-t0:.1f}s)")
        for top_k in TOPK_VALORES:
            for peso in PESO_VALORES:
                for umbral in UMBRAL_VALORES:
                    cfg = _evaluar_config(all_results, bridges, top_k, peso, umbral)
                    cfg['ventana'] = ventana
                    configs.append(cfg)

    # Selección: mayor rescate sin regresión >1 caso por categoría
    validos = [c for c in configs if c['max_regresion_por_categoria'] <= 1]
    if validos:
        mejor = max(validos, key=lambda c: (c['rescatados'], c['delta_global']))
    else:
        mejor = min(configs, key=lambda c: c['regresiones'])
    print(f"[7/7] {len(configs)} configs | Mejor: {mejor['ventana']} "
          f"top_k={mejor['top_k']} peso={mejor['peso']} umbral={mejor['umbral']} "
          f"| rescate {mejor['rescatados']} | delta {mejor['delta_global']:+}pp ({time.time()-t0:.1f}s)")

    salida = {
        'fase': '2',
        'descripcion': 'Sweep del puente HDC condicional sobre mitad A del holdout. '
                       'Pipeline real buscar_por_frase(limite=100) sobre snapshot de Fase 0. '
                       'Trigger condicional: candidato fuera de top-5 base Y score_pmi_nodo==0. '
                       'Re-ordena el pool sumando peso * bridge_score a esos candidatos.',
        'snapshot': os.path.basename(args.snapshot),
        'mitad': args.mitad,
        'seed_split': split.get('seed'),
        'n_casos': len(all_results),
        'ventanas_orden_prioridad': VENTANAS,
        'baseline': baseline,
        'grid': {
            'ventanas': VENTANAS,
            'top_k': TOPK_VALORES,
            'peso': PESO_VALORES,
            'umbral': UMBRAL_VALORES,
        },
        'n_configs': len(configs),
        'configs': configs,
        'mejor_config': mejor,
        'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"Guardado: {args.salida}")


if __name__ == '__main__':
    main()
