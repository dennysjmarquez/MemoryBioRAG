"""
Exploración semántica de los conceptos no-triviales del retículo real.

La métrica estructural (impacto) ya dijo qué dimensiones sostienen el retículo.
Ahora la pregunta es de utilidad: los conceptos no-triviales (extensiones de
2..664 nodos) ¿forman clusters temáticamente coherentes, o son solo
intersecciones de dimensiones sin significado?

Para cada concepto se listan algunos objetos de su extensión: si los nombres
comparten tema (ej. 'lección de x', 'proyecto y'), el cluster sirve como señal
por_tema; si son mezcla arbitraria, es ruido estructural.
"""

import sqlite3
import random
import sys

from lab_fca import Contexto, ganter_next_closure, concepto_no_trivial

DB = "/tmp/opencode/lab_fca.db"
random.seed(42)


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


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ctx = cargar_contexto(conn)
    conn.close()

    conceptos = ganter_next_closure(ctx)
    no_triviales = [c for c in conceptos if concepto_no_trivial(c, len(ctx.objetos))]

    # Ordenar por tamaño de extensión descendente para ver clusters grandes
    no_triviales.sort(key=lambda c: -len(c.extension))

    print(f"Retículo: {len(conceptos)} conceptos, {len(no_triviales)} no-triviales")
    print(f"Tamaños de extensión de no-triviales: "
          f"min={len(no_triviales[-1].extension)}, "
          f"p50={no_triviales[len(no_triviales)//2].extension.__len__()}, "
          f"max={len(no_triviales[0].extension)}")
    print("=" * 78)

    print("--- Top 12 clusters más grandes (extensión) ---")
    for c in no_triviales[:12]:
        ints = sorted(ctx.atributos[m] for m in c.intencion)
        muestra = [ctx.objetos[g] for g in random.sample(sorted(c.extension), min(6, len(c.extension)))]
        print(f"\next={len(c.extension):>3} | intención={ints}")
        for o in muestra:
            print(f"   · {o[:80]}")

    print("\n" + "=" * 78)
    print("--- Muestra aleatoria de clusters medianos (ext 3-8) ---")
    medianos = [c for c in no_triviales if 3 <= len(c.extension) <= 8]
    for c in random.sample(medianos, min(10, len(medianos))):
        ints = sorted(ctx.atributos[m] for m in c.intencion)
        muestra = [ctx.objetos[g] for g in sorted(c.extension)]
        print(f"\next={len(c.extension):>3} | intención={ints}")
        for o in muestra:
            print(f"   · {o[:80]}")


if __name__ == "__main__":
    main()
