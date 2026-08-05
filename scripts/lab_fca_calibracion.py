"""
Calibración de escala FCA: mide tiempo y nº de conceptos para sub-contextos
crecientes (top-K dimensiones por frecuencia) de los datos reales.

Sirve para saber QUÉ sub-contexto es computable en tiempo razonable antes
de decidir la estrategia de F2/F3. FCA explota exponencialmente en el peor
caso; en datos reales hay que encontrar el punto de equilibrio.
"""

import sys
import time
import sqlite3

from lab_fca import Contexto, ganter_next_closure

DB = "/tmp/opencode/lab_fca.db"


def cargar_contexto(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT concepto FROM largo_plazo_dimensiones ORDER BY concepto")
    objetos = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id, name FROM dimensiones_semanticas ORDER BY id")
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


def top_k_atributos(ctx, k):
    freqs = [(m, len(ctx.objetos_con(m))) for m in range(len(ctx.atributos))]
    freqs.sort(key=lambda f: -f[1])
    return [m for m, _ in freqs[:k]]


def sub_contexto(ctx, atributos_mantener):
    mant = set(atributos_mantener)
    nuevos = [ctx.atributos[m] for m in range(len(ctx.atributos)) if m in mant]
    matriz = {
        ctx.objetos[g]: {ctx.atributos[m] for m in s if m in mant}
        for g, s in enumerate(ctx.incidencia)
    }
    return Contexto.desde_matriz(matriz, orden_atributos=nuevos)


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ctx = cargar_contexto(conn)
    conn.close()

    print("=" * 78)
    print("CALIBRACIÓN FCA — datos reales (copia aislada)")
    print(f"Contexto completo: {len(ctx.objetos)} obj × {len(ctx.atributos)} dims")
    print("=" * 78)

    for k in [40, 50, 60, 70, 80, 90, 104]:
        top = top_k_atributos(ctx, k)
        sub = sub_contexto(ctx, top)
        t0 = time.time()
        try:
            conceptos = ganter_next_closure(sub)
        except RecursionError:
            print(f"K={k:>2}: RecursionError (salto)")
            continue
        t1 = time.time()
        print(f"K={k:>2} | {len(sub.objetos):>4} obj × {len(sub.atributos):>2} dims | "
              f"{len(conceptos):>7} conceptos | {t1 - t0:>7.2f}s")

    print("\nHecho.")


if __name__ == "__main__":
    main()
