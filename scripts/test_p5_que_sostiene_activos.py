#!/usr/bin/env python3
"""test_p5_que_sostiene_activos.py — La pregunta que abre P4.b.

POR QUÉ EXISTE
==============
P4 se ejecutó contra la DB real (2026-08-15) y dio:
  P4.a CONFIRMADA  — 100% de 154 dormidos con exitos_dopamina == 0
  P4.b REFUTADA    — mediana 0 en dormidos PERO TAMBIÉN 0 en activos
  P4.c CONFIRMADA  — 97 puentes (grado >= 10) muertos sin feedback

P4.b es el resultado más informativo y el que nadie pidió. Dice que el feedback
no es raro en los dormidos: es raro en TODO el sistema.

Eso abre un agujero en el modelo de termodinamica_cortical.py. Si la mediana de
exitos_dopamina en nodos ACTIVOS también es 0, entonces el LTP dopaminérgico no
es lo que los mantiene vivos. Y como el LTD pasivo resta 0.05*d*m por ciclo de
sueño, algo tiene que estar compensándolo, o el sistema estaría vaciándose.

HIPÓTESIS EN COMPETENCIA (excluyentes, se distinguen con los datos de aquí)
---------------------------------------------------------------------------
  H1. COLAPSO EN CURSO: no hay nada que los sostenga; los activos simplemente
      aún no han muerto. Predice: distribución de peso de los activos concentrada
      cerca del umbral 0.05, y muchos ciclos de sueño acumulados.
  H2. SOSTÉN POR FUSIÓN: los activos se re-guardan (fusión +0.20) con frecuencia.
      Predice: peso alto en activos y contenido con marcas " | Actualización:".
  H3. INMUNIDAD: los activos están protegidos (valencia >= 0.8, o categoría
      Principle/Protocol, o prioridad 0/1) y por eso no reciben LTD.
      Predice: alta fracción de activos inmunes.
  H4. EL LTD CASI NO CORRE: pocos ciclos de sueño ejecutados, así que el
      decaimiento no ha tenido oportunidad de actuar.
      Predice: pocas filas en metricas_cognitivas.

QUÉ HACE ESTE SCRIPT
--------------------
Mide las cuatro y dice cuál sostiene. No asume ninguna.

USO
    python3 scripts/test_p5_que_sostiene_activos.py <ruta_db>
    BIORAG_PATH=/ruta/memory_biorag.db python3 scripts/test_p5_que_sostiene_activos.py
"""
from __future__ import annotations

import os
import sqlite3
import statistics
import sys


def _abrir(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise SystemExit(
            f"ERROR: no existe la base de datos '{db_path}'.\n"
            f"Este script NO simula datos: sin DB real no hay resultado."
        )
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _tiene(con: sqlite3.Connection, tabla: str) -> bool:
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    ).fetchone())


