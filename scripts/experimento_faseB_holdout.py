#!/usr/bin/env python3
"""Fase B: holdout estricto 50/50 estratificado por categoría (seed fija).
Pregunta única: ¿la ventaja de jaccard sobre baseline se sostiene en la mitad B
que nunca vio el ajuste de α/gate?

Protocolo:
  1. Split estratificado por categoría (random shuffle con seed fija, 50/50).
  2. Mitad A: barrido de configs (α x gate x topk). Se elige la mejor por
     la métrica definida (por_tema R@5) sobre A SOLO.
  3. Mitad B (no participó del ajuste): se aplica la config elegida en A y se
     reportan baseline vs rerank en B.
"""
import os
import json
import random
from collections import defaultdict

SEED = 20260804


def load_pool():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base_dir, "scripts", "experimento_rr_pool.json"), encoding="utf-8") as f:
        return json.load(f)


def split_stratified(cases, seed=SEED):
    """Split 50/50 estratificado por categoría con seed fija."""
    rng = random.Random(seed)
    by_cat = defaultdict(list)
    for c in cases:
        by_cat[c["categoria"]].append(c)
    half_a, half_b = [], []
    for cat, items in by_cat.items():
        shuffled = list(items)
        rng.shuffle(shuffled)
        mid = len(shuffled) // 2
        half_a.extend(shuffled[:mid])
        half_b.extend(shuffled[mid:])
    half_a.sort(key=lambda c: c["id"])
    half_b.sort(key=lambda c: c["id"])
    return half_a, half_b


def apply_rerank(c, alpha, gate_umbral, topk, jacc_pool_window=50):
    """Re-ranking jaccard: gate por max jaccard del pool[:50], luego
    re-sort del top-k por score + alpha*(jaccard/max_j)."""
    pool = c["pool"]
    if not pool:
        return pool
    exp = c["expected"]
    win = pool[:jacc_pool_window]
    max_j = max((it["jaccard"] for it in win), default=0.0)
    if max_j < gate_umbral:
        return pool
    head = pool[:topk]
    tail = pool[topk:]
    max_j_norm = max_j or 1e-9
    head = sorted(head, key=lambda it: it["score"] + alpha * (it["jaccard"] / max_j_norm), reverse=True)
    return head + tail


def metrics(cases, reranked=False, alpha=0.25, gate=0.04, topk=50):
    stats = defaultdict(lambda: {"total": 0, "hits5": 0, "hits1": 0, "mrr": 0.0})
    for c in cases:
        cat = c["categoria"]
        exp = c["expected"]
        pool = apply_rerank(c, alpha, gate, topk) if reranked else c["pool"]
        stats[cat]["total"] += 1
        for i, it in enumerate(pool[:5]):
            if it["concepto"] == exp:
                stats[cat]["hits5"] += 1
                stats[cat]["hits1"] += 1 if i == 0 else 0
                stats[cat]["mrr"] += 1.0 / (i + 1)
                break
    return stats


def neto_por_tema(stats, base_stats):
    """Diferencia en hits R@5 de por_tema entre rerank y baseline (sobre la mitad dada)."""
    cat = "por_tema"
    b5 = base_stats[cat]["hits5"]
    r5 = stats[cat]["hits5"]
    return r5 - b5


def report(title, stats):
    print(f"\n{title}")
    print(f"{'categoria':<20} {'n':<4} {'R@5':<7} {'R@1':<7} {'MRR':<6}")
    tot_n = tot_h5 = tot_h1 = 0
    mrr_acc = 0.0
    for cat in sorted(stats.keys()):
        s = stats[cat]
        r5 = 100.0 * s["hits5"] / s["total"] if s["total"] else 0
        r1 = 100.0 * s["hits1"] / s["total"] if s["total"] else 0
        mrr = s["mrr"] / s["total"] if s["total"] else 0
        print(f"{cat:<20} {s['total']:<4} {r5:<7.2f} {r1:<7.2f} {mrr:<6.3f}")
        if cat != "negativo":
            tot_n += s["total"]; tot_h5 += s["hits5"]; tot_h1 += s["hits1"]; mrr_acc += s["mrr"]
    if tot_n:
        print(f"{'GLOBAL':<20} {tot_n:<4} {100.0*tot_h5/tot_n:<7.2f} {100.0*tot_h1/tot_n:<7.2f} {mrr_acc/tot_n:<6.3f}")


