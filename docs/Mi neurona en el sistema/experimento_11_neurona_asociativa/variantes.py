"""Variantes honestas del experimento 11 (escribe resultados/variantes.json; ~3 min).

  A) Piso calibrado SIN mirar la memoria examinada: la rejilla de pesos se elige
     con 2 memorias de fábrica y se examina en la 3ª. Es el número limpio de
     "pesos a mano" (el piso del archivo se eligió mirando las 3).
  B) Tamaño del techo de la corrección y su freno (l2), examen "nunca vista".
Necesita haber corrido antes fabrica.py (usa su caché).
"""
import itertools
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import agujas  # noqa: E402
import fabrica as fb  # noqa: E402
import neurona_asociativa as na  # noqa: E402


def main():
    d = fb.construir()
    names = list(d)
    base = dict(na.PISO)
    claves = ("mutuo", "parecido", "rareza_max", "semantica", "vecinos")
    grid = list(itertools.product((2, 3), (2, 3), (1, 2), (1, 2, 3), (0, 1, 2)))

    def auc_piso(P, nm):
        na.PISO.clear()
        na.PISO.update(P)
        return fb.auc(na.fuerza(d[nm]["F"], agujas.NOMBRES, p=None), d[nm]["y"])

    out = {"A_piso_sin_mirar": {}, "B_techo": {}}
    for fuera in names:
        dentro = [x for x in names if x != fuera]
        best = None
        for vals in grid:
            P = dict(base)
            P.update(dict(zip(claves, vals)))
            m = min(auc_piso(P, x) for x in dentro)
            if best is None or m > best[0]:
                best = (m, P)
        out["A_piso_sin_mirar"][fuera] = {"auc_piso_sin_mirar": round(auc_piso(best[1], fuera), 3),
                                          "pesos_elegidos": {k: best[1][k] for k in claves},
                                          "auc_piso_del_archivo": round(auc_piso(base, fuera), 3)}
        print("A", fuera, out["A_piso_sin_mirar"][fuera], flush=True)
    na.PISO.clear()
    na.PISO.update(base)
    techo0 = na.TECHO
    for techo, l2 in ((3.0, 1e-3), (1.0, 1e-3), (1.0, 1e-2), (0.5, 1e-2)):
        na.TECHO = techo
        r = {}
        for fuera in names:
            E, G = fb.filas(d, [x for x in names if x != fuera])
            p, _ = na.entrenar(*E, *G, l2=l2, semilla=0)
            r[fuera] = round(fb.auc(na.fuerza(d[fuera]["F"], agujas.NOMBRES, p=p), d[fuera]["y"]), 3)
        out["B_techo"][f"techo_{techo}_l2_{l2}"] = r
        print("B", techo, l2, r, flush=True)
    na.TECHO = techo0
    json.dump(out, open(os.path.join(fb.RES, "variantes.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
