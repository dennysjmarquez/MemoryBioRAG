#!/usr/bin/env python3
"""Barrido del extra de sinónimos sobre la base VIVA, solo categorías de riesgo.

POR QUÉ existe: la QA completa sobre la base viva tarda ~13 min por corrida y el
`[GATE]` mira 8 categorías. Antes de gastar eso, este script barre el parámetro
sobre las categorías que el cambio puede tocar (`sinonimo`, `por_tema`,
`ambiguo`) y sobre un negativo de control, con el MISMO protocolo del arnés
(`profundidad='activos'`, `limite=5`).

El piso de sinónimos ya no se reparte (eso empeoró, medido): aquí se mide el
extra que se SUMA encima, en logit.

USO:
  biovenv/bin/python scripts/barrido_bonus_sinonimos.py --db /tmp/viva.db \
      --valores 0 0.5 1.0 2.0 3.0 --categorias sinonimo por_tema
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.setdefault("BIORAG_NO_LOG", "1")


def cargar_casos(categorias: list[str]) -> list[dict]:
    ruta = os.path.join(RAIZ, "scripts/casos_qa_baseline_v1.jsonl")
    filas = [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]
    return [r for r in filas if r.get("categoria") in categorias]


def medir(ruta_db: str, casos: list[dict]) -> dict:
    from core.memory_store import SQLiteMemoryBioRAG

    db = SQLiteMemoryBioRAG(db_path=ruta_db)
    por_cat: dict[str, dict] = {}
    for caso in casos:
        cat = caso["categoria"]
        m = por_cat.setdefault(cat, {"n": 0, "r1": 0, "r5": 0, "fallos": 0, "mrr": 0.0})
        m["n"] += 1
        res, _ = db.buscar_por_frase(
            caso["query"], profundidad="activos", limite=5, ignore_peso_sinaptico=True
        )
        ids = [r[0] for r in res]
        esp = caso["concepto_esperado"]
        if esp not in ids:
            m["fallos"] += 1
            continue
        pos = ids.index(esp) + 1
        m["r5"] += 1
        m["r1"] += pos == 1
        m["mrr"] += 1.0 / pos
    for m in por_cat.values():
        n = m["n"]
        m["r1"] = m["r1"] / n
        m["r5"] = m["r5"] / n
        m["mrr"] = m["mrr"] / n
    return por_cat


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="/tmp/viva.db")
    p.add_argument("--valores", type=float, nargs="+", default=[0, 0.5, 1.0, 2.0, 3.0])
    p.add_argument("--categorias", nargs="+", default=["sinonimo", "por_tema"])
    args = p.parse_args()

    casos = cargar_casos(args.categorias)
    print(f"base={args.db}  casos={len(casos)}  categorias={args.categorias}")
    print(f"{'extra':>6} | " + " | ".join(f"{c[:10]:>22}" for c in args.categorias))
    print(f"{'':>6} | " + " | ".join(f"{'R@5    R@1   fallos':>22}" for _ in args.categorias))

    resultados = []
    for valor in args.valores:
        # Cada corrida sobre su propia copia: el motor muta la base (despierta
        # nodos dormidos), así que reutilizarla contamina la siguiente medición.
        tmp = os.path.join(tempfile.gettempdir(), f"barrido_{valor}.db")
        shutil.copyfile(args.db, tmp)
        os.environ["BIORAG_SINONIMOS_BONUS_EXTRA"] = str(valor)
        # Recargar constants para que tome el valor nuevo en este proceso.
        import importlib

        from core.memory import constants

        importlib.reload(constants)
        t0 = time.time()
        por_cat = medir(tmp, casos)
        os.remove(tmp)
        fila = f"{valor:>6} | "
        fila += " | ".join(
            f"{por_cat[c]['r5']:>6.3f} {por_cat[c]['r1']:>6.3f} {por_cat[c]['fallos']:>6}"
            if c in por_cat else f"{'-':>22}"
            for c in args.categorias
        )
        print(fila + f"   ({time.time()-t0:.0f}s)")
        resultados.append({"extra": valor, **por_cat})

    # Sin huella de la corrida pasada, la primera corrida se perdía: el JSON se
    # sobreescribía y la doc acababa reportando valores que nadie podía verificar.
    # Ahora cada corrida deja su propio fichero y dice con qué configuración se
    # hizo (neurona sí/no), para que el número sea reproducible por un tercero.
    import datetime

    sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    neurona_on = os.environ.get("BIORAG_NEURONA", "1") != "0"
    traza = {
        "fecha": sello,
        "db": args.db,
        "categorias": args.categorias,
        "neuron": "activa" if neurona_on else "apagada",
        "casos": len(casos),
        "resultados": resultados,
    }
    salida = os.path.join(RAIZ, f"scripts/barrido_bonus_sinonimos_{sello}_neurona_{'on' if neurona_on else 'off'}.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(traza, f, indent=2, ensure_ascii=False)
    print(f"-> {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
