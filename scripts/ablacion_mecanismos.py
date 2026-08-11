#!/usr/bin/env python3
"""
ablacion_mecanismos.py — Ablación de mecanismos "neuro-narrativos" de BioRAG

Corre la suite QA de 921 casos con cada mecanismo desactivado por separado
y compara contra el baseline completo.

Uso:
    python3 scripts/ablacion_mecanismos.py

Mecanismos evaluados:
    1. GABA (inhibición lateral)      — BIORAG_GABA_ACTIVO=0
    2. Re-ranking Jaccard léxico      — BIORAG_RERANKING_JACCARD_ENABLED=0
    3. PPMI+SVD vectorial             — BIORAG_PPMI_WEIGHT=0.0
    4. DMN (ideación en reposo)       — BIORAG_DMN_IDLE_SECONDS=999999
"""
import os
import sys
import json
import sqlite3
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

SNAPSHOT   = os.path.join(BASE_DIR, "scripts", "snapshot_prf_real.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")


def run_eval(env_overrides: dict, label: str) -> dict:
    env = os.environ.copy()
    env["BIORAG_PATH"] = SNAPSHOT
    env.update({k: str(v) for k, v in env_overrides.items()})

    print(f"\n>>> Iniciando prueba de evaluación: {label}")
    print(f"    Variables activas: {env_overrides if env_overrides else 'Defaults (Baseline)'}\n", flush=True)

    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "scripts", "evaluar_qa.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    output_lines = []
    for line in iter(proc.stdout.readline, ''):
        sys.stdout.write("  | " + line)
        sys.stdout.flush()
        output_lines.append(line)
    proc.wait()

    stats = {}
    for line in output_lines:
        if "|" in line and "%" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                cat = parts[0].strip()
                r5 = parts[2].strip().replace("%", "").strip()
                try:
                    stats[cat] = float(r5)
                except ValueError:
                    pass
    return {"label": label, "stats": stats}


def main():
    if not os.path.exists(SNAPSHOT):
        print(f"Snapshot no encontrado en {SNAPSHOT}. Auto-generando desde fuentes...")
        from scripts.generar_snapshot import main as gen_snap
        gen_snap()

    print("=" * 72)
    print("  ABLACIÓN DE MECANISMOS BioRAG — Contribución al Recall@5")
    print("=" * 72)
    print("  Snapshot: scripts/snapshot_prf_real.db (~803 nodos congelados)")
    print("  Casos QA: 921 (8 categorías)")
    print("  Tiempo estimado por config: ~9 min  |  Total: ~45-50 min")
    print()

    configs = [
        ({},                                            "Baseline (todos ON)"),
        ({"BIORAG_GABA_ACTIVO": "0"},                  "Sin GABA  (inhibición lateral OFF)"),
        ({"BIORAG_RERANKING_JACCARD_ENABLED": "0"},    "Sin Re-ranking Jaccard"),
        ({"BIORAG_PPMI_WEIGHT": "0.0"},                "Sin PPMI+SVD  (weight=0.0)"),
        ({"BIORAG_DMN_IDLE_SECONDS": "999999"},        "Sin DMN  (idle=999999s)"),
    ]

    results = []
    for i, (env_ov, label) in enumerate(configs, 1):
        print(f"\n========================================================================")
        print(f" ESCENARIO [{i}/{len(configs)}]: {label}")
        print(f"========================================================================", flush=True)
        r = run_eval(env_ov, label)
        results.append(r)
        g = r["stats"].get("GLOBAL SUMMARY (Retrieval)", "?")
        print(f"\n[✔] ESCENARIO [{i}/{len(configs)}] FINALIZADO → GLOBAL Recall@5: {g}%\n", flush=True)

    # Tabla comparativa final
    baseline = results[0]["stats"]
    print("\n" + "=" * 72)
    print("  TABLA FINAL COMPARATIVA DE ABLACIÓN")
    print("=" * 72)
    print(f"  {'Mecanismo':<40} | {'GLOBAL':>9} | {'por_tema':>9} | {'sinonimo':>9}")
    print("-" * 72)

    def fmt(val, base):
        try:
            d = float(val) - float(base)
            return f"{val}% ({d:+.1f}pp)"
        except Exception:
            return f"{val}%"

    for r in results:
        lbl = r["label"][:38]
        g = r["stats"].get("GLOBAL SUMMARY (Retrieval)", "?")
        t = r["stats"].get("por_tema", "?")
        s = r["stats"].get("sinonimo", "?")
        gb = baseline.get("GLOBAL SUMMARY (Retrieval)", 0)
        tb = baseline.get("por_tema", 0)
        sb = baseline.get("sinonimo", 0)
        print(f"  {lbl:<40} | {fmt(g,gb):>18} | {fmt(t,tb):>18} | {fmt(s,sb):>18}")

    print()
    print("  (±Xpp) = delta vs baseline. Negativo = ese mecanismo contribuía positivamente.")
    print()

    out = os.path.join(BASE_DIR, "scripts", "ablacion_resultado.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  JSON guardado en: {out}")


if __name__ == "__main__":
    main()
