#!/usr/bin/env python3
"""Plan Tejedora — Fase 0: Preparación reproducible.

Outputs (artefactos):
  snapshots/tejedora_pre_fase0_<timestamp>.db  Snapshot consistente (backup API) + integrity_check
  scripts/tejedora_split_50_50.json            Split estratificado por categoría (seed 20260804)
  scripts/tejedora_baseline.json               Baseline R@5/R@1/MRR por categoría + global

Reusa el protocolo de split de experimento_faseB_holdout.py y el pool de
experimento_rr_pool.json (921 casos). No toca la DB viva: solo lee.
"""
import json
import os
import random
import sqlite3
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag.db")
POOL_PATH = os.path.join(BASE, "scripts", "experimento_rr_pool.json")
SNAP_DIR = os.path.join(BASE, "snapshots")
SEED = 20260804


def snapshot_db():
    """Snapshot consistente vía backup API de sqlite (seguro con WAL)."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(SNAP_DIR, f"tejedora_pre_fase0_{stamp}.db")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    conn = sqlite3.connect(dest)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    if integrity != "ok":
        raise RuntimeError(f"Integrity check del snapshot falló: {integrity}")
    return dest, integrity


def load_pool():
    with open(POOL_PATH, encoding="utf-8") as f:
        return json.load(f)


def split_stratified(cases, seed=SEED):
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


def metrics(cases):
    stats = defaultdict(lambda: {"total": 0, "hits5": 0, "hits1": 0, "mrr": 0.0})
    for c in cases:
        cat = c["categoria"]
        exp = c["expected"]
        pool = c.get("pool", [])
        stats[cat]["total"] += 1
        for i, it in enumerate(pool[:5]):
            if it["concepto"] == exp:
                stats[cat]["hits5"] += 1
                stats[cat]["hits1"] += 1 if i == 0 else 0
                stats[cat]["mrr"] += 1.0 / (i + 1)
                break
    return stats


def report_to_json(title, stats):
    out = {}
    tot_n = tot_h5 = tot_h1 = 0
    mrr_acc = 0.0
    for cat in sorted(stats.keys()):
        s = stats[cat]
        r5 = 100.0 * s["hits5"] / s["total"] if s["total"] else 0
        r1 = 100.0 * s["hits1"] / s["total"] if s["total"] else 0
        mrr = s["mrr"] / s["total"] if s["total"] else 0
        out[cat] = {"n": s["total"], "hits5": s["hits5"], "R@5": round(r5, 2),
                    "hits1": s["hits1"], "R@1": round(r1, 2), "MRR": round(mrr, 4)}
        if cat != "negativo":
            tot_n += s["total"]; tot_h5 += s["hits5"]; tot_h1 += s["hits1"]; mrr_acc += s["mrr"]
    out["GLOBAL"] = {"n": tot_n, "hits5": tot_h5, "R@5": round(100.0 * tot_h5 / tot_n, 2),
                     "hits1": tot_h1, "R@1": round(100.0 * tot_h1 / tot_n, 2),
                     "MRR": round(mrr_acc / tot_n, 4)} if tot_n else {}
    return out


def main():
    print("=== TEJEDORA — FASE 0 ===\n")

    snap, integrity = snapshot_db()
    print(f"1. Snapshot: {os.path.relpath(snap, BASE)} (integrity={integrity})")

    cases = load_pool()
    half_a, half_b = split_stratified(cases)
    by_cat = defaultdict(lambda: [0, 0])
    for c in half_a:
        by_cat[c["categoria"]][0] += 1
    for c in half_b:
        by_cat[c["categoria"]][1] += 1
    dist = {k: {"A": v[0], "B": v[1], "total": v[0] + v[1]} for k, v in sorted(by_cat.items())}
    print(f"2. Split seed={SEED}: A={len(half_a)}, B={len(half_b)}, total={len(cases)}")
    for k, v in dist.items():
        print(f"    {k:<20} A={v['A']:<4} B={v['B']:<4} total={v['total']}")

    split_path = os.path.join(BASE, "scripts", "tejedora_split_50_50.json")
    with open(split_path, "w", encoding="utf-8") as f:
        json.dump({"seed": SEED, "mitad_A": half_a, "mitad_B": half_b,
                   "distribucion": dist, "total": len(cases)}, f, ensure_ascii=False, indent=1)
    print(f"3. Split guardado: {os.path.relpath(split_path, BASE)}")

    base_full = metrics(cases)
    base_a = metrics(half_a)
    base_b = metrics(half_b)
    baseline = {
        "descripcion": "Baseline R@5 sobre pools almacenados en experimento_rr_pool.json (sin tejido). "
                       "n_pools_sin_resultado: casos cuyo pool está vacío.",
        "GLOBAL_completo": report_to_json("completo", base_full)["GLOBAL"],
        "por_categoria_completo": report_to_json("completo", base_full),
        "GLOBAL_mitad_A": report_to_json("A", base_a)["GLOBAL"],
        "GLOBAL_mitad_B": report_to_json("B", base_b)["GLOBAL"],
        "por_categoria_mitad_B": report_to_json("B", base_b),
        "seed": SEED,
        "n_casos": len(cases),
    }
    baseline_path = os.path.join(BASE, "scripts", "tejedora_baseline.json")
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=1)
    print(f"4. Baseline guardado: {os.path.relpath(baseline_path, BASE)}")

    rep = baseline["por_categoria_completo"]
    print("\n=== BASELINE COMPLETO (921 casos, sin tejido) ===")
    print(f"{'categoria':<20} {'n':<4} {'R@5':<7} {'R@1':<7} {'MRR':<6}")
    for cat, s in rep.items():
        if cat == "GLOBAL":
            continue
        print(f"{cat:<20} {s['n']:<4} {s['R@5']:<7.2f} {s['R@1']:<7.2f} {s['MRR']:<6.3f}")
    g = rep["GLOBAL"]
    print(f"{'GLOBAL':<20} {g['n']:<4} {g['R@5']:<7.2f} {g['R@1']:<7.2f} {g['MRR']:<6.3f}")
    print("\nFase 0 COMPLETA. Producción no modificada.")


if __name__ == "__main__":
    main()
