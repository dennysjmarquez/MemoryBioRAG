#!/usr/bin/env python3
"""test_p4_feedback.py — P4: ¿el olvido es por falta de valor o por falta de feedback?

POR QUÉ EXISTE ESTE SCRIPT
==========================
Surge de la refutación de P3 (ver docs/HACIA_DONDE_VA.md §2.5). Al verificar por qué
P3 falló, se descubrió que hay tres reglas distintas que suben el peso sináptico, y
que **leer un nodo activo no le sube el peso**. Solo lo suben:

  (a) fusión al guardar un concepto existente  (+0.20, memory_store.py:2011)
  (b) despertar un nodo dormido                (+0.15/+0.3, :1591/:4790/:5196)
  (c) feedback dopaminérgico explícito         (0.15(1-0.3w), :2454)

La (c) sólo se dispara desde mcp_server.py:2094, es decir cuando un agente llama
adrede a la herramienta de feedback.

HIPÓTESIS P4
------------
Si el peso sólo sube con feedback explícito, y el feedback rara vez se da, entonces
los nodos no se duermen por ser poco valiosos: se duermen porque **nadie cerró el
bucle de refuerzo**. Eso es una patología del bucle, no de la memoria, y se arregla
en un sitio distinto (instrumentar el feedback) que si el problema fuera el decay.

PREDICCIÓN FALSABLE (fijada ANTES de mirar los datos)
------------------------------------------------------
  P4.a  >= 80% de los nodos en estado 'dormido' tendrán exitos_dopamina == 0.
  P4.b  La mediana de exitos_dopamina en dormidos será estrictamente menor que
        en activos.
  P4.c  Existirá al menos un nodo dormido con grado sináptico >= 10 y
        exitos_dopamina == 0 (olvido estructuralmente costoso).

QUÉ LA REFUTARÍA
----------------
  - Si los dormidos tienen exitos_dopamina > 0 de forma habitual, el olvido SÍ
    discrimina por valor y P4 se cae. En ese caso el problema está en las
    constantes de decaimiento, no en el bucle de feedback.
  - Si activos y dormidos tienen la misma distribución de exitos_dopamina, el
    peso no está siendo gobernado por el refuerzo en absoluto, y habría que
    buscar la causa en inhibición lateral / homeostasis.

USO
---
    python3 scripts/test_p4_feedback.py <ruta_db>
    BIORAG_PATH=/ruta/memory_biorag.db python3 scripts/test_p4_feedback.py

NO INVENTA DATOS: si la DB no existe o le faltan columnas, falla ruidosamente en
vez de devolver ceros que se puedan confundir con un resultado válido.
"""
from __future__ import annotations

import os
import sqlite3
import statistics
import sys
from typing import List, Tuple


def _abrir(db_path: str) -> sqlite3.Connection:
    """Abre la DB en solo-lectura. Falla con mensaje claro si no existe."""
    if not os.path.exists(db_path):
        raise SystemExit(
            f"ERROR: no existe la base de datos '{db_path}'.\n"
            f"Pasa la ruta como argumento o exporta BIORAG_PATH.\n"
            f"(Este script NO simula datos: sin DB real no hay resultado.)"
        )
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _verificar_esquema(con: sqlite3.Connection) -> None:
    """Comprueba que existen las columnas necesarias antes de consultar.

    Regla del proyecto: verificar que un campo existe de verdad, no asumirlo por
    el nombre que 'debería' tener.
    """
    cols = {r[1] for r in con.execute("PRAGMA table_info(largo_plazo)")}
    faltan = {"estado", "peso_sinaptico", "exitos_dopamina"} - cols
    if faltan:
        raise SystemExit(
            f"ERROR: a la tabla largo_plazo le faltan columnas: {sorted(faltan)}.\n"
            f"Columnas presentes: {sorted(cols)}\n"
            f"Puede ser una DB anterior a la migración v20.0."
        )
    tablas = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "sinapsis" not in tablas:
        raise SystemExit("ERROR: no existe la tabla 'sinapsis'. No se puede medir P4.c.")


