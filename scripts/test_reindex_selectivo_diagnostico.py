"""
Diagnóstico/validación del reindex SDM selectivo por dirty-set.
================================================================
Valida el fix implementado (sdm_dirty + reindex_selectivo_sdm + full
periódico de seguridad). Corre SIEMPRE contra una copia de la DB,
nunca contra producción.

Prueba 2 (primero — la más peligrosa): propagación a vecinos vía dirty-set.
Prueba 1: actualizar nodo existente, ¿el vector cambia de verdad?
Prueba 3: costo real de indexar_todos_sdm() (referencia del full periódico).
Prueba 4: doble consolidación sin cambios — el 2º sueño debe reindexar ~0.

Uso:  python3 scripts/test_reindex_selectivo_diagnostico.py
"""

import sys
import os
import time
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.memory_store import SQLiteMemoryBioRAG
from core.sdm import (
    generar_vector_sdm, indexar_nodo_sdm, distancia_hamming,
    limpiar_sdm_dirty, reindex_selectivo_sdm, _sdm_full_reindex_due,
)

PROD_DB = str(ROOT / "MemoryBioRAG_Data" / "memory_biorag.db")
COPY_DB = "/tmp/opencode/test_reindex_copy.db"


def hacer_copia():
    """Copia consistente de producción (backup API, maneja WAL)."""
    os.makedirs(os.path.dirname(COPY_DB), exist_ok=True)
    if os.path.exists(COPY_DB):
        os.remove(COPY_DB)
    src = sqlite3.connect(PROD_DB)
    dst = sqlite3.connect(COPY_DB)
    src.backup(dst)
    dst.close()
    src.close()


def estado_sdm(cerebro, concepto):
    """Retorna (vector_almacenado, actualizado_en) o (None, None)."""
    row = cerebro.cursor.execute(
        "SELECT vector, actualizado_en FROM nodos_sdm WHERE concepto = ?",
        (concepto,),
    ).fetchone()
    if not row:
        return None, None
    return row[0], row[1]


def vecinos_de(cerebro, concepto):
    rows = cerebro.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? "
        "UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (concepto, concepto),
    ).fetchall()
    return {r[0] for r in rows}


def vector_fresco(cerebro, concepto):
    """Vector SDM calculado a mano desde el estado ACTUAL de la DB."""
    row = cerebro.cursor.execute(
        "SELECT categoria, contenido FROM largo_plazo WHERE concepto = ?",
        (concepto,),
    ).fetchone()
    if not row:
        return None
    cat, cont = row[0] or "", row[1] or ""
    dims = [r[0] for r in cerebro.cursor.execute(
        "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?",
        (concepto,)).fetchall()]
    vecs = list(vecinos_de(cerebro, concepto))
    return generar_vector_sdm(concepto, cont, cat, dims, vecs)


# ═══════════════════════════════════════════════════════════════
# PRUEBA 2 — Propagación a vecinos (la que nadie mencionó)
# ═══════════════════════════════════════════════════════════════
def prueba_2(cerebro):
    print("=" * 66)
    print("PRUEBA 2 — Propagación a vecinos vía dirty-set")
    print("  Nodo A existe. Se crea nodo B que auto-vincula con A.")
    print("  ¿A entra al dirty-set? ¿El reindex selectivo lo refresca?")
    print("=" * 66)

    # Crear nodo A limpio (contenido distintivo)
    A = "test_reindex_vecino_a_20260803"
    contenido_a = ("arquitectura reindexacion selectiva vectores sdm propagacion "
                   "vecinos sinapticos diagnostico memoria biorag prueba dos")
    cerebro.percibir_corto_plazo(A, contenido_a, "", "Lesson")
    cerebro.consolidar_concepto(A)

    vec_a_antes, _ = estado_sdm(cerebro, A)
    print(f"  Nodo A creado: '{A}', vector almacenado: {'sí' if vec_a_antes else 'NO'}")
    # Flush: limpiar dirty dejado por el auto_vincular interno de consolidar A
    limpiar_sdm_dirty(cerebro)

    # Crear nodo B con contenido que solapa tokens con A (fuerza auto_vincular)
    B = "test_reindex_vecino_b_20260803"
    contenido_b = ("arquitectura reindexacion selectiva vectores sdm propagacion "
                   "vecinos sinapticos diagnostico memoria biorag prueba be")
    # Flujo real de "aprender": percibir + auto_vincular
    cerebro.percibir_corto_plazo(B, contenido_b, "", "Lesson")
    from core.sinapsis import auto_vincular
    enlaces = auto_vincular(cerebro, B, contenido_b)
    cerebro.conn.commit()
    print(f"  Nodo B creado: '{B}', auto_vincular creó {len(enlaces)} enlace(s)")

    vecinos_a_despues = vecinos_de(cerebro, A)
    b_es_vecino_de_a = B in vecinos_a_despues
    print(f"  Vecinos de A después: {len(vecinos_a_despues)} "
          f"({'B SÍ es vecino de A' if b_es_vecino_de_a else 'B NO vinculó con A'})")

    if not b_es_vecino_de_a:
        print("  ⚠️  B no quedó como vecino de A — auto_vincular no los unió.")
        print("      (Ajustar contenido para forzar solapamiento.) Inconcluso.")
        return

    # Contrato NUEVO: A y B deben estar en el dirty-set tras auto_vincular
    dirty = set(r[0] for r in cerebro.cursor.execute(
        "SELECT concepto FROM sdm_dirty").fetchall())
    a_en_dirty = A in dirty and B in dirty
    print(f"  Dirty-set tras auto_vincular: {len(dirty)} nodos "
          f"({'A y B presentes' if a_en_dirty else '⚠️ A/B NO en dirty-set'})")

    # Reindex selectivo: refresca A (el que ya existía) y vacía el set
    n_selectivo = reindex_selectivo_sdm(cerebro)
    restante = cerebro.cursor.execute("SELECT COUNT(*) FROM sdm_dirty").fetchone()[0]

    vec_a_despues, _ = estado_sdm(cerebro, A)
    fresco_a = vector_fresco(cerebro, A)
    dist = distancia_hamming(vec_a_despues, fresco_a) if vec_a_despues and fresco_a else -1

    print(f"  reindex_selectivo_sdm reindexó: {n_selectivo} vectores")
    print(f"  Dirty-set tras reindex: {restante} nodos")
    print(f"  Distancia vector almacenado vs fresco (con B incluido): {dist} bits")

    if a_en_dirty and dist == 0 and restante == 0:
        print("  ✅ VEREDICTO: A marcado dirty → reindex selectivo lo refrescó")
        print("     y el set quedó vacío (contrato cumplido).")
    elif a_en_dirty and dist == 0:
        print("  ⚠️  A refrescado pero el set no se vació.")
    else:
        print("  ❌ VEREDICTO: la propagación por dirty-set NO funciona.")
        print(f"     a_en_dirty={a_en_dirty}, dist={dist}, restante={restante}")