def ejecutar(db_path: str) -> dict:
    con = _abrir(db_path)

    cols = {r[1] for r in con.execute("PRAGMA table_info(largo_plazo)")}
    requeridas = {"estado", "peso_sinaptico", "exitos_dopamina", "contenido"}
    faltan = requeridas - cols
    if faltan:
        raise SystemExit(f"ERROR: faltan columnas en largo_plazo: {sorted(faltan)}")

    tiene_valencia = "valencia_somatica" in cols
    tiene_prioridad = "prioridad" in cols

    activos = con.execute(
        "SELECT concepto, peso_sinaptico, COALESCE(exitos_dopamina,0), contenido "
        "FROM largo_plazo WHERE estado='activo'"
    ).fetchall()

    if not activos:
        raise SystemExit(
            "ERROR: no hay nodos activos. Corteza vacía != corteza fría; "
            "si esto es real, el colapso ya ocurrió (H1 en su forma extrema)."
        )

    pesos = [a[1] or 0.0 for a in activos]
    n = len(activos)

    print("=" * 70)
    print("  P5 — ¿Qué mantiene vivos a los nodos activos, si no hay feedback?")
    print("=" * 70)
    print(f"\nDB: {db_path}")
    print(f"nodos activos: {n}")

    # ---------- Distribución de peso (discrimina H1) ----------
    pesos_ord = sorted(pesos)
    q1 = pesos_ord[n // 4]
    med = statistics.median(pesos)
    q3 = pesos_ord[(3 * n) // 4]
    cerca_muerte = sum(1 for p in pesos if p <= 0.15)
    saturados = sum(1 for p in pesos if p >= 0.95)

    print("\n--- Distribución de peso en activos (H1: colapso en curso) ---")
    print(f"  min={min(pesos):.2f}  Q1={q1:.2f}  mediana={med:.2f}  Q3={q3:.2f}  max={max(pesos):.2f}")
    print(f"  cerca del umbral de sueño (w<=0.15): {cerca_muerte}/{n} ({100*cerca_muerte/n:.1f}%)")
    print(f"  saturados (w>=0.95):                 {saturados}/{n} ({100*saturados/n:.1f}%)")
    h1 = cerca_muerte / n > 0.50
    print(f"  H1 (colapso en curso): {'PLAUSIBLE' if h1 else 'no sostenida'}")

    # ---------- Temperatura cortical ----------
    theta = sum(pesos) / n
    print(f"\n  Θ (temperatura cortical) = {theta:.3f}")
    if theta > 0.70:
        print("  -> por encima de 0.70: la homeostasis está comprimiendo pesos activamente.")
    else:
        print("  -> por debajo de 0.70: la homeostasis NO se está disparando.")

    # ---------- Fusión (H2) ----------
    con_marca = sum(1 for a in activos if a[3] and "| Actualización:" in a[3])
    print("\n--- Rastro de fusión (H2: sostén por re-guardado) ---")
    print(f"  activos con marca '| Actualización:': {con_marca}/{n} ({100*con_marca/n:.1f}%)")
    h2 = con_marca / n > 0.30
    print(f"  H2 (sostén por fusión): {'PLAUSIBLE' if h2 else 'no sostenida'}")

    # ---------- Inmunidad (H3) ----------
    print("\n--- Inmunidad al LTD (H3) ---")
    inmunes = 0
    if tiene_valencia:
        inmunes_val = con.execute(
            "SELECT COUNT(*) FROM largo_plazo WHERE estado='activo' "
            "AND COALESCE(valencia_somatica,0.0) >= 0.80"
        ).fetchone()[0]
        print(f"  por valencia_somatica >= 0.80: {inmunes_val}/{n} ({100*inmunes_val/n:.1f}%)")
        inmunes = max(inmunes, inmunes_val)
    if tiene_prioridad:
        inmunes_pri = con.execute(
            "SELECT COUNT(*) FROM largo_plazo WHERE estado='activo' AND prioridad IN (0,1)"
        ).fetchone()[0]
        print(f"  por prioridad 0/1:             {inmunes_pri}/{n} ({100*inmunes_pri/n:.1f}%)")
        inmunes = max(inmunes, inmunes_pri)
    if _tiene(con, "categories"):
        inmunes_cat = con.execute(
            "SELECT COUNT(*) FROM largo_plazo WHERE estado='activo' AND categoria IN "
            "(SELECT id FROM categories WHERE name IN ('Principle','Protocol'))"
        ).fetchone()[0]
        print(f"  por categoría Principle/Protocol: {inmunes_cat}/{n} ({100*inmunes_cat/n:.1f}%)")
        inmunes = max(inmunes, inmunes_cat)
    h3 = inmunes / n > 0.50
    print(f"  H3 (inmunidad): {'PLAUSIBLE' if h3 else 'no sostenida'}")

    # ---------- Ciclos de sueño (H4) ----------
    print("\n--- Ciclos de sueño ejecutados (H4: el LTD apenas corrió) ---")
    n_ciclos = None
    if _tiene(con, "metricas_cognitivas"):
        n_ciclos = con.execute("SELECT COUNT(*) FROM metricas_cognitivas").fetchone()[0]
        print(f"  ciclos registrados: {n_ciclos}")
        if n_ciclos:
            rango = con.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM metricas_cognitivas"
            ).fetchone()
            if rango and rango[0]:
                dias = (rango[1] - rango[0]) / 86400.0
                print(f"  abarcan {dias:.1f} días  ({n_ciclos/max(dias,1e-9):.2f} ciclos/día)")
        # Cuántos ciclos sobrevive un nodo mediano sin feedback
        ciclos_vida = (med - 0.05) / (0.05 * 1.5)
        print(f"  un nodo en la mediana (w={med:.2f}) aguanta ~{ciclos_vida:.0f} ciclos sin feedback")
    else:
        print("  tabla metricas_cognitivas ausente: no evaluable")
    h4 = bool(n_ciclos is not None and n_ciclos < 10)
    print(f"  H4 (pocos ciclos): {'PLAUSIBLE' if h4 else 'no sostenida'}")

    con.close()

    # ---------- Veredicto ----------
    print("\n" + "=" * 70)
    vivas = [nom for nom, ok in
             [("H1 colapso en curso", h1), ("H2 sostén por fusión", h2),
              ("H3 inmunidad", h3), ("H4 pocos ciclos", h4)] if ok]
    if len(vivas) == 1:
        print(f"VEREDICTO: una sola hipótesis se sostiene -> {vivas[0]}")
    elif vivas:
        print(f"VEREDICTO: varias compatibles -> {', '.join(vivas)}")
        print("Hace falta desempatar con datos temporales antes de actuar.")
    else:
        print("VEREDICTO: NINGUNA de las cuatro se sostiene.")
        print("Eso significa que el modelo de dinámica de peso está incompleto:")
        print("hay una ruta de sostén que no está en termodinamica_cortical.py.")
        print("NO tocar el bucle de feedback hasta entender qué es.")
    print("=" * 70)

    return {
        "n_activos": n, "theta": round(theta, 4), "mediana_peso": med,
        "frac_cerca_muerte": round(cerca_muerte / n, 4),
        "H1": h1, "H2": h2, "H3": h3, "H4": h4, "n_ciclos": n_ciclos,
    }


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIORAG_PATH", "")
    if not ruta:
        raise SystemExit(
            "Uso: python3 scripts/test_p5_que_sostiene_activos.py <ruta_db>"
        )
    ejecutar(ruta)
