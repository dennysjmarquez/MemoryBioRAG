"""¿Qué le queda por aprender a la neurona? (experimento 11, v2; escribe resultados/variantes.json)

  A) CADA MEMORIA SOLA: se entrena la corrección con UNA memoria y se mide en su
     guardia (recuerdos que nunca estudió). Dice cuánto se podría ganar si la
     neurona aprendiera DENTRO de esa memoria.
  B) TODAS JUNTAS: se entrena con las 7 a la vez y se mira, paso a paso, cómo le va
     a cada una en su guardia. Dice si existe UNA corrección que sirva para todas.
  C) Lo mismo que B pero "cuidando a la que va peor" (homeostasis).

Necesita haber corrido antes fabrica.py (usa su caché). ~1 min.
"""
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import fabrica as fb  # noqa: E402
import neurona_asociativa as na  # noqa: E402


def main():
    d = fb.construir()
    nombres = list(d)
    out = {"A_cada_memoria_sola": {}, "B_todas_juntas": [], "C_todas_juntas_cuidando": []}
    for nm in nombres:
        E, G = fb.filas(d, [nm])
        reg = []
        na.entrenar(E, G, pasos=1500, paciencia=10 ** 9, cada=100, registro=reg, cuidar=0)
        out["A_cada_memoria_sola"][nm] = round(max(r[1][nm] for r in reg), 4)
        print("A", nm, out["A_cada_memoria_sola"][nm], flush=True)
    E, G = fb.filas(d, nombres)
    for clave, cuidar in (("B_todas_juntas", 0.0), ("C_todas_juntas_cuidando", 0.003)):
        reg = []
        na.entrenar(E, G, pasos=2000, paciencia=10 ** 9, cada=100, registro=reg, cuidar=cuidar)
        for t, dif in reg:
            out[clave].append({"paso": t, **dif, "peor": round(min(dif.values()), 4),
                               "promedio": round(float(np.mean(list(dif.values()))), 4)})
        ult = out[clave][-1]
        print(clave, ult, flush=True)
    json.dump(out, open(os.path.join(fb.RES, "variantes.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
