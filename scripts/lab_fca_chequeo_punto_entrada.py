"""
Chequeo puntual (Opción 2 afilada, pedido por Dennys vía canal 2026-08-04):
¿la query puede aterrizar en un concepto fino del retículo FCA?

Replica el PRF dimensional de producción (core/memory_store.py L3782-3795)
sobre los 5 casos reales de test_sdm_collision.py:
  - FTS5 match con la query cruda (sin paráfrasis), igual que en producción.
  - top-5 conceptos FTS5 → dimensiones DISTINCT de esos conceptos.
  - Sobre el retículo de Galois calculado: ¿qué extensión tiene el conjunto
    de dimensiones extraídas? ¿es un concepto fino (ext 2-6) que contiene al
    nodo esperado, o un concepto grande genérico?

NO construye la señal. Solo verifica el punto de entrada: si el PRF nunca
aterriza en conceptos finos, la señal está condenada antes de construirla.
"""

import re
import sys
import sqlite3

sys.path.insert(0, "scripts")
from lab_fca import Contexto, ganter_next_closure, concepto_no_trivial

DB = "/tmp/opencode/lab_fca.db"

TEST_CASES = [
    {"query": "operativo capa rag", "expected": "oracle_custom_prompt_arsitecura_que_funciona"},
    {"query": "relevantes biomimética mejor", "expected": "benchmark_antes_despues_fix3"},
    {"query": "activa largo archivos", "expected": "biorag_v11_1_detalle_tecnico"},
    {"query": "modelo typos completa", "expected": "sin_vectores_sin_ml_sin_dependencias"},
    {"query": "paráfrasis vectores búsqueda", "expected": "arquitectura_dos_niveles_biorag"},
]


def _fts_safe_term(t):
    return " ".join(p for p in re.split(r"[-]+", t) if p)


def _fts_safe_phrase(p):
    return " ".join(_fts_safe_term(t) for t in p.split())


def construir_fts_match(frase):
    """Mismo mapeo que producción (sin parafrasis_list ni modo_estricto)."""
    frase = _fts_safe_phrase(frase)
    if len(frase.split()) > 1:
        return " OR ".join(frase.split())
    return frase


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
    return Contexto(objetos, atributos, incidencia), id_a_idx


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ctx, id_a_idx = cargar_contexto(conn)
    cur = conn.cursor()
    conceptos = ganter_next_closure(ctx)
    idx_objeto = {o: i for i, o in enumerate(ctx.objetos)}

    # Mapa: (frozenset de índices de dims) -> lista de conceptos no-triviales
    # Y: para cada query, el concepto más fino que contiene al esperado.
    no_triviales = [c for c in conceptos if concepto_no_trivial(c, len(ctx.objetos))]

    print("=" * 90)
    print("CHECQUEO PUNTO DE ENTRADA — ¿la query aterriza en concepto fino?")
    print("=" * 90)

    for caso in TEST_CASES:
        q = caso["query"]
        esperado = caso["expected"]
        print(f"\n--- query: '{q}'  → esperado: {esperado}")

        # 1. FTS5 top-5 (igual que producción, sin paráfrasis)
        fts_match = construir_fts_match(q)
        sql = """
            SELECT l.rowid, l.concepto
            FROM largo_plazo_fts f
            CROSS JOIN largo_plazo l ON l.rowid = f.rowid
            WHERE largo_plazo_fts MATCH ?
              AND l.estado = 'activo'
            ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico)
            LIMIT 5
        """
        try:
            cur.execute(sql, (fts_match,))
            fts5_conceptos = [r[1] for r in cur.fetchall()]
        except sqlite3.OperationalError as e:
            print(f"   FTS5 error: {e}")
            continue

        print(f"   fts_match='{fts_match}'")
        print(f"   top-5 FTS5: {fts5_conceptos}")

        if len(fts5_conceptos) < 3:
            print(f"   → PRF NO SE ACTIVA (len FTS5 < 3). Gate en producción no dispara.")
            continue

        # 2. PRF: dimensiones DISTINCT de top-5
        ph = ",".join("?" for _ in fts5_conceptos)
        cur.execute(
            f"SELECT DISTINCT dimension_id FROM largo_plazo_dimensiones WHERE concepto IN ({ph})",
            fts5_conceptos,
        )
        pseudo_dims_ids = [r[0] for r in cur.fetchall()]
        pseudo_dims = [ctx.atributos[id_a_idx[d]] for d in pseudo_dims_ids if d in id_a_idx]
        print(f"   dims extraídas por PRF ({len(pseudo_dims)}): {pseudo_dims}")

        # 3. En el retículo: extensión de esa combinación exacta de dims
        if pseudo_dims:
            idx_dims = {ctx.atributos.index(d) for d in pseudo_dims}
            ext = ctx.extension(idx_dims)
            print(f"   extensión exacta de {len(pseudo_dims)} dims: {len(ext)} objetos")
            if esperado in idx_objeto and idx_objeto[esperado] in ext:
                print(f"   → contiene al esperado ✓ (pero ¿fino o genérico?)")
            else:
                print(f"   → NO contiene al esperado ✗")

            # 4. Todos los conceptos que contienen al esperado, con su tamaño
            #    ¿el esperado vive en conceptos finos (ext 2-6) o solo genéricos?
            if esperado in idx_objeto:
                g = idx_objeto[esperado]
                conc_esperado = [c for c in no_triviales if g in c.extension]
                conc_esperado.sort(key=lambda c: len(c.extension))
                finos = [c for c in conc_esperado if len(c.extension) <= 6]
                grandes = [c for c in conc_esperado if len(c.extension) > 30]
                print(f"   conceptos no-triviales que contienen al esperado: {len(conc_esperado)}")
                print(f"     finos (ext<=6): {len(finos)} | grandes (ext>30): {len(grandes)}")
                if finos:
                    c = finos[0]
                    ints = [ctx.atributos[m] for m in c.intencion]
                    print(f"     el más fino: ext={len(c.extension)} | intención={ints}")
                    print(f"       → ¿las dims del PRF (primeras 3) están en esta intención? "
                          f"{[d for d in pseudo_dims[:3] if d in ints]}")
                else:
                    print(f"     → ¡el esperado NO está en NINGÚN concepto fino! "
                          f"Solo genéricos.")

            # 5. ¿Cuál es el concepto MÁS FINO alcanzable por las dims del PRF?
            #    Es decir: clausura de las dims → ¿qué extensión tiene?
            claus = ctx.clausura_intencion(idx_dims)
            ext_claus = ctx.extension(claus)
            ints_claus = [ctx.atributos[m] for m in claus]
            print(f"   clausura de dims PRF → concepto ext={len(ext_claus)} | intención={ints_claus}")
            if len(ext_claus) <= 6:
                print(f"   → ¡aterriza en concepto FINO! (ext={len(ext_claus)})")
            else:
                print(f"   → aterriza en concepto GENÉRICO (ext={len(ext_claus)})")

    conn.close()
    print("\n" + "=" * 90)
    print("FIN CHECQUEO")


if __name__ == "__main__":
    main()
