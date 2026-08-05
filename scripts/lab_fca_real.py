"""
Fase 2 — FCA sobre datos REALES (copia aislada, solo lectura).

Contexto: 665 conceptos (objetos) × 104 dimensiones semánticas (atributos),
proveniente de largo_plazo_dimensiones en /tmp/opencode/lab_fca.db.

Objetivo:
  1. Construir el retículo de Galois completo y medir su tamaño (conceptos,
     no-triviales, jerarquía) y el tiempo que tarda.
  2. Medir el impacto estructural REAL de las dimensiones candidatas a
     "triviales" usando impacto_atributo (retículo completo vs retículo sin
     esa dimensión), NO su frecuencia de aparición.
  3. Ranking global de impacto para todas las dimensiones.

La lección de F1 (cobertura != trivialidad) se aplica aquí: una dimensión
en 75% de los nodos puede ser informativa si estructura el retículo; una en
20% puede ser ruido. Lo decide el impacto medido, no la magnitud del número.
"""

import sys
import time
import sqlite3

from lab_fca import (
    Contexto,
    concepto_no_trivial,
    ganter_next_closure,
    impacto_atributo,
)

DB = "/tmp/opencode/lab_fca.db"

# Dimensiones candidatas a triviales (frecuencia alta en la DB real).
CANDIDATAS = [
    "intencion_documentar",
    "dominio_tecnico",
    "identidad_artificial",
    "cualidad_abstracta_conceptual",
]

# Tope de seguridad: FCA puede explotar exponencialmente en el peor caso.
CAP_CONCEPTOS = 300_000


def cargar_contexto(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT concepto
        FROM largo_plazo_dimensiones
        ORDER BY concepto
        """
    )
    objetos = [r[0] for r in cur.fetchall()]

    cur.execute(
        """
        SELECT id, name
        FROM dimensiones_semanticas
        ORDER BY id
        """
    )
    dims = cur.fetchall()
    atributos = [name for _, name in dims]
    id_a_idx = {did: i for i, (did, _) in enumerate(dims)}

    incidencia = [set() for _ in objetos]
    obj_idx = {o: i for i, o in enumerate(objetos)}
    cur.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones")
    for concepto, dim_id in cur.fetchall():
        if concepto in obj_idx and dim_id in id_a_idx:
            incidencia[obj_idx[concepto]].add(id_a_idx[dim_id])

    return Contexto(objetos, atributos, incidencia)


def correr_con_cap(ctx, etiqueta=""):
    t0 = time.time()
    conceptos = ganter_next_closure(ctx)
    t1 = time.time()
    n = len(conceptos)
    no_triviales = sum(1 for c in conceptos if concepto_no_trivial(c, len(ctx.objetos)))
    print(f"[{etiqueta or 'base'}] {n} conceptos en {t1 - t0:.2f}s, "
          f"{no_triviales} no-triviales")
    return conceptos


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ctx = cargar_contexto(conn)
    conn.close()

    n_objetos, n_atributos = len(ctx.objetos), len(ctx.atributos)
    pares = sum(len(s) for s in ctx.incidencia)
    densidad = pares / (n_objetos * n_atributos)
    print("=" * 78)
    print(f"F2 — FCA REAL: {n_objetos} objetos × {n_atributos} atributos, "
          f"{pares} pares, densidad {densidad:.1%}")
    print("=" * 78)

    conceptos = correr_con_cap(ctx, "retículo completo")
    if len(conceptos) >= CAP_CONCEPTOS:
        print("CAP alcanzado: retículo parcial, resultados no completos.")
        sys.exit(2)

    n_no_trivial = sum(
        1 for c in conceptos if concepto_no_trivial(c, n_objetos)
    )
    print(f"\nRetículo base: {len(conceptos)} conceptos, "
          f"{n_no_trivial} no-triviales (1 < |ext| < {n_objetos}).")

    print("\n--- Impacto estructural de dimensiones candidatas (con/sin) ---")
    print(f"{'dimension':<34} | {'cobertura':>9} | {'con':>5} | {'sin':>5} | {'impacto':>7} | lectura")
    print("-" * 100)
    base_no_trivial = n_no_trivial
    for nombre in CANDIDATAS:
        if nombre not in ctx.atributos:
            print(f"{nombre:<34} | (no existe en contexto)")
            continue
        m = ctx.atributos.index(nombre)
        res = impacto_atributo(ctx, conceptos, m)
        lectura = (
            "TRIVIAL estructural" if res["impacto"] == 0
            else f"informativo ({res['impacto']} concepto(s))"
        )
        print(f"{nombre:<34} | {res['cobertura']:>9.3f} | {res['conceptos_no_triviales_con']:>5} "
              f"| {res['conceptos_no_triviales_sin']:>5} | {res['impacto']:>7} | {lectura}")

    print("\n--- Ranking global de impacto (todas las dimensiones) ---")
    print(f"{'#':>3} | {'dimension':<34} | {'cobertura':>9} | {'impacto':>7}")
    print("-" * 70)
    filas = []
    sin_pares = []
    for m in range(n_atributos):
        if not ctx.objetos_con(m):
            sin_pares.append(ctx.atributos[m])
            continue
        res = impacto_atributo(ctx, conceptos, m)
        filas.append((ctx.atributos[m], res["cobertura"], res["impacto"]))
    filas.sort(key=lambda f: (-f[2], -f[1]))
    for i, (nombre, cob, imp) in enumerate(filas[:30], start=1):
        print(f"{i:>3} | {nombre:<34} | {cob:>9.3f} | {imp:>7}")

    if sin_pares:
        print(f"\nDimensiones con 0 pares en largo_plazo_dimensiones ({len(sin_pares)}):")
        print("  " + ", ".join(sin_pares))

    print("\n--- Interpretación (lo que verifiqué vs lo que interpreto) ---")
    print(f"Base: {base_no_trivial} no-triviales.")


if __name__ == "__main__":
    main()
