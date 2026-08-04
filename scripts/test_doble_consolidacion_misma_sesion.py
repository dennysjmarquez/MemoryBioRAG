#!/usr/bin/env python3
"""
PRUEBA 4 — Doble consolidación en la misma sesión
====================================================

Pregunta: consolidar dos veces seguidas sin cambios entre medio.
¿La segunda vez reindexa todo igual, o detecta que no hay nada nuevo?
Confirma si "reindexa todo siempre" es literal o solo pasa cuando hay
algo que consolidar.

Solo observa sobre copia. No toca código de producción.

Uso: python3 scripts/test_doble_consolidacion_misma_sesion.py
"""

import contextlib
import io
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PROD = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"
DB_TEST = Path("/tmp/opencode/test_doble_consolidacion.db")

from core.sdm import distancia_hamming  # noqa: E402


def correr_sueno(cerebro):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cerebro.ciclo_sueno_consolidacion()
    return buf.getvalue()


def main():
    DB_TEST.parent.mkdir(parents=True, exist_ok=True)
    if DB_TEST.exists():
        DB_TEST.unlink()
    src = sqlite3.connect(str(DB_PROD))
    dst = sqlite3.connect(str(DB_TEST))
    src.backup(dst)
    src.close()
    dst.close()

    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=str(DB_TEST))
    cur = cerebro.cursor

    n_corto = cur.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
    print(f"[estado] corto_plazo pendiente: {n_corto} nodos")

    vec_antes = {c: v for c, v in cur.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()}

    # ── Sueño 1 ───────────────────────────────────────────────────────
    t0 = time.perf_counter()
    salida1 = correr_sueno(cerebro)
    cerebro.conn.commit()
    t1 = time.perf_counter() - t0
    lineas_sdm1 = [l.strip() for l in salida1.splitlines() if "SDM" in l]
    print(f"\n[SUEÑO 1] {t1:.2f}s — {lineas_sdm1 or '(sin línea SDM)'}")

    vec_tras1 = {c: v for c, v in cur.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()}
    cambiados1 = sum(1 for c, v in vec_tras1.items()
                     if c in vec_antes and distancia_hamming(vec_antes[c], v) > 0)

    # ── Sueño 2 (inmediato, sin cambios entre medio) ──────────────────
    t0 = time.perf_counter()
    salida2 = correr_sueno(cerebro)
    cerebro.conn.commit()
    t2 = time.perf_counter() - t0
    lineas_sdm2 = [l.strip() for l in salida2.splitlines() if "SDM" in l]
    print(f"[SUEÑO 2] {t2:.2f}s — {lineas_sdm2 or '(sin línea SDM)'}")

    vec_tras2 = {c: v for c, v in cur.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()}
    cambiados2 = sum(1 for c, v in vec_tras2.items()
                     if c in vec_tras1 and distancia_hamming(vec_tras1[c], v) > 0)

    print(f"\n{'='*70}")
    print("RESULTADOS PRUEBA 4 — doble consolidación")
    print(f"{'='*70}")
    print(f"  Sueño 1: {t1:.2f}s, vectores cambiados: {cambiados1}")
    print(f"  Sueño 2: {t2:.2f}s, vectores cambiados: {cambiados2}")
    print()
    if lineas_sdm2 and cambiados2 == 0:
        print("  ⚠️ El sueño 2 reindexó TODO aunque 0 vectores cambiaron.")
        print("     'Reindexa todo siempre' es literal: pasa incluso sin nada nuevo.")
    elif not lineas_sdm2:
        print("  ✅ El sueño 2 no reindexó (detectó que no había nada).")
    else:
        print(f"  Sueño 2 reindexó y {cambiados2} vectores cambiaron (posible inestabilidad).")

    cerebro.cerrar_sistema()


if __name__ == "__main__":
    main()
