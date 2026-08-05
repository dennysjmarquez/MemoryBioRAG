"""
lab_fca_sugeridor_dimensiones.py — Chequeo del "sugeridor automático" (F3 renombrado)
====================================================================================
Pregunta (Dennys, 2026-08-04): para los 5 nodos esperados conocidos (fallos por_tema),
¿qué dimensión específica — de las que YA existen en el catálogo, no inventada —
movería a cada nodo desde un concepto de extensión gigante a uno fino (2-6 objetos)?

Idea de fondo: la señal "boost por pertenencia a conceptos finos" es vacía para los
nodos pobres porque sus 2-5 dimensiones son de máxima cobertura (intencion_documentar,
dominio_tecnico, identidad_artificial) y su clausura vive en extensiones 878-1087.
El retículo ya calculado puede responder: añadir dimensión d ⇒ ext(A_o ∪ {d}) cambia
la extensión del concepto que contiene al nodo. Si alguna d del catálogo baja esa
extensión a 2-6, el retículo puede SUGERIR qué dimensión le falta a un nodo pobre,
sin re-etiquetar a mano. Eso alimentaría al PRF o al Árbitro de aprender.

Métrica por nodo:
  A_o  = conjunto de dims actuales del nodo (índices)
  ext(A_o ∪ {d}) = objetos que tienen todas las dims de A_o MÁS d
  candidata_fina(d) ⟺ nodo ∈ ext(A_o ∪ {d}) y 2 <= |ext| <= 6

Si hay patrón claro y explicable en las candidatas (ej: "a estos 5 les falta una
dimensión de dominio más específica que dominio_tecnico") → enfoque funciona y se
integra. Si es ruido → Opción 2 (auditoría de calidad, sin scoring).

100% stdlib, solo lectura, determinista. Usa Contexto de lab_fca.py.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab_fca import Contexto

DB = "/tmp/opencode/lab_fca.db"

# Los 5 casos de test_sdm_collision.py con su nodo esperado (fallos por_tema)
CASOS = [
    ("operativo capa rag", "oracle_custom_prompt_arsitecura_que_funciona"),
    ("relevantes biomimética mejor", "benchmark_antes_despues_fix3"),
    ("activa largo archivos", "biorag_v11_1_detalle_tecnico"),
    ("modelo typos completa", "sin_vectores_sin_ml_sin_dependencias"),
    ("paráfrasis vectores búsqueda", "arquitectura_dos_niveles_biorag"),
]

TIPO_FINO_MIN = 2
TIPO_FINO_MAX = 6


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
    n_objs = len(ctx.objetos)
    print(f"Contexto: {n_objs} objetos × {len(ctx.atributos)} atributos")

    for query, esperado in CASOS:
        if esperado not in ctx.objetos:
            print(f"\n--- query: {query!r} → esperado '{esperado}' NO ESTÁ en la matriz")
            continue
        g = ctx.objetos.index(esperado)
        A_o = ctx.incidencia[g]
        ext_actual = ctx.extension(A_o)
        print(f"\n--- query: {query!r}  → esperado: {esperado}")
        print(f"    dims actuales ({len(A_o)}): {sorted(ctx.atributos[m] for m in A_o)}")
        print(f"    ext(A_o) actual: {len(ext_actual)}  → el nodo vive en un concepto de extensión {len(ext_actual)}")

        finas = []   # (d, |ext|, ext_contiene_esperado)
        singletons = []
        for d in range(len(ctx.atributos)):
            if d in A_o:
                continue
            ext = ctx.extension(A_o | {d})
            if TIPO_FINO_MIN <= len(ext) <= TIPO_FINO_MAX:
                finas.append((d, len(ext), esperado in ctx.objetos and g in ext))
            elif len(ext) == 1:
                singletons.append((d, len(ext)))

        if finas:
            print(f"    ✔ {len(finas)} dimensiones del catálogo mueven al nodo a concepto fino (ext {TIPO_FINO_MIN}-{TIPO_FINO_MAX}):")
            # ordenar: las que contienen al nodo primero, luego por menor ext
            finas.sort(key=lambda t: (not t[2], t[1]))
            for d, ext_n, contiene in finas[:20]:
                marca = "→ CONTIENE al esperado" if contiene else "   (no contiene)"
                print(f"      + {ctx.atributos[d]:<38} ext={ext_n:>3}  {marca}")
        else:
            print(f"    ✘ NINGUNA dimensión del catálogo produce concepto fino (ext {TIPO_FINO_MIN}-{TIPO_FINO_MAX}) que contenga al nodo")
        if singletons:
            print(f"    · {len(singletons)} dims reducen a singleton (ext=1) — trivial, no cluster")
            for d, ext_n in sorted(singletons, key=lambda t: t[1])[:6]:
                print(f"        + {ctx.atributos[d]:<38} ext=1")

        # Las mejores candidatas por menor extensión (aunque no contengan aún)
        mejores = []
        for d in range(len(ctx.atributos)):
            if d in A_o:
                continue
            ext = ctx.extension(A_o | {d})
            if len(ext) > 1:
                mejores.append((d, len(ext), g in ext))
        mejores.sort(key=lambda t: t[1])
        print(f"    · top-5 candidatas por menor extensión (>1):")
        for d, ext_n, contiene in mejores[:5]:
            print(f"        {ctx.atributos[d]:<38} ext={ext_n:>3}  {'contiene esperado' if contiene else ''}")

    conn.close()


if __name__ == "__main__":
    main()
