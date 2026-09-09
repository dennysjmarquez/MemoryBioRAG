#!/usr/bin/env python3
"""
scripts/ejecutar_matriz_ablacion.py

Matriz de Ablación Formal 2x2: Concept Hub × WordNet
sobre v30.2 estabilizada (B3 Strict Real + QCR 0.60 + Hubs en 5 ángulos).

Matriz:
- Run A: Hub ON  (1) | WordNet ON  (1) -> Baseline oficial v30.2
- Run B: Hub OFF (0) | WordNet ON  (1) -> Sin Concept Hub
- Run C: Hub ON  (1) | WordNet OFF (0) -> Sin WordNet
- Run D: Hub OFF (0) | WordNet OFF (0) -> Base sinérgica cero

Evalúa sobre los 921 casos de casos_qa_baseline_v1.jsonl (875 recuperación + 40 negativos + 6 ambiguos).
"""

import os
import sys
import json
import time
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get(
    "BIORAG_PATH",
    os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
)
CASOS_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
METRICS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(METRICS_DIR, exist_ok=True)

CONFIGS = [
    {"nombre": "Run A (Hub ON / WN ON)", "id": "A", "hub": "1", "wn": "1", "desc": "Baseline oficial v30.2 completo"},
    {"nombre": "Run B (Hub OFF / WN ON)", "id": "B", "hub": "0", "wn": "1", "desc": "Concept Hub desactivado, WordNet activo"},
    {"nombre": "Run C (Hub ON / WN OFF)", "id": "C", "hub": "1", "wn": "0", "desc": "Concept Hub activo, WordNet desactivado"},
    {"nombre": "Run D (Hub OFF / WN OFF)", "id": "D", "hub": "0", "wn": "0", "desc": "Ambos desactivados (baseline léxico/híbrido puro)"}
]


def ejecutar_corrida(config):
    print("\n" + "="*80)
    print(f"EJECUTANDO: {config['nombre']}")
    print(f"Descripción: {config['desc']}")
    print(f"Variables: BIORAG_HUB_ENABLED={config['hub']} | BIORAG_WORDNET_ENABLED={config['wn']}")
    print("="*80)

    env = os.environ.copy()
    env["BIORAG_HUB_ENABLED"] = config["hub"]
    env["BIORAG_WORDNET_ENABLED"] = config["wn"]
    env["BIORAG_NO_LOG"] = "1"
    env["BIORAG_PATH"] = DB_PATH
    env["BIORAG_QA_GATE"] = "0"  # Para no abortar la corrida si alguna variante cae del gate

    metrics_out = os.path.join(METRICS_DIR, f"qa_metrics_ablation_{config['id']}.json")
    env["BIORAG_QA_METRICS"] = metrics_out

    start_t = time.time()
    cmd = [sys.executable, os.path.join(BASE_DIR, "scripts", "evaluar_qa.py"), CASOS_FILE]
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    duracion = time.time() - start_t

    if proc.returncode != 0 and not os.path.exists(metrics_out):
        print(f"Error en corrida {config['id']}: {proc.stderr[:500]}")
        return None

    with open(metrics_out, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    # Copiar lista de fallos específica
    fallos_src = os.path.join(BASE_DIR, "scripts", "casos_fallidos.jsonl")
    fallos_dst = os.path.join(METRICS_DIR, f"casos_fallidos_ablation_{config['id']}.jsonl")
    if os.path.exists(fallos_src):
        with open(fallos_src, "r", encoding="utf-8") as f_in, open(fallos_dst, "w", encoding="utf-8") as f_out:
            f_out.write(f_in.read())

    metrics["duracion_segundos"] = duracion
    metrics["config"] = config
    return metrics


def main():
    print("="*80)
    print("INICIANDO MATRIZ DE ABLACIÓN 2x2: CONCEPT HUB × WORDNET (v30.2)")
    print(f"Base de datos origen: {DB_PATH}")
    print(f"Casos QA: {CASOS_FILE}")
    print("="*80)

    resultados = {}
    for cfg in CONFIGS:
        res = ejecutar_corrida(cfg)
        if res:
            resultados[cfg["id"]] = res

    # ── GENERACIÓN DEL REPORTE COMPARATIVO ──
    print("\n" + "="*80)
    print("                     MATRIZ DE ABLACIÓN — RESULTADOS GLOBALES")
    print("="*80)
    print(f"{'Variante':<25} | {'Hub':<5} | {'WN':<5} | {'R@5':<9} | {'R@1':<9} | {'MRR':<8} | {'Fallos':<8} | {'FP Rate':<8}")
    print("-" * 88)

    for cfg in CONFIGS:
        cid = cfg["id"]
        if cid not in resultados:
            continue
        g = resultados[cid]["global"]
        r5 = f"{g['recall_at_5']:.2f}%"
        r1 = f"{g['recall_at_1']:.2f}%"
        mrr = f"{g['mrr']:.4f}"
        fallos = f"{g['fallos']}"
        fp = f"{g['negativos_fp_rate']:.2f}%"
        print(f"{cfg['nombre']:<25} | {cfg['hub']:<5} | {cfg['wn']:<5} | {r5:<9} | {r1:<9} | {mrr:<8} | {fallos:<8} | {fp:<8}")

    # Guardar resumen consolidado
    resumen_file = os.path.join(METRICS_DIR, "ablation_matrix_summary.json")
    with open(resumen_file, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print("\n" + "="*80)
    print(f"Resumen consolidado guardado en: {resumen_file}")
    print("="*80)


if __name__ == "__main__":
    main()
