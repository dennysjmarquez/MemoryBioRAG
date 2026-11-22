#!/usr/bin/env python3
"""¿El ranking depende del tamaño de la base? Experimento de crecimiento controlado.

POR QUÉ existe: el usuario reportó que el comportamiento de `sinonimo` varía según
la base («las ecuaciones se han hecho con una anotación equivocada»). El motor
puntúa con pesos fijos calibrados sobre un corpus concreto. Si eso es cierto, el
mismo par consulta/nodo tiene que cambiar de puesto cuando el corpus crece.

CÓMO se aísla la variable:
  - Se conservan SIEMPRE los nodos esperados de los 61 casos `sinonimo` (el gold
    nunca desaparece; si desapareciera mediríamos otra cosa).
  - Se rellena con distractores aleatorios hasta el tamaño T.
  - Se borran las demás filas de `largo_plazo` (los triggers limpian FTS y aristas).
  - Se corre el MISMO motor, las MISMAS consultas, sin neurona (BIORAG_NEURONA=0),
    para medir el motor desnudo y no una neurona entrenada en cada corrida.

MÉTRICAS:
  - R@1 / R@5 sobre el gold.
  - `empatados`: cuántos candidatos puntúan exactamente lo mismo que el gold en la
    señal de sinónimos (el empate es lo que deja decidir a BM25).
  - `puesto`: puesto del gold (mediana), que es lo que se degrada con el corpus.

USO:
  biovenv/bin/python scripts/experimento_crecimiento_corpus.py \
      --db snapshots/qa_escape_qcr_20260811.db --tamanos 150 400 866 --semillas 1
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def cargar_casos(ruta: str, categoria: str) -> list[dict]:
    filas = [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]
    return [r for r in filas if r.get("categoria") == categoria]


def construir_db(origen: str, destino: str, conservar: set[str], total: int, semilla: int) -> int:
    """Copia la DB y deja solo `conservar` + relleno aleatorio hasta `total`."""
    shutil.copyfile(origen, destino)
    con = sqlite3.connect(destino)
    todos = [r[0] for r in con.execute("SELECT concepto FROM largo_plazo")]
    relleno = [c for c in todos if c not in conservar]
    random.Random(semilla).shuffle(relleno)
    faltan = max(0, total - len(conservar))
    quedan = set(conservar) | set(relleno[:faltan])
    borrar = [(c,) for c in todos if c not in quedan]
    con.executemany("DELETE FROM largo_plazo WHERE concepto = ?", borrar)
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    con.close()
    return n


def medir(db_path: str, casos: list[dict], categoria: str) -> dict:
    from core.memory_store import SQLiteMemoryBioRAG

    db = SQLiteMemoryBioRAG(db_path=db_path)
    puestos, r1, r5, empatados, cubierto = [], 0, 0, [], 0
    for caso in casos:
        q, esp = caso["query"], caso["concepto_esperado"]
        res, _ = db.buscar_por_frase(q, limite=50)
        ids = [r[0] for r in res]
        if esp not in ids:
            puestos.append(999)
            empatados.append(0)
            continue
        pos = ids.index(esp) + 1
        puestos.append(pos)
        cubierto += 1
        if pos == 1:
            r1 += 1
        if pos <= 5:
            r5 += 1
        try:
            empatados.append(db.contar_empatados_sinonimos(q) if hasattr(db, "contar_empatados_sinonimos") else 0)
        except Exception:
            empatados.append(0)
    n = len(casos)
    return {
        "n": n,
        "r1": r1 / n if n else 0.0,
        "r5": r5 / n if n else 0.0,
        "puesto_mediana": statistics.median(puestos) if puestos else 0,
        "puesto_media": statistics.mean(puestos) if puestos else 0,
        "fuera_top50": sum(1 for p in puestos if p == 999),
    }


def empatados_sinonimos(db_path: str, casos: list[dict]) -> list[int]:
    """Cuántos candidatos empatan a 1.0 en la señal binaria de sinónimos."""
    sys.path.insert(0, RAIZ)
    from core.fallback_simbolico import _tokenizar_normalizado

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    nodos = [(c, _tokenizar_normalizado(s or "")) for c, s in
             con.execute("SELECT concepto, COALESCE(sinonimos,'') FROM largo_plazo")]
    con.close()
    salida = []
    for caso in casos:
        toks = set(_tokenizar_normalizado(caso["query"]))
        if not toks:
            salida.append(0)
            continue
        salida.append(sum(1 for _, ts in nodos if ts and (toks & ts)))
    return salida


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=os.path.join(RAIZ, "snapshots/qa_escape_qcr_20260811.db"))
    p.add_argument("--casos", default=os.path.join(RAIZ, "scripts/casos_qa_baseline_v1.jsonl"))
    p.add_argument("--categoria", default="sinonimo")
    p.add_argument("--tamanos", type=int, nargs="+", default=[150, 400, 866])
    p.add_argument("--semillas", type=int, default=1)
    args = p.parse_args()

    casos = cargar_casos(args.casos, args.categoria)
    conservar = {c["concepto_esperado"] for c in casos}
    print(f"categoría={args.categoria}  casos={len(casos)}  gold distinto={len(conservar)}")
    print(f"corpus origen={args.db}\n")

    base_emp = empatados_sinonimos(args.db, casos)
    print(f"{'T':>6} {'sem':>4} {'R@1':>7} {'R@5':>7} {'puesto med':>11} "
          f"{'fuera50':>8} {'empatados med':>14} {'s':>5}")
    resultados = []
    for semilla in range(args.semillas):
        for T in args.tamanos:
            destino = os.path.join(tempfile.gettempdir(), f"crec_{T}_{semilla}.db")
            t0 = time.time()
            n_real = construir_db(args.db, destino, conservar, T, semilla)
            m = medir(destino, casos, args.categoria)
            emp = empatados_sinonimos(destino, casos)
            dt = time.time() - t0
            resultados.append({"T": T, "semilla": semilla, "n_real": n_real, **m,
                               "empatados_mediana": statistics.median(emp) if emp else 0})
            print(f"{n_real:>6} {semilla:>4} {m['r1']:>7.3f} {m['r5']:>7.3f} "
                  f"{m['puesto_mediana']:>11.1f} {m['fuera_top50']:>8} "
                  f"{statistics.median(emp):>14.0f} {dt:>5.0f}")
            os.remove(destino)

    print(f"\n{'—':>6} referencia corpus completo ({len(base_emp)} consultas): "
          f"empatados mediana={statistics.median(base_emp):.0f} "
          f"media={statistics.mean(base_emp):.1f} max={max(base_emp)}")

    salida = os.path.join(RAIZ, "scripts/crecimiento_corpus_resultado.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"resultado -> {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
