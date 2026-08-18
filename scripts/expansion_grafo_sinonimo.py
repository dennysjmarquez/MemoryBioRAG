"""expansion_grafo_sinonimo.py — Expansión de query determinista por grafo,
usando sinapsis(tipo='sinonimo_explicito') como diccionario de sinónimos.

Motivación (ver retrofit_ppmi_svd.py y EXPERIMENTS.md hipótesis E-retrofit):
retrofitear los vectores de CONCEPTO no ayuda a `sinonimo` porque el fallo
no está en cómo se agrupan los documentos — está en que la QUERY es una sola
palabra abstracta, mal representada en un espacio SVD que solo explica 33%
de varianza. Ningún reacomodo del lado del documento arregla eso.

Esta alternativa NO toca vectores. Es grafo puro:
1. "Semillas": conceptos cuyo CONTENIDO contiene literalmente algún token
   de la query (match léxico exacto, gratis, determinista).
2. Expansión: cualquier concepto conectado a una semilla por una arista
   sinonimo_explicito recibe un boost = peso de esa arista (acumulado si
   hay varios caminos).
3. Score final = score_vectorial_original + boost_grafo. Aditivo, no
   reemplaza — así por_tema (que ya pasa el gate con el vector puro) no
   se degrada por este cambio.

Uso:
    python3 scripts/expansion_grafo_sinonimo.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ppmi_svd_puro_v2_suave import _cargar_modelo, _tokenizar, DEFAULT_POOL, FALLOS_ID  # noqa: E402

DEFAULT_VECTORS_DB = Path("/tmp/ppmi_svd_vectors_suave.db")
DEFAULT_ORIGEN_DB = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"


def cargar_indice_invertido(origen: Path) -> dict[str, set[str]]:
    """token -> conjunto de conceptos cuyo contenido contiene ese token
    literalmente (tras tokenizar igual que el resto del pipeline)."""
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    filas = con.execute("SELECT concepto, contenido FROM largo_plazo").fetchall()
    con.close()
    indice: dict[str, set[str]] = defaultdict(set)
    for concepto, contenido in filas:
        for tok in set(_tokenizar(contenido or "")):
            indice[tok].add(concepto)
    return indice


def cargar_grafo_sinonimos(origen: Path) -> dict[str, list[tuple[str, float]]]:
    con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    filas = con.execute(
        "SELECT origen, destino, peso FROM sinapsis WHERE tipo='sinonimo_explicito'"
    ).fetchall()
    con.close()
    grafo: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for o, d, peso in filas:
        grafo[o].append((d, float(peso)))
        grafo[d].append((o, float(peso)))
    return grafo


def boost_grafo_para_query(query_toks: list[str], indice: dict, grafo: dict) -> dict[str, float]:
    """Devuelve {concepto: boost_maximo} para los vecinos (1 salto) de las
    semillas encontradas por match léxico literal de la query.
    MAX, no suma: un concepto no debe ganar boost por tener muchos caminos
    débiles acumulados (efecto hub, visto en retrofit_ppmi_svd.py con nodos
    de hasta 305 vecinos) — gana por tener AL MENOS UN camino fuerte real."""
    semillas = set()
    for tok in query_toks:
        semillas |= indice.get(tok, set())
    boost: dict[str, float] = defaultdict(float)
    for semilla in semillas:
        for vecino, peso in grafo.get(semilla, []):
            if vecino in semillas:
                continue  # no boostear otra semilla, ya tiene match directo
            if peso > boost[vecino]:
                boost[vecino] = peso
    return boost


def evaluar_hibrido(modelo, vecs_orig: dict, indice: dict, grafo: dict, w_grafo: float,
                     limitar_boost_a_top_n: int | None = None) -> dict:
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
        boost = boost_grafo_para_query(q_toks, indice, grafo)

        # Score vectorial puro primero, para saber quién es "plausible".
        scores_vec = []
        for cand in caso["pool"]:
            concepto = cand["concepto"]
            vn = vecs_orig.get(concepto)
            score_vec = modelo.coseno(vq, vn) if vn is not None else 0.0
            scores_vec.append((concepto, score_vec))
        scores_vec.sort(key=lambda x: -x[1])

        if limitar_boost_a_top_n is not None:
            candidatos_boosteables = {c for c, _ in scores_vec[:limitar_boost_a_top_n]}
        else:
            candidatos_boosteables = None  # todos

        scores = []
        for concepto, score_vec in scores_vec:
            b = boost.get(concepto, 0.0)
            if candidatos_boosteables is not None and concepto not in candidatos_boosteables:
                b = 0.0  # fuera del top-N vectorial: no recibe boost, protegido de intrusos
            scores.append((concepto, score_vec + w_grafo * b))
        scores.sort(key=lambda x: -x[1])
        rank = next((i + 1 for i, (c, _) in enumerate(scores) if c == expected),
                    len(scores) + 1)
        resumen[cat]["n"] += 1
        resumen[cat]["top1"] += rank == 1
        resumen[cat]["top5"] += rank <= 5
        resumen[cat]["top10"] += rank <= 10
        detalle.append({"id": caso["id"], "categoria": cat, "expected": expected,
                         "query": caso["query"], "rank": rank,
                         "tenia_boost": expected in boost})
    return {"resumen": resumen, "detalle": detalle}


def main():
    con = sqlite3.connect(str(DEFAULT_VECTORS_DB))
    modelo = _cargar_modelo(con)
    con.close()

    print("Cargando vectores originales, índice invertido y grafo...", file=sys.stderr)
    from scripts.retrofit_ppmi_svd import cargar_vectores_originales
    vecs_orig = cargar_vectores_originales(modelo, DEFAULT_ORIGEN_DB)
    indice = cargar_indice_invertido(DEFAULT_ORIGEN_DB)
    grafo = cargar_grafo_sinonimos(DEFAULT_ORIGEN_DB)
    print(f"  {len(vecs_orig)} conceptos, {len(indice)} tokens en índice, "
          f"{sum(len(v) for v in grafo.values())//2} edges sinonimo_explicito.", file=sys.stderr)

    for w in [0.3, 0.5, 1.0, 1.5, 2.0, 3.0]:
        res = evaluar_hibrido(modelo, vecs_orig, indice, grafo, w_grafo=w)
        print(f"\n=== w_grafo={w} ===", file=sys.stderr)
        print(json.dumps(res["resumen"], indent=2), file=sys.stderr)
        if w == 1.0:
            Path("/tmp/expansion_grafo_eval.json").write_text(
                json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
