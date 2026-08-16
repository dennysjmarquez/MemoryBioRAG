#!/usr/bin/env python3
"""verificar_contaminacion_log.py — ¿Los "negativos reales" son consultas de test?

POR QUÉ EXISTE
==============
El dry-run de `feedback_implicito.py` encontró 336 negativos con confianza >= 0.7.
Antes de aplicarlos hay que descartar una posibilidad que los invalidaría por
completo:

    `scripts/evaluar_qa.py:97` llama a `buscar_por_frase()`, y
    `buscar_por_frase` (memory_store.py:4857) SIEMPRE inserta en `log_busquedas`.

Es decir: **cada corrida del benchmark mete 921 filas en el log de producción.**

Durante la auditoría de v28.1 el benchmark se corrió muchas veces (baseline
snapshot, baseline live, con los 5 fixes, con umbral 0.1866, con el daemon
apagado...). Con solo 2-3 corridas ya se superan las 2.157 filas que tiene el log.

Si los 336 "negativos reales" son en realidad casos del benchmark, calibrar con
ellos sería calibrar contra el propio test — el error de metodología más clásico
que existe, y encima circular: el benchmark mide el FP con un umbral calibrado
sobre el propio benchmark.

LA PISTA QUE YA APARECIÓ
------------------------
El dry-run reportó inferencias del tipo "reformulada en 0s". Una persona o un
agente no reformula en cero segundos. Un bucle `for caso in casos_qa` sí: ejecuta
las consultas uno detrás de otro en milisegundos. Eso es la firma del benchmark.

QUÉ COMPRUEBA ESTE SCRIPT
-------------------------
  1. Cuántas queries del log coinciden EXACTAMENTE con casos de casos_qa.jsonl.
  2. Cuántas llegan en ráfagas (delta < 1s), típico de un bucle automatizado.
  3. Si hay bloques de ~921 consultas seguidas (una corrida completa).
  4. Cuántos de los 336 negativos inferidos caen en zona contaminada.

USO
    python3 scripts/verificar_contaminacion_log.py <ruta_db>
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python3 scripts/verificar_contaminacion_log.py <db>")
    db = sys.argv[1]
    if not os.path.exists(db):
        raise SystemExit(f"ERROR: no existe la DB '{db}'. Sin datos no hay análisis.")

    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

    filas = con.execute(
        "SELECT id, query, resultados_count, creado_en FROM log_busquedas "
        "ORDER BY creado_en ASC"
    ).fetchall()
    if not filas:
        raise SystemExit("ERROR: log_busquedas vacía.")

    print("=" * 72)
    print("  ¿Está el log contaminado por corridas del benchmark?")
    print("=" * 72)
    print(f"\nDB: {db}")
    print(f"filas en log_busquedas: {len(filas)}")

    # --- 1. Coincidencia exacta con casos del benchmark ---
    qa_path = os.path.join(BASE, "scripts", "casos_qa.jsonl")
    queries_qa = set()
    if os.path.exists(qa_path):
        with open(qa_path, encoding="utf-8") as fh:
            for linea in fh:
                if linea.strip():
                    try:
                        queries_qa.add(json.loads(linea).get("query", "").strip().lower())
                    except Exception:
                        continue

    print(f"\n--- 1. Coincidencia con casos_qa.jsonl ({len(queries_qa)} casos) ---")
    if queries_qa:
        coinciden = [f for f in filas if (f[1] or "").strip().lower() in queries_qa]
        pct = 100 * len(coinciden) / len(filas)
        print(f"  filas del log que son casos del benchmark: {len(coinciden)}/{len(filas)} ({pct:.1f}%)")
        if pct > 30:
            print("  *** ALERTA: el benchmark domina el log. ***")
            print("  Calibrar con estos datos = calibrar contra el propio test.")
    else:
        print("  no se encontró casos_qa.jsonl; se omite este chequeo")
        coinciden = []

    # --- 2. Ráfagas: consultas separadas por menos de 1 segundo ---
    print("\n--- 2. Ráfagas (delta < 1s = bucle automatizado, no humano) ---")
    rafaga = sum(1 for i in range(1, len(filas)) if filas[i][3] - filas[i-1][3] < 1.0)
    pct_r = 100 * rafaga / max(len(filas) - 1, 1)
    print(f"  consultas con delta < 1s respecto a la anterior: {rafaga} ({pct_r:.1f}%)")
    if pct_r > 40:
        print("  *** ALERTA: la mayoría del log son ráfagas automatizadas. ***")
        print("  Un agente/humano real no consulta cada <1s de forma sostenida.")

    # --- 3. Bloques largos seguidos (una corrida completa del benchmark) ---
    print("\n--- 3. Bloques continuos (posibles corridas del benchmark) ---")
    bloques, actual = [], 1
    for i in range(1, len(filas)):
        if filas[i][3] - filas[i-1][3] < 5.0:
            actual += 1
        else:
            if actual >= 50:
                bloques.append(actual)
            actual = 1
    if actual >= 50:
        bloques.append(actual)
    if bloques:
        print(f"  bloques de >=50 consultas seguidas: {len(bloques)}")
        print(f"  tamaños: {sorted(bloques, reverse=True)[:10]}")
        grandes = [b for b in bloques if b >= 500]
        if grandes:
            print(f"  *** {len(grandes)} bloque(s) de >=500: casi seguro corridas del benchmark ***")
    else:
        print("  sin bloques largos: el log parece de uso real")

    # --- 4. Cruce con las inferencias de feedback implícito ---
    print("\n--- 4. ¿Los negativos inferidos caen en zona contaminada? ---")
    try:
        from core.feedback_implicito import inferir_feedback
        inf = inferir_feedback(db)
        fuertes = [x for x in inf if x["confianza"] >= 0.7 and x["util"] == 0]
        ids_qa = {f[0] for f in coinciden}
        en_qa = sum(1 for x in fuertes if x["id"] in ids_qa)
        cero_seg = sum(1 for x in fuertes if "en 0s" in x["senal"])
        print(f"  negativos inferidos (conf>=0.7): {len(fuertes)}")
        if fuertes:
            print(f"    de los cuales son casos del benchmark: {en_qa} ({100*en_qa/len(fuertes):.1f}%)")
            print(f"    con señal 'reformulada en 0s':          {cero_seg} ({100*cero_seg/len(fuertes):.1f}%)")
            limpios = len(fuertes) - max(en_qa, cero_seg)
            print(f"\n  NEGATIVOS PLAUSIBLEMENTE LIMPIOS: ~{limpios}")
    except Exception as e:
        print(f"  no se pudo cruzar con feedback_implicito: {e}")

    con.close()

    print("\n" + "=" * 72)
    print("VEREDICTO")
    print("=" * 72)
    print("Si el benchmark domina el log, hay dos caminos:")
    print("  a) FILTRAR: excluir del feedback implícito las queries que coinciden")
    print("     con casos_qa.jsonl y las ráfagas de <1s.")
    print("  b) SEPARAR EN ORIGEN: que evaluar_qa.py no escriba en log_busquedas")
    print("     (flag BIORAG_NO_LOG=1), para que el log sea solo de uso real.")
    print("\nLa (b) es la correcta a largo plazo: el log de producción no debería")
    print("contener consultas de test. La (a) sirve para aprovechar lo ya acumulado.")


if __name__ == "__main__":
    main()
