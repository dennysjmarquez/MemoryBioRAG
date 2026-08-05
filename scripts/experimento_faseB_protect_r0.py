#!/usr/bin/env python3
"""Fase B — variante "no demover rank 0" (Opción 2 del evaluador, 2026-08-04).

Hipótesis de diseño (no parche): el re-ranking está diseñado para RESCATAR
candidatos hundidos, no para reordenar lo que ya andaba bien. Si un ítem ya está
en el primer puesto (rank 0), el caso ya está "ganado"; ninguna señal de rescate
debería hundirlo. Regla: tras re-sort del head por score+alpha*jaccard, se
RESTAURA a la posición 0 el ítem que ocupaba la primera posición del pool antes
del re-ranking.

Se mide con el mismo protocolo de holdout estricto: split estratificado seed fija,
ajuste de α/gate/topk en A SOLO (criterio balanceado con restricción de no-daño),
medición en B que nunca vio el ajuste. Foco de la medición:
  - ¿variante/pregunta_natural/sinonimo/typo dejan de perder R@1 en B?
  - ¿el rescate de por_tema en B se mantiene mayormente intacto al proteger rank 0?
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
    """Split 50/50 estratificado por categoría con seed fija (idéntico a Fase B)."""
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


def apply_rerank_protect_r0(c, alpha, gate_umbral, topk, jacc_pool_window=50):
    """Re-ranking jaccard con protección de rank 0.

    Gate por max jaccard del pool[:50]; re-sort del top-k por
    score + alpha*(jaccard/max_j); luego, si el ítem que ocupaba la posición 0
    del pool original fue desplazado, se restaura a la primera posición.
    """
    pool = c["pool"]
    if not pool:
        return pool
    win = pool[:jacc_pool_window]
    max_j = max((it["jaccard"] for it in win), default=0.0)
    if max_j < gate_umbral:
        return pool
    original_r0 = pool[0]
    head = pool[:topk]
    tail = pool[topk:]
    max_j_norm = max_j or 1e-9
    head = sorted(head, key=lambda it: it["score"] + alpha * (it["jaccard"] / max_j_norm), reverse=True)
    if head and head[0] is not original_r0:
        head = [original_r0] + [it for it in head if it is not original_r0]
    return head + tail


def metrics(cases, reranked=False, alpha=0.25, gate=0.04, topk=50):
    stats = defaultdict(lambda: {"total": 0, "hits5": 0, "hits1": 0, "mrr": 0.0})
    for c in cases:
        cat = c["categoria"]
        exp = c["expected"]
        pool = apply_rerank_protect_r0(c, alpha, gate, topk) if reranked else c["pool"]
        stats[cat]["total"] += 1
        for i, it in enumerate(pool[:5]):
            if it["concepto"] == exp:
                stats[cat]["hits5"] += 1
                stats[cat]["hits1"] += 1 if i == 0 else 0
                stats[cat]["mrr"] += 1.0 / (i + 1)
                break
    return stats


def neto_por_tema(stats, base_stats):
    cat = "por_tema"
    return stats[cat]["hits5"] - base_stats[cat]["hits5"]


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


def detalle_casos(half_b, alpha, gate, topk, categorias_objetivo):
    """Lista caso por caso los cambios de bucket (R1/R5/OUT) en B por categoría."""
    def bucket(c, pool):
        for i, it in enumerate(pool):
            if it["concepto"] == c["expected"]:
                return "R1" if i == 0 else ("R5" if i < 5 else "OUT")
        return "NF"

    print("\n=== DETALLE CASO POR CASO EN B (cambios de bucket) ===")
    for cat in categorias_objetivo:
        regs, rescs = [], []
        for c in half_b:
            if c["categoria"] != cat:
                continue
            bb = bucket(c, c["pool"])
            rb = bucket(c, apply_rerank_protect_r0(c, alpha, gate, topk))
            if bb == rb:
                continue
            (rescs if rb < bb else regs).append((c["id"], bb, rb))
        if regs:
            print(f"  {cat:<18} REGRESIONES: {regs}")
        if rescs:
            print(f"  {cat:<18} RESCATES: {rescs}")


def main():
    cases = load_pool()
    half_a, half_b = split_stratified(cases)
    print(f"Split seed={SEED}: A={len(half_a)}, B={len(half_b)}, total={len(cases)}")

    base_a = metrics(half_a)
    base_b = metrics(half_b)
    report("BASELINE MITAD A (ajuste)", base_a)
    report("BASELINE MITAD B (validación)", base_b)

    print("\n=== AJUSTE EN MITAD A (protect-r0, balanceado con restricción) ===")
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
    validas.sort(key=lambda r: (r[1], r[0]), reverse=True)
    for net, penal, alpha, gate, topk in (validas or rows)[:6]:
        print(f"  net_por_tema={net:+d}  penal_otras={penal:+d}  α={alpha}  gate={gate}  topk={topk}")
    if not validas:
        print("  (ninguna config cumple la restricción — se elige la mejor net sin restricción)")
        validas = rows
    best_net, best_penal, best_alpha, best_gate, best_topk = validas[0]
    print(f"ELEGIDA EN A (protect-r0): α={best_alpha}, gate={best_gate}, topk={best_topk} "
          f"(neto por_tema A={best_net:+d}, penal_otras={best_penal:+d})")

    print("\n=== MEDICIÓN EN MITAD B (config elegida en A, protect-r0) ===")
    s_b = metrics(half_b, reranked=True, alpha=best_alpha, gate=best_gate, topk=best_topk)
    report("MITAD B + RERANK protect-r0 (config de A)", s_b)
    print("\n=== DELTA POR CATEGORÍA EN B (baseline -> rerank protect-r0) ===")
    for cat in sorted(base_b.keys()):
        b = base_b[cat]
        r = s_b[cat]
        if b["total"] == 0:
            continue
        d5 = r["hits5"] - b["hits5"]
        d1 = r["hits1"] - b["hits1"]
        print(f"  {cat:<20} R@5 {100.0*b['hits5']/b['total']:6.2f} -> {100.0*r['hits5']/r['total']:6.2f}  ({d5:+d})  | R@1 {100.0*b['hits1']/b['total']:6.2f} -> {100.0*r['hits1']/r['total']:6.2f}  ({d1:+d})")

    detalle_casos(half_b, best_alpha, best_gate, best_topk,
                  ["por_tema", "variante_gramatical", "pregunta_natural", "sinonimo", "typo", "cruce_idioma"])


if __name__ == "__main__":
    main()