def ejecutar(db_path: str) -> dict:
    con = _abrir(db_path)
    _verificar_esquema(con)

    filas: List[Tuple[str, float, int, str]] = con.execute("""
        SELECT concepto, COALESCE(peso_sinaptico, 0.0),
               COALESCE(exitos_dopamina, 0), estado
        FROM largo_plazo
    """).fetchall()

    if not filas:
        raise SystemExit(
            "ERROR: largo_plazo está vacía. Corteza sin nodos != corteza fría; "
            "no se puede evaluar P4."
        )

    activos = [f for f in filas if f[3] == "activo"]
    dormidos = [f for f in filas if f[3] == "dormido"]

    if not dormidos:
        print("AVISO: no hay nodos dormidos en esta DB. P4 no es evaluable todavía "
              "(no ha habido olvido). Esto no confirma ni refuta la hipótesis.")
        return {"evaluable": False, "n_activos": len(activos), "n_dormidos": 0}

    # --- P4.a ---
    dormidos_sin_feedback = [f for f in dormidos if f[2] == 0]
    frac_a = len(dormidos_sin_feedback) / len(dormidos)

    # --- P4.b ---
    med_dorm = statistics.median([f[2] for f in dormidos])
    med_act = statistics.median([f[2] for f in activos]) if activos else float("nan")

    # --- P4.c: grado sináptico de los dormidos sin feedback ---
    grados = {}
    for origen, destino in con.execute("SELECT origen, destino FROM sinapsis"):
        grados[origen] = grados.get(origen, 0) + 1
        grados[destino] = grados.get(destino, 0) + 1

    puentes_muertos = sorted(
        [(f[0], grados.get(f[0], 0)) for f in dormidos_sin_feedback
         if grados.get(f[0], 0) >= 10],
        key=lambda x: -x[1],
    )
    con.close()

    # --- Reporte ---
    print("=" * 68)
    print("  P4 — ¿El olvido es por falta de valor o por falta de feedback?")
    print("=" * 68)
    print(f"\nDB: {db_path}")
    print(f"nodos totales: {len(filas)}  |  activos: {len(activos)}  |  dormidos: {len(dormidos)}")

    print("\n--- P4.a: ¿>=80% de los dormidos nunca recibió feedback? ---")
    print(f"  dormidos con exitos_dopamina == 0: {len(dormidos_sin_feedback)}/{len(dormidos)}"
          f"  ({100*frac_a:.1f}%)")
    print(f"  VEREDICTO: {'CONFIRMADA' if frac_a >= 0.80 else 'REFUTADA'} (umbral 80%)")

    print("\n--- P4.b: ¿la mediana de feedback es menor en dormidos? ---")
    print(f"  mediana exitos_dopamina en activos : {med_act}")
    print(f"  mediana exitos_dopamina en dormidos: {med_dorm}")
    veredicto_b = med_dorm < med_act if activos else None
    print(f"  VEREDICTO: {'CONFIRMADA' if veredicto_b else 'REFUTADA'}")

    print("\n--- P4.c: ¿hay puentes estructurales muertos sin feedback? ---")
    if puentes_muertos:
        print(f"  CONFIRMADA: {len(puentes_muertos)} nodos dormidos con grado >= 10 "
              f"y cero feedback.")
        print("  Top 10 olvidos estructuralmente costosos:")
        for c, g in puentes_muertos[:10]:
            print(f"    grado {g:>4}  {c[:60]}")
    else:
        print("  REFUTADA: ningún nodo dormido tiene grado >= 10.")

    print("\n" + "=" * 68)
    if frac_a >= 0.80:
        print("LECTURA: el olvido NO está discriminando por valor. Está")
        print("gobernado por la ausencia de feedback. El arreglo va en el bucle")
        print("de refuerzo (instrumentar/automatizar el feedback), NO en tocar")
        print("las constantes de decaimiento.")
    else:
        print("LECTURA: el feedback SÍ llega a una parte relevante de los nodos")
        print("dormidos. La hipótesis P4 no se sostiene; revisar si el olvido")
        print("está dominado por inhibición lateral u homeostasis.")
    print("=" * 68)

    return {
        "evaluable": True,
        "n_activos": len(activos),
        "n_dormidos": len(dormidos),
        "frac_dormidos_sin_feedback": round(frac_a, 4),
        "p4a_confirmada": frac_a >= 0.80,
        "mediana_activos": med_act,
        "mediana_dormidos": med_dorm,
        "p4b_confirmada": bool(veredicto_b),
        "puentes_muertos": puentes_muertos[:20],
        "p4c_confirmada": bool(puentes_muertos),
    }


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIORAG_PATH", "")
    if not ruta:
        raise SystemExit(
            "Uso: python3 scripts/test_p4_feedback.py <ruta_db>\n"
            "  o:  BIORAG_PATH=/ruta/memory_biorag.db python3 scripts/test_p4_feedback.py"
        )
    ejecutar(ruta)
