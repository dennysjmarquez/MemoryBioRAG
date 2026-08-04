#!/usr/bin/env python3
"""
PRUEBA 1 — Actualizar nodo existente: ¿el vector cambia de verdad?
====================================================================

Pregunta: cuando actualizás un nodo existente (mismo nombre) vía
corto_plazo → consolidar, ¿su vector SDM queda realmente al día con el
contenido nuevo?

Hay DOS caminos de consolidación:
  A) consolidar_concepto(concepto) — consolida UN nodo (usado por interceptor)
  B) ciclo_sueno_consolidacion() — consolida TODO corto_plazo (usado por
     la tool MCP 'consolidar')

Se prueban ambos. Solo observa sobre copia. No toca código de producción.

Uso: python3 scripts/test_reindex_actualizar_existente.py
"""

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PROD = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"
DB_TEST = Path("/tmp/opencode/test_reindex_existente.db")

from core.sdm import distancia_hamming, generar_vector_sdm  # noqa: E402


def copiar_db():
    DB_TEST.parent.mkdir(parents=True, exist_ok=True)
    if DB_TEST.exists():
        DB_TEST.unlink()
    src = sqlite3.connect(str(DB_PROD))
    dst = sqlite3.connect(str(DB_TEST))
    src.backup(dst)
    src.close()
    dst.close()


def vector_fresco(cur, concepto):
    fila = cur.execute(
        "SELECT contenido, categoria FROM largo_plazo WHERE concepto = ?",
        (concepto,)).fetchone()
    if not fila:
        return None
    contenido, categoria = fila
    dims = [r[0] for r in cur.execute(
        "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?",
        (concepto,)).fetchall()]
    vecinos = [r[0] for r in cur.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (concepto, concepto)).fetchall()]
    return generar_vector_sdm(concepto, contenido, categoria or "", dims, vecinos)


def medir(cur, concepto, etiqueta, vector_prev, ts_prev):
    fila = cur.execute(
        "SELECT vector, actualizado_en FROM nodos_sdm WHERE concepto = ?",
        (concepto,)).fetchone()
    if not fila:
        print(f"  [{etiqueta}] ❌ nodo sin vector en nodos_sdm")
        return
    vec_alm, ts_alm = fila
    dh_vs_prev = distancia_hamming(vector_prev, vec_alm)
    fresco = vector_fresco(cur, concepto)
    dh_vs_fresco = distancia_hamming(fresco, vec_alm)
    print(f"  [{etiqueta}]")
    print(f"    Hamming(prev, almacenado): {dh_vs_prev} bits")
    print(f"    Hamming(fresco, almacenado): {dh_vs_fresco} bits  (0 = al día)")
    print(f"    timestamp cambió: {ts_prev != ts_alm}")
    return dh_vs_prev, dh_vs_fresco


def main():
    copiar_db()
    print(f"[setup] Copia en {DB_TEST}\n")

    con = sqlite3.connect(str(DB_TEST))
    cur = con.cursor()

    # Elegir nodo candidato: activo, con vector, contenido mediano
    fila = cur.execute("""
        SELECT l.concepto, n.vector, n.actualizado_en
        FROM nodos_sdm n JOIN largo_plazo l ON l.concepto = n.concepto
        WHERE l.estado = 'activo' AND length(l.contenido) BETWEEN 100 AND 400
        ORDER BY l.concepto LIMIT 1
    """).fetchone()
    if not fila:
        print("[ABORT] sin candidato")
        return
    nodo, vec_prev, ts_prev = fila
    contenido_original = cur.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto = ?", (nodo,)).fetchone()[0]
    print(f"[PASO 0] Nodo: {nodo}")
    print(f"  contenido original (80 chars): {contenido_original[:80]}")

    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=str(DB_TEST))

    # ── CAMINO A: consolidar_concepto ─────────────────────────────────
    print(f"\n{'='*70}\nCAMINO A: consolidar_concepto\n{'='*70}")
    contenido_nuevo = f"ACTUALIZACION-DE-PRUEBA-{int(time.time())} contenido distinto deliberado para verificar reindex"
    cerebro.percibir_corto_plazo(nodo, contenido_nuevo, "", "General", {}, predicados=None, valencia_somatica=0.0)
    ok = cerebro.consolidar_concepto(nodo)
    cerebro.conn.commit()
    cur = cerebro.cursor

    contenido_fusionado = cur.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto = ?", (nodo,)).fetchone()[0]
    tiene_fusion = "ACTUALIZACION-DE-PRUEBA" in contenido_fusionado
    print(f"  consolidar_concepto -> {ok}")
    print(f"  contenido fusionado contiene lo nuevo: {tiene_fusion}")
    medir(cur, nodo, "tras consolidar_concepto", vec_prev, ts_prev)

    # ── CAMINO B: ciclo_sueno_consolidacion (lo que usa la tool MCP) ──
    print(f"\n{'='*70}\nCAMINO B: ciclo_sueno_consolidacion (tool MCP 'consolidar')\n{'='*70}")
    # Guardar estado post-camino-A como nuevo "prev"
    fila2 = cur.execute(
        "SELECT vector, actualizado_en FROM nodos_sdm WHERE concepto = ?", (nodo,)).fetchone()
    vec_prev_b, ts_prev_b = fila2

    contenido_nuevo_2 = f"SEGUNDA-ACTUALIZACION-{int(time.time())} via ciclo de sueno"
    cerebro.percibir_corto_plazo(nodo, contenido_nuevo_2, "", "General", {}, predicados=None, valencia_somatica=0.0)

    # Capturar salida del ciclo
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cerebro.ciclo_sueno_consolidacion()
    salida = buf.getvalue()
    lineas_sdm = [l for l in salida.splitlines() if "SDM" in l]
    print(f"  ciclo_sueno corrió. Líneas SDM: {lineas_sdm}")
    cerebro.conn.commit()
    cur = cerebro.cursor

    contenido_final = cur.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto = ?", (nodo,)).fetchone()[0]
    print(f"  contenido final contiene SEGUNDA actualización: {'SEGUNDA-ACTUALIZACION' in contenido_final}")
    medir(cur, nodo, "tras ciclo_sueno", vec_prev_b, ts_prev_b)

    cerebro.cerrar_sistema()
    con.close()


if __name__ == "__main__":
    main()