# ═══════════════════════════════════════════════════════════════
# PRUEBA 1 — Actualizar nodo existente, ¿el vector cambia?
# ═══════════════════════════════════════════════════════════════
def prueba_1(cerebro):
    print("\n" + "=" * 66)
    print("PRUEBA 1 — Actualizar nodo existente vía corto_plazo → consolidar")
    print("=" * 66)

    C = "test_reindex_actualizar_20260803"
    contenido_v1 = "primera version del contenido nodo prueba actualizacion sdm"
    cerebro.percibir_corto_plazo(C, contenido_v1, "", "Lesson")
    cerebro.consolidar_concepto(C)
    vec_v1, ts_v1 = estado_sdm(cerebro, C)
    print(f"  Nodo '{C}' creado, vector almacenado: {'sí' if vec_v1 else 'NO'}")

    # Misma clave, contenido DISTINTO
    contenido_v2 = "SEGUNDA version totalmente distinta del texto para medir reindex"
    cerebro.percibir_corto_plazo(C, contenido_v2, "", "Lesson")
    cerebro.consolidar_concepto(C)
    vec_v2, ts_v2 = estado_sdm(cerebro, C)

    contenido_db = cerebro.cursor.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto = ?", (C,)).fetchone()[0]
    fresco = vector_fresco(cerebro, C)
    dist_vs_fresco = distancia_hamming(vec_v2, fresco) if vec_v2 and fresco else -1
    dist_v1_v2 = distancia_hamming(vec_v1, vec_v2) if vec_v1 and vec_v2 else -1

    print(f"  Contenido en DB tras 2da consolidación incluye v2: "
          f"{'sí' if contenido_v2 in contenido_db else 'NO'}")
    print(f"  actualizado_en cambió: {'SÍ' if ts_v2 != ts_v1 else 'NO'}")
    print(f"  Distancia vector_v1 vs vector_v2: {dist_v1_v2} bits")
    print(f"  Distancia vector_v2 vs fresco (calculado a mano): {dist_vs_fresco} bits")

    if dist_vs_fresco == 0 and dist_v1_v2 > 0:
        print("  ✅ VEREDICTO: consolidar_concepto SÍ reindexa el nodo actualizado")
        print("     (vector cambió y quedó al día con el contenido nuevo).")
    elif dist_v1_v2 == 0:
        print("  ❌ VEREDICTO: el vector NO cambió pese al contenido nuevo.")
    else:
        print(f"  ⚠️  VEREDICTO AMBIGUO: dist_vs_fresco={dist_vs_fresco}.")


