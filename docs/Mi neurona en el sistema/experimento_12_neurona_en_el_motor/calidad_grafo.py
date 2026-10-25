"""Calidad del grafo: peso de hoy contra peso de la neurona, mirando lo que el motor USA.

Uso:  python calidad_grafo.py ANTES.db DESPUES.db
      (las dos son copias; se abren solo lectura)

La expansión por el grafo (spreading activation, core/memory/synapses.py) toma, de cada
recuerdo, sus 6 vecinos de mayor peso (BIORAG_MAX_VECINOS_POR_NODO=6; empates: la sinapsis más
nueva primero). Este script mira esos "6 elegidos" en las dos DBs y cuenta:

  1. Pares del examen de Dennys (etiquetado/…/examen_hoja_dennys.json) que quedan entre los
     6 elegidos: cuántos "sí" y cuántos "no".
  2. Enlaces manuales (los que Dennys hizo a mano) que quedan entre los 6 elegidos.
  3. AUC del peso sobre los pares del examen que ya existen (sí contra no).
"""
import json
import os
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
EXAMEN = os.path.join(AQUI, "..", "experimento_11_neurona_asociativa", "resultados", "examen_hoja_dennys.json")
K = 6


def elegidos(ruta):
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    activos = {r[0] for r in con.execute("SELECT concepto FROM largo_plazo WHERE estado='activo'")}
    vec = {}
    for o, d, p, rid, t in con.execute("SELECT origen, destino, peso, rowid, tipo FROM sinapsis"):
        if o in activos and d in activos and o != d:
            vec.setdefault(o, []).append((p or 0.0, rid, d, t))
            vec.setdefault(d, []).append((p or 0.0, rid, o, t))
    pesos = {}
    for o, d, p in con.execute("SELECT origen, destino, peso FROM sinapsis"):
        k = tuple(sorted((o, d)))
        pesos[k] = max(pesos.get(k, 0.0), p or 0.0)
    manual = {tuple(sorted((o, d))) for o, d in con.execute(
        "SELECT origen, destino FROM sinapsis WHERE tipo IN ('manual','manual_v7')")}
    con.close()
    top = set()
    for n, lista in vec.items():
        lista.sort(key=lambda x: (-x[0], -x[1]))
        vistos = []
        for p, rid, d, t in lista:
            if d not in vistos:
                vistos.append(d)
            if len(vistos) >= K:
                break
        for d in vistos:
            top.add(tuple(sorted((n, d))))
    return top, pesos, manual


def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / len(pos) / len(neg)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ex = json.load(open(EXAMEN, encoding="utf-8"))["pares"]
    lab = {}
    for p in ex:
        r = p["respuesta_dennys"]
        if p["grupo"] in "AB" and r in ("si", "momento", "no"):
            lab[tuple(sorted((p["a"], p["b"])))] = 1 if r != "no" else 0
    out = {}
    for nombre, ruta in (("antes", sys.argv[1]), ("despues", sys.argv[2])):
        top, pesos, manual = elegidos(ruta)
        si = sum(1 for k, v in lab.items() if v == 1 and k in top)
        no = sum(1 for k, v in lab.items() if v == 0 and k in top)
        out[nombre] = {
            "examen_si_entre_los_6": si, "examen_no_entre_los_6": no,
            "examen_si_total": sum(lab.values()), "examen_no_total": len(lab) - sum(lab.values()),
            "manuales_entre_los_6": len(manual & top), "manuales_total": len(manual),
            "auc_peso_examen": round(auc([pesos.get(k, 0) for k, v in lab.items() if v],
                                         [pesos.get(k, 0) for k, v in lab.items() if not v]), 3),
            "pares_elegidos": len(top)}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
