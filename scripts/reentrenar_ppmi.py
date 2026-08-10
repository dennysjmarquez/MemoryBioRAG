#!/usr/bin/env python3
"""Reentrenamiento FORZADO de los vectores PPMI+SVD (Signal #13) de una DB BioRAG.

Uso:
    python3 scripts/reentrenar_ppmi.py                    # DB de producción
    python3 scripts/reentrenar_ppmi.py path/a/db.db       # DB explícita
    BIORAG_PATH=path/a/db.db python3 scripts/reentrenar_ppmi.py

Fuerza el full reindex espectral (SVD 100 dims + Retrofitting Hebbiano),
regenerando las tablas `tokens` y `nodos`. NO respeta las condiciones automáticas
(≥7 días Y ≥50 nodos) del ciclo de sueño: reentrena ya.
"""
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ppmi_vectorizer import reindexar_ppmi_svd


def estado(con, etiqueta):
    try:
        tokens = con.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
    except sqlite3.OperationalError:
        tokens = 0
    nodos = con.execute("SELECT COUNT(*) FROM nodos").fetchone()[0]
    con_vec = con.execute(
        "SELECT COUNT(*) FROM nodos WHERE vector IS NOT NULL AND length(vector) > 0"
    ).fetchone()[0]
    row_ts = con.execute(
        "SELECT valor FROM data WHERE clave='ppmi_ultima_reindexacion'"
    ).fetchone()
    row_n = con.execute(
        "SELECT valor FROM data WHERE clave='ppmi_nodos_acumulados'"
    ).fetchone()
    ts = float(row_ts[0]) if row_ts else None
    fecha = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "nunca"
    acum = int(row_n[0]) if row_n else 0
    print(f"[{etiqueta}] tokens={tokens} | nodos={nodos} | con_vector={con_vec}/{nodos} "
          f"| ultima_reindex={fecha} | acumulados={acum}")


def main():
    default = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "MemoryBioRAG_Data", "memory_biorag.db",
    )
    db_path = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("BIORAG_PATH") or default)

    if not os.path.exists(db_path):
        print(f"[ERROR] Base de datos no encontrada: {db_path}")
        sys.exit(1)

    print(f"DB: {db_path}")
    con = sqlite3.connect(db_path)

    try:
        con.execute("PRAGMA journal_mode=WAL")
        estado(con, "ANTES")
        t0 = time.time()
        n = reindexar_ppmi_svd(con, dim=100, retrofit_lam=0.2, retrofit_iters=5)
        dt = time.time() - t0
        estado(con, "DESPUES")
        print(f"Vectores PPMI+SVD reentrenados: {n} nodos en {dt:.1f}s")
    finally:
        con.close()


if __name__ == "__main__":
    main()
