"""validar_fp_holdout.py — Mide el FP real con partición calibración/validación.

Responde a la auditoría v28.1 (P1): el "FP 6%" reportado era tautológico porque
`calibrar_y_persistir()` calibraba con los 32 negativos y media sobre los mismos.
Aquí se parte la muestra: la mitad calibra el umbral conforme, la otra mitad lo
valida. El FP se reporta SOLO sobre negativos que el umbral nunca vio.

Uso:
    BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/validar_fp_holdout.py

NOTA: la partición 16/16 deja k=ceil(17*0.90)=16 = el MÁXIMO de la submuestra,
el estadístico más inestable. Se reporta además el intervalo de Wilson 95% para
que se vea la fragilidad de n=16 (auditoría v28.1, P1: subir a 200-300 negativos
hace el umbral defendible).
"""

import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.calibracion import UmbralConforme

DB = os.environ.get("BIORAG_PATH", "MemoryBioRAG_Data/memory_biorag.db")


def wilson_95(positivos: int, n: int) -> tuple:
    """Intervalo de confianza de Wilson para una proporción (95%)."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = positivos / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (centro - margen, centro + margen)


def cargar_negativos(qa_path: str) -> list:
    """Devuelve las queries de categoría 'negativo' del QA baseline."""
    neg = []
    with open(qa_path, encoding="utf-8") as f:
        for line in f:
            caso = json.loads(line.strip())
            if caso.get("categoria") == "negativo" and caso.get("query"):
                neg.append(caso["query"])
    return neg


def scores_negativos(cerebro, queries: list) -> list:
    """score_hibrido crudo del top-1 para cada query negativa."""
    out = []
    for q in queries:
        res = cerebro.buscar_por_frase(q, limite=1)
        if res and res[0]:
            out.append(res[0][0][4])
    return out


def main():
    import sqlite3

    from core.memory_store import SQLiteMemoryBioRAG

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    qa_path = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")
    if not os.path.exists(qa_path):
        qa_path = os.path.join(base_dir, "scripts", "casos_qa.jsonl")

    queries = cargar_negativos(qa_path)
    print("=" * 78)
    print("VALIDACIÓN FP HELD-OUT — auditoría v28.1 (P1)")
    print(f"DB: {DB}")
    print(f"Negativos disponibles: {len(queries)}")

    cerebro = SQLiteMemoryBioRAG(DB)

    # Semilla fija para reproducibilidad
    rng = random.Random(20260816)
    rng.shuffle(queries)

    for n_cal in [24, 16]:
        n_val = len(queries) - n_cal
        cal_q = queries[:n_cal]
        val_q = queries[n_cal:]
        s_cal = scores_negativos(cerebro, cal_q)
        s_val = scores_negativos(cerebro, val_q)

        umb = UmbralConforme(alpha=0.10)
        umb.calibrar(s_cal, scores_positivos=None)

        fp = [s for s in s_val if s > umb.umbral]
        n_fp = len(fp)
        lo, hi = wilson_95(n_fp, len(s_val))

        print("-" * 78)
        print(f"Particion {n_cal} cal / {n_val} val  (alpha=0.10)")
        print(f"  umbral calibrado: {umb.umbral:.4f}  (cuantil k={math.ceil((n_cal+1)*0.90)} de {n_cal})")
        print(f"  rango negativos cal: {umb.rango_negativos[0]:.4f} - {umb.rango_negativos[1]:.4f}")
        print(f"  FP held-out: {n_fp}/{len(s_val)} = {100*n_fp/len(s_val):.1f}%")
        print(f"  Wilson 95%: [{lo:.1%}, {hi:.1%}]")

    cerebro.cerrar_sistema()
    print("=" * 78)
    print("Interpretacion: si el FP held-out supera alpha=0.10 (o su Wilson no lo")
    print("contiene), la garantia conforme NO se sostiene con la muestra actual —")
    print("hacen falta mas negativos (reales, de log_busquedas).")
    print("=" * 78)


if __name__ == "__main__":
    main()
