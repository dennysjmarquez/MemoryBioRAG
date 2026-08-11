#!/usr/bin/env python3
"""
medir_gaba_activacion.py — Medición empírica y reproducible de la activación GABA

Mide la frecuencia exacta con la que la inhibición lateral GABA (Edelman 1987)
se dispara (Top-1 score >= 0.80) y cuántas veces atenúa competidores (score < top*0.70)
sobre los 881 casos de búsqueda del benchmark Cranfield en el snapshot congelado.

Uso:
    python3 scripts/medir_gaba_activacion.py

Salida:
    - Impresión en consola de la tabla de resultados.
    - Artefacto JSON en scripts/gaba_activacion_resultado.json
"""
import os
import sys
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG

SNAPSHOT = os.path.join(BASE_DIR, "scripts", "snapshot_prf_real.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
OUT_JSON = os.path.join(BASE_DIR, "scripts", "gaba_activacion_resultado.json")


def main():
    if not os.path.exists(SNAPSHOT):
        print(f"Snapshot no encontrado en {SNAPSHOT}. Auto-generando desde fuentes...")
        from scripts.generar_snapshot import main as gen_snap
        gen_snap()

    if not os.path.exists(CASES_FILE):
        print(f"ERROR: Casos QA no encontrados en {CASES_FILE}")
        sys.exit(1)

    db = SQLiteMemoryBioRAG(db_path=SNAPSHOT)

    with open(CASES_FILE, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    # Filtrar categoría 'negativo' (ruido out-of-domain)
    retrieval_cases = [c for c in cases if c.get("categoria") != "negativo"]

    gaba_activados = 0
    gaba_inactivos = 0
    atenuaciones_efectivas = 0
    por_categoria = {}

    for c in retrieval_cases:
        cat = c.get("categoria", "desconocida")
        if cat not in por_categoria:
            por_categoria[cat] = {"total": 0, "activados": 0, "atenuaciones": 0}

        por_categoria[cat]["total"] += 1
        query = c.get("query", "")

        # Ejecutar búsqueda
        res, _ = db.buscar_por_frase(query, limite=5)

        if res and res[0][4] >= 0.80:
            gaba_activados += 1
            por_categoria[cat]["activados"] += 1

            top_score = res[0][4]
            # Verificar si hubo al menos un competidor atenuado (score < top_score * 0.70)
            hubo_atenuacion = any(sc < top_score * 0.70 for conc, cont, peso, est, sc, asoc in res[1:])
            if hubo_atenuacion:
                atenuaciones_efectivas += 1
                por_categoria[cat]["atenuaciones"] += 1
        else:
            gaba_inactivos += 1

    total_busquedas = len(retrieval_cases)
    pct_activados = (gaba_activados / total_busquedas) * 100
    pct_atenuados = (atenuaciones_efectivas / total_busquedas) * 100

    reporte = {
        "snapshot": SNAPSHOT,
        "total_casos_busqueda": total_busquedas,
        "gaba_activados_top1_ge_80": gaba_activados,
        "gaba_inactivos_top1_lt_80": gaba_inactivos,
        "porcentaje_activados": round(pct_activados, 2),
        "atenuaciones_efectivas_competidores": atenuaciones_efectivas,
        "porcentaje_atenuaciones_efectivas": round(pct_atenuados, 2),
        "desglose_por_categoria": por_categoria
    }

    # Imprimir reporte limpio en pantalla
    print("=" * 72)
    print("  MEDICIÓN DE ACTIVACIÓN DE INHIBICIÓN LATERAL GABA (881 CASOS)")
    print("=" * 72)
    print(f"  Snapshot DB                    : {os.path.basename(SNAPSHOT)}")
    print(f"  Total Consultas de Búsqueda    : {total_busquedas}")
    print(f"  GABA Activado (Top-1 >= 0.80)  : {gaba_activados} / {total_busquedas} ({pct_activados:.2f}%)")
    print(f"  GABA Inactivo (Top-1 < 0.80)   : {gaba_inactivos} / {total_busquedas} ({100-pct_activados:.2f}%)")
    print(f"  Atenuaciones a Competidores   : {atenuaciones_efectivas} / {total_busquedas} ({pct_atenuados:.2f}%)")
    print("-" * 72)
    print(f"  {'Categoría':<22} | {'Total':<7} | {'GABA Activado':<15} | {'% Act.':<8}")
    print("-" * 72)

    for cat_name, d in sorted(por_categoria.items()):
        cnt = d["total"]
        act = d["activados"]
        pct = (act / cnt * 100) if cnt > 0 else 0
        print(f"  {cat_name:<22} | {cnt:<7} | {act:<15} | {pct:>6.2f}%")

    print("=" * 72)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print(f"\n  [✔] Artefacto JSON verificado y guardado en: {OUT_JSON}\n")


if __name__ == "__main__":
    main()
