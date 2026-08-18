"""retrofit_ppmi_svd.py — Retrofitting (Faruqui et al. 2015) sobre vectores
de concepto PPMI+SVD, usando la tabla `sinapsis` (tipo='sinonimo_explicito')
de la DB real como grafo relacional.

Por qué a nivel de CONCEPTO y no de TOKEN:
El paper original retrofitea vectores de PALABRA usando un lexicon
palabra-palabra (WordNet). Acá no tenemos eso — lo que tenemos es un grafo
concepto-concepto (`sinapsis`). Por eso el retrofitting se aplica sobre los
vectores de documento/concepto (promedio de vectores de token), no sobre la
matriz de tokens del modelo PPMI+SVD. La ecuación es la misma, el nodo del
grafo cambia de "palabra" a "concepto".

Fórmula (Faruqui et al. 2015, eq. 2), resuelta por Jacobi iterativo:
    q'_i^(t+1) = (alpha_i * q_i + sum_j beta_ij * q'_j^(t)) / (alpha_i + sum_j beta_ij)

- q_i: vector original (PPMI+SVD) del concepto i — el "anclaje".
- alpha_i = 1 (fijo, como en el paper).
- beta_ij = peso de la sinapsis sinonimo_explicito entre i y j (0..1 real).
- Si un concepto no tiene sinapsis sinonimo_explicito, no tiene vecinos ->
  la suma es 0 -> q'_i = q_i (queda exactamente igual que el original, sin
  degradar nada de lo que ya funcionaba). Esto es una extensión estricta,
  no un reemplazo.

Uso:
    python3 scripts/retrofit_ppmi_svd.py --iters 10
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ppmi_svd_puro_v2_suave import (  # noqa: E402
    _cargar_modelo, _tokenizar, DEFAULT_POOL, FALLOS_ID,
)

DEFAULT_VECTORS_DB = Path("/tmp/ppmi_svd_vectors_suave.db")
DEFAULT_ORIGEN_DB = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"


def cargar_vectores_originales(modelo, origen: Path) -> dict[str, np.ndarray]:
    """Vector de documento (promedio de tokens) por concepto, para TODOS
    los conceptos de largo_plazo — mismo criterio que evaluar() en
    ppmi_svd_puro_v2_suave.py, para que la comparación baseline/retrofit
    sea sobre exactamente el mismo universo."""
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    filas = con.execute("SELECT concepto, contenido FROM largo_plazo").fetchall()
    con.close()
    vecs = {}
    for concepto, contenido in filas:
        toks = _tokenizar(contenido or "")
        v, _, _ = modelo.vector_documento(toks)
        vecs[concepto] = v
    return vecs


def cargar_grafo_sinonimos(origen: Path, conceptos_validos: set, min_peso: float = 0.0) -> tuple[dict, int]:
    """Grafo no dirigido origen<->destino desde sinapsis tipo=sinonimo_explicito,
    restringido a conceptos que existen en el universo de vectores.
    min_peso filtra edges de baja confianza (ruido de la señal relacional)."""
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    filas = con.execute(
        "SELECT origen, destino, peso FROM sinapsis WHERE tipo='sinonimo_explicito'"
    ).fetchall()
    con.close()
    grafo: dict[str, list[tuple[str, float]]] = defaultdict(list)
    edges_usadas = 0
    for o, d, peso in filas:
        if peso < min_peso:
            continue
        if o in conceptos_validos and d in conceptos_validos and o != d:
            grafo[o].append((d, float(peso)))
            grafo[d].append((o, float(peso)))
            edges_usadas += 1
    return grafo, edges_usadas


def retrofit(vecs: dict[str, np.ndarray], grafo: dict, iters: int, alpha: float = 1.0,
             normalizar_por_grado: bool = False) -> dict[str, np.ndarray]:
    """Jacobi iterativo. Copia los vectores originales como punto de partida;
    solo los conceptos con al menos un vecino en el grafo se mueven.
    normalizar_por_grado=True convierte el término de vecinos de SUMA a
    PROMEDIO ponderado (beta_ij = peso_ij / grado_i), evitando que un nodo-hub
    con cientos de vecinos aplaste el ancla original (alpha=1 fijo)."""
    q = {k: v.copy() for k, v in vecs.items()}
    q_original = vecs
    for it in range(iters):
        q_next = {}
        for concepto, vecinos in grafo.items():
            if concepto not in q_original:
                continue
            suma_beta = sum(b for _, b in vecinos)
            if suma_beta <= 0:
                q_next[concepto] = q_original[concepto]
                continue
            if normalizar_por_grado:
                # promedio ponderado de vecinos, con peso relativo del ancla
                # equivalente a: alpha_efectivo = alpha * grado_i, para que
                # el ancla y "un vecino promedio" pesen parejo sin importar
                # cuantos vecinos tenga el nodo.
                grado_i = len(vecinos)
                acumulado = alpha * grado_i * q_original[concepto] + sum(
                    b * q.get(vecino, q_original[concepto]) for vecino, b in vecinos
                )
                q_next[concepto] = acumulado / (alpha * grado_i + suma_beta)
            else:
                acumulado = alpha * q_original[concepto] + sum(
                    b * q.get(vecino, q_original[concepto]) for vecino, b in vecinos
                )
                q_next[concepto] = acumulado / (alpha + suma_beta)
        for concepto in q:
            if concepto not in q_next:
                q_next[concepto] = q[concepto]
        q = q_next
    return q


def evaluar_con_vectores(modelo, vecs_candidatos: dict[str, np.ndarray]) -> dict:
    """Misma lógica de evaluar() en ppmi_svd_puro_v2_suave.py, pero usando
    un diccionario de vectores de candidato dado (original o retrofiteado)
    en vez de recomputarlos siempre desde el modelo."""
    casos = json.loads(Path(DEFAULT_POOL).read_text(encoding="utf-8"))
    casos = [c for c in casos if c["id"] in FALLOS_ID]

    resumen = {"por_tema": {"n": 0, "top1": 0, "top5": 0, "top10": 0},
               "sinonimo": {"n": 0, "top1": 0, "top5": 0, "top10": 0}}
    detalle = []
    for caso in casos:
        cat = "por_tema" if caso["categoria"] == "por_tema" else "sinonimo"
        expected = caso["expected"]
        q_toks = _tokenizar(caso["query"])
        vq = modelo.vector_tokens(q_toks)
        scores = []
        for cand in caso["pool"]:
            vn = vecs_candidatos.get(cand["concepto"])
            if vn is None:
                vn = np.zeros(modelo.dim)
            scores.append((cand["concepto"], modelo.coseno(vq, vn)))
        scores.sort(key=lambda x: -x[1])
        rank = next((i + 1 for i, (c, _) in enumerate(scores) if c == expected),
                    len(scores) + 1)
        resumen[cat]["n"] += 1
        resumen[cat]["top1"] += rank == 1
        resumen[cat]["top5"] += rank <= 5
        resumen[cat]["top10"] += rank <= 10
        detalle.append({"id": caso["id"], "categoria": cat, "expected": expected,
                         "query": caso["query"], "rank": rank})
    return {"resumen": resumen, "detalle": detalle}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vectors-db", default=str(DEFAULT_VECTORS_DB))
    ap.add_argument("--origen", default=str(DEFAULT_ORIGEN_DB))
    ap.add_argument("--iters", type=int, default=10, help="iteraciones Jacobi (paper usa 10)")
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--normalizar-grado", action="store_true",
                     help="beta_ij = peso_ij/grado_i (promedio, no suma) — evita que hubs aplasten el ancla")
    ap.add_argument("--min-peso", type=float, default=0.0, help="filtra edges con peso < este valor")
    args = ap.parse_args()

    con = sqlite3.connect(args.vectors_db)
    modelo = _cargar_modelo(con)
    con.close()

    print(f"Cargando vectores originales de documento desde {args.origen}...", file=sys.stderr)
    vecs_orig = cargar_vectores_originales(modelo, Path(args.origen))
    print(f"  {len(vecs_orig)} conceptos con vector.", file=sys.stderr)

    grafo, n_edges = cargar_grafo_sinonimos(Path(args.origen), set(vecs_orig.keys()), min_peso=args.min_peso)
    print(f"  grafo sinonimo_explicito (min_peso={args.min_peso}): {n_edges} edges usables, "
          f"{len(grafo)} conceptos con >=1 vecino.", file=sys.stderr)

    print(f"Retrofitting ({args.iters} iteraciones, alpha={args.alpha}, "
          f"normalizar_grado={args.normalizar_grado})...", file=sys.stderr)
    vecs_retro = retrofit(vecs_orig, grafo, iters=args.iters, alpha=args.alpha,
                           normalizar_por_grado=args.normalizar_grado)

    print("\n=== BASELINE (vectores originales PPMI+SVD) ===", file=sys.stderr)
    res_base = evaluar_con_vectores(modelo, vecs_orig)
    print(json.dumps(res_base["resumen"], indent=2), file=sys.stderr)

    print("\n=== RETROFIT (mismo modelo, vectores de concepto ajustados) ===", file=sys.stderr)
    res_retro = evaluar_con_vectores(modelo, vecs_retro)
    print(json.dumps(res_retro["resumen"], indent=2), file=sys.stderr)

    salida = {
        "baseline": res_base["resumen"],
        "retrofit": res_retro["resumen"],
        "params": {"iters": args.iters, "alpha": args.alpha, "n_edges": n_edges,
                   "n_conceptos_con_vecino": len(grafo)},
        "detalle_baseline": res_base["detalle"],
        "detalle_retrofit": res_retro["detalle"],
    }
    out_path = Path("/tmp/retrofit_eval.json")
    out_path.write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGuardado en {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
