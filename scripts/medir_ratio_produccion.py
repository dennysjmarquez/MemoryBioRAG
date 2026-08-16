#!/usr/bin/env python3
"""medir_ratio_produccion.py — El dato que falta para poder elegir el umbral.

POR QUÉ EXISTE
==============
Toda la discusión del umbral de FP quedó bloqueada en la misma pregunta:

    ¿cuántas consultas REALES tienen respuesta útil en la memoria,
     y cuántas no?

El benchmark tiene 881 positivos y 40 negativos (ratio ~22:1), pero ese ratio es un
artefacto del diseño del benchmark, no una medida de la carga real. Y de ese ratio
depende por completo cuál es el umbral correcto:

  - si casi todas las consultas tienen respuesta -> abstenerse es carísimo,
    conviene un umbral BAJO (falso positivo ocasional < perder respuestas buenas)
  - si muchas son exploratorias sin respuesta -> un umbral ALTO se justifica

Con `TP - FP` y ratio 881:32 el óptimo sale 0.25 (el actual). Con ratio 1.6:1 salía
0.78. Mismo método, conclusión opuesta: **el ratio decide, no el método.**

QUÉ MIDE
--------
La tabla `log_busquedas` (core/memory_store.py:847) registra cada consulta real con:
  query, resultados_count, top_score, creado_en, util, params_json

`util` es la señal de oro cuando existe: es feedback humano/agente explícito
(1 = la respuesta sirvió, 0 = no sirvió). Cuando falta, se estima por proxy con
`resultados_count` y `top_score`.

SALIDA
------
El ratio estimado y, con él, el coste relativo que hace falta asumir para que un
umbral dado sea óptimo. No elige el umbral: da el dato para elegirlo con criterio.

USO
    python3 scripts/medir_ratio_produccion.py <ruta_db>
    BIORAG_PATH=/ruta/memory_biorag.db python3 scripts/medir_ratio_produccion.py
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
            "Este script NO simula datos: sin DB real no hay resultado."
        )
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def ejecutar(db_path: str, umbral_actual: float = 0.25) -> dict:
    con = _abrir(db_path)

    tablas = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "log_busquedas" not in tablas:
        raise SystemExit(
            "ERROR: no existe la tabla 'log_busquedas'. Sin histórico de consultas "
            "reales no se puede medir el ratio de producción."
        )

    total = con.execute("SELECT COUNT(*) FROM log_busquedas").fetchone()[0]
    if total == 0:
        raise SystemExit(
            "ERROR: log_busquedas está vacía. Eso NO significa ratio 0: significa "
            "que no hay datos. No se puede estimar el ratio todavía."
        )

    print("=" * 68)
    print("  Ratio real de producción: ¿cuántas consultas tienen respuesta?")
    print("=" * 68)
    print(f"\nDB: {db_path}")
    print(f"consultas registradas: {total}")

    # ---------- Señal de oro: feedback explícito ----------
    con_util = con.execute(
        "SELECT COUNT(*) FROM log_busquedas WHERE util IS NOT NULL").fetchone()[0]
    print(f"\n--- Feedback explícito (columna `util`) ---")
    print(f"  consultas con `util` informado: {con_util}/{total} "
          f"({100*con_util/total:.1f}%)")

    ratio_oro = None
    if con_util > 0:
        utiles = con.execute(
            "SELECT COUNT(*) FROM log_busquedas WHERE util = 1").fetchone()[0]
        inutiles = con_util - utiles
        print(f"    útiles   (util=1): {utiles}")
        print(f"    inútiles (util=0): {inutiles}")
        if inutiles > 0:
            ratio_oro = utiles / inutiles
            print(f"    RATIO (útil:inútil) = {ratio_oro:.1f} : 1")
        else:
            print("    RATIO: no calculable (cero consultas marcadas como inútiles)")
    else:
        print("    Sin feedback explícito. Se usa el proxy de abajo.")
        print("    NOTA: esto es coherente con P4 (100% de dormidos con "
              "exitos_dopamina=0): el bucle de feedback casi nunca se cierra.")

    # ---------- Proxy: resultados_count ----------
    sin_res = con.execute(
        "SELECT COUNT(*) FROM log_busquedas WHERE resultados_count = 0").fetchone()[0]
    con_res = total - sin_res
    print(f"\n--- Proxy A: ¿devolvió algún resultado? ---")
    print(f"  con resultados: {con_res}  |  sin resultados: {sin_res}")
    if sin_res > 0:
        print(f"  RATIO (con:sin) = {con_res/sin_res:.1f} : 1")
    else:
        print("  RATIO: todas las consultas devolvieron algo "
              "(consistente con FP alto: el sistema casi nunca dice 'nada')")

    # ---------- Proxy: distribución de top_score ----------
    scores = [r[0] for r in con.execute(
        "SELECT top_score FROM log_busquedas WHERE top_score IS NOT NULL")]
    print(f"\n--- Proxy B: distribución de top_score ({len(scores)} consultas) ---")
    if scores:
        s = sorted(scores)
        n = len(s)
        print(f"  min={s[0]:.3f}  p25={s[n//4]:.3f}  mediana={statistics.median(s):.3f}  "
              f"p75={s[(3*n)//4]:.3f}  max={s[-1]:.3f}")
        for u in (0.25, 0.50, 0.70, 0.78):
            pasan = sum(1 for x in s if x >= u)
            print(f"  top_score >= {u:.2f}: {pasan}/{n} ({100*pasan/n:.1f}%)")
    else:
        print("  sin top_score registrado")

    # ---------- Qué implica para el umbral ----------
    print("\n" + "=" * 68)
    print("QUÉ IMPLICA PARA LA ELECCIÓN DEL UMBRAL")
    print("=" * 68)

    ratio = ratio_oro if ratio_oro else (con_res / sin_res if sin_res > 0 else None)
    if ratio is None:
        print("  No hay suficiente señal para estimar el ratio.")
        print("  ACCIÓN: instrumentar `util` en las consultas reales durante unos")
        print("  días. Sin ese dato, cualquier umbral es una preferencia, no una")
        print("  decisión fundamentada.")
    else:
        fuente = "feedback explícito" if ratio_oro else "proxy resultados_count"
        print(f"  Ratio estimado (por {fuente}): {ratio:.1f} consultas con "
              f"respuesta por cada una sin respuesta.")
        print()
        print("  Regla de decisión con `neto = recall - fp/ratio`:")
        print(f"  con ratio {ratio:.1f}, perder 1 punto de recall cuesta lo mismo")
        print(f"  que ganar {ratio:.1f} puntos de reducción de FP.")
        print()
        if ratio >= 10:
            print("  => Ratio ALTO: la mayoría de consultas tienen respuesta.")
            print("     Un umbral agresivo destruye más valor del que protege.")
            print("     Conviene un umbral BAJO y atacar el FP por otra vía")
            print("     (p.ej. abstención graduada, o mejorar la señal de 'no sé').")
        elif ratio >= 3:
            print("  => Ratio MEDIO: hay margen para un umbral intermedio.")
            print("     Barrer el umbral con este ratio en `test_h_corpus_umbral.py`.")
        else:
            print("  => Ratio BAJO: muchas consultas sin respuesta.")
            print("     Un umbral alto SÍ se justifica; el FP es un coste real.")

    print("\n  ADVERTENCIA: `log_busquedas` registra las consultas que el sistema")
    print("  YA recibió, que están sesgadas por cómo se usa hoy. Si el agente")
    print("  aprendió a no preguntar lo que la memoria no sabe, el ratio saldrá")
    print("  inflado. Interpretar con esa reserva.")

    con.close()
    return {"total": total, "con_util": con_util, "ratio": ratio,
            "sin_resultados": sin_res}


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIORAG_PATH", "")
    if not ruta:
        raise SystemExit(
            "Uso: python3 scripts/medir_ratio_produccion.py <ruta_db>\n"
            "  o:  BIORAG_PATH=/ruta/memory_biorag.db python3 scripts/medir_ratio_produccion.py"
        )
    ejecutar(ruta)