def main():
    cases = load_pool()
    half_a, half_b = split_stratified(cases)
    n_total = len(cases)
    print(f"Split seed={SEED}: A={len(half_a)}, B={len(half_b)}, total={n_total}")
    by_cat_a = defaultdict(int)
    by_cat_b = defaultdict(int)
    for c in half_a:
        by_cat_a[c["categoria"]] += 1
    for c in half_b:
        by_cat_b[c["categoria"]] += 1
    print("Distribución A:", dict(by_cat_a))
    print("Distribución B:", dict(by_cat_b))
    assert all(by_cat_a[k] >= 1 for k in by_cat_a if k != "negativo"), "Categoría sin casos en A"

    base_a = metrics(half_a)
    base_b = metrics(half_b)
    report("BASELINE MITAD A (ajuste)", base_a)
    report("BASELINE MITAD B (validación)", base_b)

    # Ajuste en A SOLO: barrido de configs.
    # Criterio balanceado con restricción explícita:
    #   - Solo configs con neto por_tema positivo en A.
    #   - Entre ellas, solo las que NO dañan otras categorías en A (penal >= -1).
    #   - Elegir la de mayor neto por_tema; desempate por penalidad más alta.
    # Esto evita que el ajuste sobre-optimice por_tema destruyendo sinonimo/literal.
    print("\n=== AJUSTE EN MITAD A (balanceado con restricción: no dañar otras categorías) ===")
    rows = []
    for alpha in (0.25, 0.5, 1.0):
        for gate in (0.02, 0.04, 0.06, 0.08, 0.10):
            for topk in (10, 20, 50):
                s = metrics(half_a, reranked=True, alpha=alpha, gate=gate, topk=topk)
                net = neto_por_tema(s, base_a)
                penal = sum(
                    s[k]["hits5"] - base_a[k]["hits5"]
                    for k in ("sinonimo", "literal", "pregunta_natural", "variante_gramatical", "typo", "dormido")
                )
                rows.append((net, penal, alpha, gate, topk))
    validas = [r for r in rows if r[0] > 0 and r[1] >= -1]
    validas.sort(key=lambda r: (r[0], r[1]), reverse=True)
    for net, penal, alpha, gate, topk in (validas or rows)[:6]:
        print(f"  net_por_tema={net:+d}  penal_otras={penal:+d}  α={alpha}  gate={gate}  topk={topk}")
    if not validas:
        print("  (ninguna config cumple la restricción — se elige la mejor net sin restricción)")
        validas = rows
    best_net, best_penal, best_alpha, best_gate, best_topk = validas[0]
    print(f"ELEGIDA EN A (balanceada): α={best_alpha}, gate={best_gate}, topk={best_topk} "
          f"(neto por_tema A={best_net:+d}, penal_otras={best_penal:+d})")

    # Medición en B con la config elegida en A (B no vio el ajuste)
    print("\n=== MEDICIÓN EN MITAD B (config elegida en A) ===")
    s_b = metrics(half_b, reranked=True, alpha=best_alpha, gate=best_gate, topk=best_topk)
    report("MITAD B + RERANK (config de A)", s_b)
    print("\n=== DELTA POR CATEGORÍA EN B (baseline -> rerank) ===")
    for cat in sorted(base_b.keys()):
        b = base_b[cat]
        r = s_b[cat]
        if b["total"] == 0:
            continue
        d5 = r["hits5"] - b["hits5"]
        d1 = r["hits1"] - b["hits1"]
        print(f"  {cat:<20} R@5 {100.0*b['hits5']/b['total']:6.2f} -> {100.0*r['hits5']/r['total']:6.2f}  ({d5:+d})  | R@1 {100.0*b['hits1']/b['total']:6.2f} -> {100.0*r['hits1']/r['total']:6.2f}  ({d1:+d})")


if __name__ == "__main__":
    main()
