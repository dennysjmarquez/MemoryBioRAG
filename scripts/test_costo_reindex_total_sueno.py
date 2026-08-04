#!/usr/bin/env python3
"""
PRUEBA 3 — Costo real de indexar_todos_sdm() en cada sueño
=============================================================

Pregunta: ¿cuánto cuesta reindexar TODO en cada sueño vs. reindexar solo
lo que cambió? No asumir — medir.

Mide sobre copia:
  1. Cuántos nodos activos hay
  2. Tiempo real de indexar_todos_sdm() completo
  3. Cuántos vectores cambiaron REALMENTE al reindexar (= cuántos estaban
     desactualizados; si 0 cambian, el reindex total fue puro gasto)
  4. Tiempo de UN indexar_nodo_sdm() promedio → estimación del costo
     selectivo (solo recuerdos_sesion + vecinos)

Solo observa sobre copia. No toca código de producción.

Uso: python3 scripts/test_costo_reindex_total_sueno.py
"""

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PROD = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"
DB_TEST = Path("/tmp/opencode/test_costo_reindex.db")

from core.sdm import distancia_hamming, indexar_nodo_sdm, indexar_todos_sdm  # noqa: E402


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

    n_activos = cur.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'").fetchone()[0]
    n_total = cur.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    n_con_vector = cur.execute("SELECT COUNT(*) FROM nodos_sdm").fetchone()[0]
    print(f"[estado] largo_plazo total: {n_total} | activos: {n_activos} | con vector SDM: {n_con_vector}")

    # 1. Snapshot de todos los vectores antes
    vec_antes = {c: v for c, v in cur.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()}

    # 2. Reindex total cronometrado
    t0 = time.perf_counter()
    n_reindexados = indexar_todos_sdm(cerebro)
    t_total = time.perf_counter() - t0
    cerebro.conn.commit()

    # 3. ¿Cuántos cambiaron de verdad?
    cambiados = 0
    no_estaban = 0
    for c, v in cur.execute("SELECT concepto, vector FROM nodos_sdm").fetchall():
        if c not in vec_antes:
            no_estaban += 1
        elif distancia_hamming(vec_antes[c], v) > 0:
            cambiados += 1
    desactualizados_pct = 100.0 * cambiados / max(1, len(vec_antes))

    # 4. Costo de UN nodo (promedio sobre 10)
    muestra = [c for c, in cur.execute(
        "SELECT concepto FROM largo_plazo WHERE estado='activo' LIMIT 10").fetchall()]
    t0 = time.perf_counter()
    for c in muestra:
        indexar_nodo_sdm(cerebro, c)
    t_unitario = (time.perf_counter() - t0) / max(1, len(muestra))

    print(f"\n{'='*70}")
    print("RESULTADOS PRUEBA 3 — costo del reindex total en cada sueño")
    print(f"{'='*70}")
    print(f"  nodos reindexados: {n_reindexados}")
    print(f"  tiempo reindex TOTAL: {t_total*1000:.1f} ms")
    print(f"  vectores que CAMBIARON de verdad: {cambiados} ({desactualizados_pct:.1f}% de los existentes)")
    print(f"  vectores nuevos (no existían): {no_estaban}")
    print(f"  tiempo de UN indexar_nodo_sdm: {t_unitario*1000:.2f} ms")
    print()
    # Estimación: sesión típica guarda ~5 nodos; vecinos afectados ~10 por nodo (fanout auto_vincular)
    for n_session in (1, 5, 20):
        estim_selectivo = n_session * (1 + 10) * t_unitario * 1000
        print(f"  estimado selectivo ({n_session} nodos sesión +10 vecinos c/u): {estim_selectivo:.1f} ms vs total {t_total*1000:.1f} ms")
    print()
    if cambiados == 0 and no_estaban == 0:
        print("  ⚠️ 0 vectores cambiaron: el reindex total de este sueño fue 100% gasto.")
    elif desactualizados_pct < 10:
        print(f"  ⚠️ Solo {desactualizados_pct:.1f}% estaba desactualizado: reindexar todo es sobre-trabajo.")
    else:
        print(f"  ✅ {desactualizados_pct:.1f}% desactualizado: el reindex total se paga solo.")

    cerebro.cerrar_sistema()


if __name__ == "__main__":
    main()