# ═══════════════════════════════════════════════════════════════
# PRUEBA 3 — Costo real de indexar_todos_sdm()
# ═══════════════════════════════════════════════════════════════
def prueba_3(cerebro):
    print("\n" + "=" * 66)
    print("PRUEBA 3 — Costo real de indexar_todos_sdm() en cada sueño")
    print("=" * 66)

    n_activos = cerebro.cursor.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'").fetchone()[0]
    n_con_sdm = cerebro.cursor.execute("SELECT COUNT(*) FROM nodos_sdm").fetchone()[0]

    # Cuántos ya están al día vs cuántos están desactualizados AHORA
    al_dia = 0
    desactualizados = 0
    sin_vector = 0
    conceptos = [r[0] for r in cerebro.cursor.execute(
        "SELECT concepto FROM largo_plazo WHERE estado = 'activo'").fetchall()]
    for c in conceptos:
        vec, _ = estado_sdm(cerebro, c)
        if vec is None:
            sin_vector += 1
            continue
        fresco = vector_fresco(cerebro, c)
        if fresco and distancia_hamming(vec, fresco) == 0:
            al_dia += 1
        else:
            desactualizados += 1

    print(f"  Nodos activos: {n_activos} | con vector SDM: {n_con_sdm}")
    print(f"  YA al día (vector == fresco): {al_dia}")
    print(f"  Desactualizados genuinos: {desactualizados}")
    print(f"  Sin vector: {sin_vector}")

    t0 = time.time()
    n_reindex = 0
    for c in conceptos:
        if indexar_nodo_sdm(cerebro, c):
            n_reindex += 1
    t_total = time.time() - t0
    print(f"  indexar_todos: {n_reindex} nodos en {t_total:.3f}s "
          f"({t_total/n_activos*1000:.2f} ms/nodo)")
    print(f"  Si solo se reindexaran los {desactualizados} desactualizados: "
          f"~{desactualizados*(t_total/n_activos):.3f}s")


# ═══════════════════════════════════════════════════════════════
# PRUEBA 4 — Doble consolidación sin cambios
# ═══════════════════════════════════════════════════════════════
def prueba_4(cerebro):
    print("\n" + "=" * 66)
    print("PRUEBA 4 — Doble consolidación sin cambios")
    print("  Sueño 1: full periódico (registra meta). Sueño 2: selectivo.")
    print("  Con corto_plazo vacío, el sueño 2 debe reindexar 0 vectores.")
    print("=" * 66)

    # Limpiar corto_plazo para que la consolidación no tenga nada nuevo
    cerebro.cursor.execute("DELETE FROM corto_plazo")
    cerebro.cursor.execute("DELETE FROM corto_plazo_dimensiones")
    cerebro.cursor.execute("DELETE FROM corto_plazo_predicados")
    cerebro.conn.commit()

    import io, contextlib

    # Sueño 1 — primera vez en esta copia: meta vacía → full reindex
    print("  Sueño 1 (corto_plazo vacío)...")
    with contextlib.redirect_stdout(io.StringIO()):
        cerebro.ciclo_sueno_consolidacion()
    due_1 = _sdm_full_reindex_due(cerebro)
    print(f"  Tras sueño 1 — full_reindex_due: {due_1} "
          f"(esperado False: la meta quedó registrada)")

    # Sueño 2 — meta presente → camino selectivo con dirty-set vacío
    conceptos = [r[0] for r in cerebro.cursor.execute(
        "SELECT concepto FROM nodos_sdm").fetchall()]
    ts_antes = {c: cerebro.cursor.execute(
        "SELECT actualizado_en FROM nodos_sdm WHERE concepto = ?", (c,)).fetchone()[0]
        for c in conceptos}

    print("  Sueño 2 (corto_plazo vacío)...")
    with contextlib.redirect_stdout(io.StringIO()):
        cerebro.ciclo_sueno_consolidacion()

    cambiados = 0
    for c in conceptos:
        row = cerebro.cursor.execute(
            "SELECT actualizado_en FROM nodos_sdm WHERE concepto = ?", (c,)).fetchone()
        if row and row[0] != ts_antes.get(c):
            cambiados += 1

    print(f"  Vectores con actualizado_en cambiado en sueño 2: {cambiados}/{len(conceptos)}")
    if cambiados == 0:
        print("  ✅ VEREDICTO: sueño sin cambios → reindex selectivo reindexa 0.")
    elif cambiados <= 3:
        print(f"  ⚠️  PARCIAL: reindexó {cambiados} (posible auto-clustering).")
    else:
        print("  ❌ VEREDICTO: sigue reindexando masivamente sin cambios.")


def main():
    print("Haciendo copia fresca de producción...")
    hacer_copia()
    cerebro = SQLiteMemoryBioRAG(db_path=COPY_DB)
    print(f"Copia abierta: {COPY_DB}\n")

    prueba_2(cerebro)
    prueba_1(cerebro)
    prueba_3(cerebro)
    prueba_4(cerebro)

    print("\n" + "=" * 66)
    print("DIAGNÓSTICO COMPLETO — todo contra copia, producción intacta.")
    print("=" * 66)
    cerebro.conn.close()


if __name__ == "__main__":
    main()
