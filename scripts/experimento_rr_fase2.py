import os
import json
import sys
from collections import defaultdict

def load_pool():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base_dir, "scripts", "experimento_rr_pool.json"), encoding="utf-8") as f:
        return json.load(f)

def recall_5(results, topk=5):
    stats = defaultdict(lambda: {"total": 0, "hits5": 0, "hits1": 0, "mrr": 0.0})
    for c in results:
        cat = c["categoria"]
        exp = c["expected"]
        pool = c["pool"]
        stats[cat]["total"] += 1
        pos = -1
        for i, it in enumerate(pool[:topk]):
            if it["concepto"] == exp:
                pos = i
                break
        if pos != -1:
            stats[cat]["hits5"] += 1
            stats[cat]["hits1"] += 1 if pos == 0 else 0
            stats[cat]["mrr"] += 1.0 / (pos + 1)
    return stats

def apply_rerank(c, alpha, gate_umbral, topk, gate_mode, jacc_pool_window):
    pool = c["pool"]
    if not pool:
        return pool
    exp = c["expected"]
    q = c["query"]
    # gate: uniformemente bajo jaccard en el pool -> no re-rankear
    if gate_mode == "max_pool":
        # max jaccard en todo el pool (o ventana)
        win = pool[:jacc_pool_window]
        max_j = max((it["jaccard"] for it in win), default=0.0)
        if max_j < gate_umbral:
            return pool
    elif gate_mode == "max_expected":
        j_exp = next((it["jaccard"] for it in pool if it["concepto"] == exp), 0.0)
        if j_exp < gate_umbral:
            return pool
    # re-rankear top-k por score + alpha*jaccard
    head = pool[:topk]
    tail = pool[topk:]
    max_j = max((it["jaccard"] for it in pool[:jacc_pool_window]), default=1e-9) or 1e-9
    def key_fn(it):
        return it["score"] + alpha * (it["jaccard"] / max_j)
    head = sorted(head, key=key_fn, reverse=True)
    return head + tail

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
    base = recall_5(cases)
    report("BASELINE (sin re-ranking)", base)

    configs = []
    for alpha in (0.25, 0.5, 1.0, 2.0):
        for umbral in (0.02, 0.04, 0.06, 0.08, 0.10):
            for topk in (10, 20, 50):
                configs.append({"alpha": alpha, "gate": umbral, "topk": topk, "mode": "max_pool", "win": 50})
    # variantes
    configs.append({"alpha": 0.5, "gate": 0.06, "topk": 20, "mode": "max_expected", "win": 50})
    configs.append({"alpha": 1.0, "gate": 0.06, "topk": 20, "mode": "max_expected", "win": 50})

    best_by_total = []
    for cfg in configs:
        reranked = []
        for c in cases:
            rr = apply_rerank(c, cfg["alpha"], cfg["gate"], cfg["topk"], cfg["mode"], cfg["win"])
            reranked.append({**c, "pool": rr})
        st = recall_5(reranked)
        # metricas de interes
        g = {k: v for k, v in st.items()}
        total_h5 = sum(v["hits5"] for k, v in g.items() if k != "negativo")
        total_n = sum(v["total"] for k, v in g.items() if k != "negativo")
        pt = g.get("por_tema", {"hits5": 0, "total": 1})
        si = g.get("sinonimo", {"hits5": 0, "total": 1})
        li = g.get("literal", {"hits5": 0, "total": 1})
        best_by_total.append({
            **cfg,
            "global_r5": 100.0 * total_h5 / total_n,
            "por_tema_r5": 100.0 * pt["hits5"] / pt["total"],
            "sinonimo_r5": 100.0 * si["hits5"] / si["total"],
            "literal_r5": 100.0 * li["hits5"] / li["total"],
        })

    print("\n" + "="*100)
    print("BARRIDO — delta vs baseline por config (global, por_tema, sinonimo, literal)")
    print("="*100)
    b_g = sum(v["hits5"] for k, v in base.items() if k != "negativo")
    b_n = sum(v["total"] for k, v in base.items() if k != "negativo")
    b_pt = 100.0 * base["por_tema"]["hits5"] / base["por_tema"]["total"]
    b_si = 100.0 * base["sinonimo"]["hits5"] / base["sinonimo"]["total"]
    b_li = 100.0 * base["literal"]["hits5"] / base["literal"]["total"]
    print(f"baseline: global={100.0*b_g/b_n:.2f} por_tema={b_pt:.2f} sinonimo={b_si:.2f} literal={b_li:.2f}")
    print(f"{'alpha':<6} {'gate':<6} {'topk':<5} {'mode':<12} {'win':<4} | {'dGLOBAL':<8} {'dpor_tema':<9} {'dsinonimo':<10} {'dliteral':<9}")
    seen = set()
    for c in sorted(best_by_total, key=lambda x: (-x["global_r5"], -x["por_tema_r5"])):
        key = (c["alpha"], c["gate"], c["topk"], c["mode"], c["win"])
        if key in seen:
            continue
        seen.add(key)
        dg = c["global_r5"] - 100.0*b_g/b_n
        dpt = c["por_tema_r5"] - b_pt
        dsi = c["sinonimo_r5"] - b_si
        dli = c["literal_r5"] - b_li
        flag = " *" if (dpt > 1.0 and dsi >= -0.5 and dli >= -0.5) else ""
        print(f"{c['alpha']:<6} {c['gate']:<6} {c['topk']:<5} {c['mode']:<12} {c['win']:<4} | {dg:<+8.2f} {dpt:<+9.2f} {dsi:<+10.2f} {dli:<+9.2f}{flag}")

    # Mejores 8 configs por ganancia neta (por_tema + sinonimo no degradado)
    print("\nTOP 8 CONFIGS — mejor dpor_tema sin degradar sinonimo/literal:")
    scored = []
    for c in best_by_total:
        key = (c["alpha"], c["gate"], c["topk"], c["mode"], c["win"])
        if key in scored:
            continue
        scored.append(key)
        dpt = c["por_tema_r5"] - b_pt
        dsi = c["sinonimo_r5"] - b_si
        dli = c["literal_r5"] - b_li
        if dsi >= -0.5 and dli >= -0.5:
            scored[-1] = (c, dpt, dsi, dli)
        else:
            scored[-1] = (c, dpt, dsi, dli)
    scored.sort(key=lambda x: -x[1])
    for c, dpt, dsi, dli in scored[:8]:
        print(f"  alpha={c['alpha']:.2f} gate={c['gate']:.2f} topk={c['topk']} mode={c['mode']} win={c['win']} -> por_tema {dpt:+.2f}pp | sinonimo {dsi:+.2f}pp | literal {dli:+.2f}pp | global {c['global_r5']-100.0*b_g/b_n:+.2f}pp")

if __name__ == "__main__":
    main()
