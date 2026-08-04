#!/usr/bin/env python3
"""
PRUEBA 2 — Propagación a vecinos: ¿se reindexa el nodo A cuando B lo referencia?
==================================================================================

Pregunta: cuando un nodo A gana un vecino nuevo porque OTRO nodo B lo
referenció (auto_vincular al aprender B), ¿el vector SDM de A se actualiza
para reflejar ese vecino nuevo?

El segmento "vecinos" (bits 1920-2047) del vector de A cambia cuando aparece
B, pero A no fue el nodo tocado — fue B. Si nadie dispara el reindex de A,
A queda con un vector de vecinos viejo indefinidamente (bug silencioso).

Metodología:
  1. Copia de la DB de producción (nunca toca producción)
  2. Elegir nodo A real, activo, con vector SDM
  3. Crear nodo B con contenido que solapa con A → auto_vincular crea B→A
  4. Consolidar B (flujo real: consolidar_concepto)
  5. Medir: ¿cambió el vector almacenado de A? ¿coincide con el fresco
     calculado a mano incluyendo B como vecino?

Solo observa. No modifica dmn_reflexion.py, memory_store.py ni sdm.py.

Uso: python3 scripts/test_reindex_propagacion_vecinos.py
"""

import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PROD = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"
DB_TEST = Path("/tmp/opencode/test_reindex_propagacion.db")

from core.sdm import distancia_hamming, generar_vector_sdm  # noqa: E402


def copiar_db():
    DB_TEST.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(DB_PROD))
    dst = sqlite3.connect(str(DB_TEST))
    src.backup(dst)
    src.close()
    dst.close()
    print(f"[setup] Copia de producción en {DB_TEST}")


def main():
    copiar_db()

    con = sqlite3.connect(str(DB_TEST))
    cur = con.cursor()

    # 1. Elegir nodo A: activo, con vector SDM y al menos 1 vecino actual
    cur.execute("""
        SELECT l.concepto, n.vector
        FROM nodos_sdm n JOIN largo_plazo l ON l.concepto = n.concepto
        WHERE l.estado = 'activo'
        ORDER BY length(l.contenido) DESC
        LIMIT 200
    """)
    candidatos = cur.fetchall()
    nodo_a, vector_a_inicial = None, None
    for concepto, vec in candidatos:
        n_vecinos = cur.execute(
            "SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?",
            (concepto, concepto)).fetchone()[0]
        if 2 <= n_vecinos <= 10 and len(vec) == 256:
            nodo_a, vector_a_inicial = concepto, vec
            break
    if not nodo_a:
        print("[ABORT] No se encontró nodo A candidato")
        return

    ts_a_inicial = cur.execute(
        "SELECT actualizado_en FROM nodos_sdm WHERE concepto = ?",
        (nodo_a,)).fetchone()[0]
    contenido_a = cur.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto = ?",
        (nodo_a,)).fetchone()[0]
    print(f"\n[PASO 1] Nodo A elegido: {nodo_a}")
    print(f"  vector inicial ts={ts_a_inicial:.2f}, vecinos={cur.execute('SELECT COUNT(*) FROM sinapsis WHERE origen=? OR destino=?', (nodo_a, nodo_a)).fetchone()[0]}")

    # 2. Contenido del nodo B: solapa fuertemente con A para forzar auto_vincular
    tokens_a = [t for t in contenido_a.split() if len(t) >= 5][:15]
    contenido_b = ("nodo de prueba propagacion vecinos " + " ".join(tokens_a))

    # 3. Flujo real: percibir_corto_plazo + auto_vincular (lo que hace aprender)
    sys.path.insert(0, str(ROOT))
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=str(DB_TEST))

    nodo_b = "zzz_test_propagacion_vecino_b"
    cerebro.percibir_corto_plazo(nodo_b, contenido_b, "", "General", {}, predicados=None, valencia_somatica=0.0)
    from core.sinapsis import auto_vincular
    enlaces = auto_vincular(cerebro, nodo_b, contenido_b)
    print(f"\n[PASO 2] Nodo B creado: {nodo_b}")
    print(f"  auto_vincular creó {len(enlaces)} sinapsis")

    # ¿Se creó sinapsis B→A o A→B?
    hay_enlace = cerebro.cursor.execute(
        "SELECT origen, destino FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
        (nodo_b, nodo_a, nodo_a, nodo_b)).fetchall()
    if not hay_enlace:
        print(f"[WARN] auto_vincular NO enlazó B con A ({nodo_a}). Sinapsis de B:")
        for o, d in cerebro.cursor.execute(
                "SELECT origen, destino FROM sinapsis WHERE origen=? OR destino=? LIMIT 10",
                (nodo_b, nodo_b)).fetchall():
            print(f"    {o} -> {d}")
        print("  Ajustar solapamiento y re-ejecutar.")
        cerebro.cerrar_sistema()
        return
    print(f"  Sinapsis entre A y B: {hay_enlace}")

    # 4. Consolidar B por el camino real (consolidar_concepto indexa SOLO B)
    ok = cerebro.consolidar_concepto(nodo_b)
    print(f"\n[PASO 3] consolidar_concepto('{nodo_b}') -> {ok}")

    # 5. Medición: ¿cambió el vector ALMACENADO de A?
    cerebro.conn.commit()
    cur = cerebro.cursor
    fila_a = cur.execute(
        "SELECT vector, actualizado_en FROM nodos_sdm WHERE concepto = ?",
        (nodo_a,)).fetchone()
    if not fila_a:
        print("[ABORT] Nodo A ya no tiene vector en nodos_sdm")
        cerebro.cerrar_sistema()
        return
    vector_a_almacenado, ts_a_final = fila_a

    dh_almacenado = distancia_hamming(vector_a_inicial, vector_a_almacenado)

    # Vector fresco de A calculado a mano CON B incluido entre vecinos
    contenido_now = cur.execute(
        "SELECT contenido, categoria FROM largo_plazo WHERE concepto = ?",
        (nodo_a,)).fetchone()
    dims = [r[0] for r in cur.execute(
        "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?",
        (nodo_a,)).fetchall()]
    vecinos_now = [r[0] for r in cur.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (nodo_a, nodo_a)).fetchall()]
    vector_a_fresco = generar_vector_sdm(
        concepto=nodo_a, contenido=contenido_now[0],
        categoria=contenido_now[1] or "", dimensiones=dims, vecinos=vecinos_now)
    dh_fresco_vs_almacenado = distancia_hamming(vector_a_fresco, vector_a_almacenado)

    print(f"\n{'='*70}")
    print("RESULTADOS PRUEBA 2 — propagación a vecinos")
    print(f"{'='*70}")
    print(f"  Nodo A: {nodo_a}")
    print(f"  Nodo B: {nodo_b} (nuevo, enlazado a A)")
    print(f"  vecinos de A ahora: {len(vecinos_now)} (incluye B: {nodo_b in vecinos_now})")
    print()
    print(f"  Hamming(A_inicial, A_almacenado): {dh_almacenado} bits")
    print(f"  Hamming(A_fresco_con_B, A_almacenado): {dh_fresco_vs_almacenado} bits")
    print(f"  timestamp A cambió: {ts_a_inicial != ts_a_final} ({ts_a_inicial:.2f} -> {ts_a_final:.2f})")
    print()
    if dh_almacenado == 0 and dh_fresco_vs_almacenado > 0:
        print("  ❌ BUG CONFIRMADO: el vector almacenado de A NO se actualizó.")
        print(f"     El vector fresco (con B incluido) difiere en {dh_fresco_vs_almacenado} bits.")
        print("     A quedó con el segmento de vecinos VIEJO. Bug silencioso.")
    elif dh_almacenado == 0 and dh_fresco_vs_almacenado == 0:
        print("  ⚠️  A no se reindexó PERO el vector fresco coincide con el almacenado.")
        print("     (B no afectó los bits — revisar si vecinos de A se saturaron)")
    else:
        print("  ✅ El vector de A SÍ se reindexó al ganar el vecino B.")

    cerebro.cerrar_sistema()
    con.close()


if __name__ == "__main__":
    main()
