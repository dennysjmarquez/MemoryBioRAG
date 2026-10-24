"""¿Cuánta seguridad cuesta cuánta ganancia? Regla de margen + regla de identidad, en el top-5.

Simula el modo top5 (la neurona solo reordena los 5 primeros de los pesos base) sobre
los nodos de GUARDIA del examen autogenerado (que la neurona no estudió), con dos
reglas de seguridad:

  - identidad: si el #1 base se llama exactamente como la consulta, sigue #1.
  - margen ε: la neurona solo cambia el #1 si su favorito le saca más de ε (en logit)
    al #1 base. Con ε=0 es la neurona sin freno.

El ε se elige AQUÍ, con el examen. El QA no se usa para elegir nada.
Uso: python regla_margen.py --semilla 7 --pesos resultados/pesos/A_R2_semilla7.npz
"""
import argparse
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "experimento_01_pesos_aprendidos"))
sys.path.insert(0, str(AQUI))
import entrenar_neurona as en  # noqa: E402
import escala  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--semilla", type=int, default=7)
ap.add_argument("--pesos", required=True)
A = ap.parse_args()
en.logit = escala.g

casos = []
for p in ("pools_examen_p0.jsonl.gz", "pools_examen_p1.jsonl.gz"):
    casos += en.cargar(AQUI / "datos" / p)
nodos = sorted({c["exp"] for c in casos})
rng = np.random.default_rng(A.semilla)
rng.shuffle(nodos)
guardia_nodos = set(nodos[: len(nodos) // 5])
guardia = [c for c in casos if c["exp"] in guardia_nodos and len(c["X"]) > 1]

z = np.load(AQUI / A.pesos)
W, b, v = z["W"], z["b"], z["v"]

import gzip  # noqa: E402
import json  # noqa: E402
qtxt = {}
for p in ("pools_examen_p0.jsonl.gz", "pools_examen_p1.jsonl.gz"):
    for l in gzip.open(AQUI / "datos" / p, "rt", encoding="utf-8"):
        r = json.loads(l)
        qtxt[r["id"]] = (r["q"], [k["c"] for k in r["cands"]])


def simular(eps, identidad):
    gana = pierde = 0
    for c in guardia:
        base = c["base"]
        top = np.argsort(-base, kind="stable")[:5]
        corr = np.tanh(c["X"][top] @ W.T + b) @ v
        clave = base[top] + corr
        nuevo = top[int(np.argmax(clave))]
        q, nombres = qtxt[c["id"]]
        cambia = nuevo != top[0] and (clave.max() - clave[0]) > eps
        if identidad and nombres[top[0]].lower() == q.strip().lower():
            cambia = False
        uno = nuevo if cambia else top[0]
        gana += int(uno == c["y"] and top[0] != c["y"])
        pierde += int(uno != c["y"] and top[0] == c["y"])
    return gana, pierde


print(f"guardia de la semilla {A.semilla}: {len(guardia)} preguntas de nodos no estudiados")
print("  ε      identidad   gana  pierde   neto   pierde/gana")
for identidad in (False, True):
    for eps in (0, .25, .5, 1, 1.5, 2, 3):
        g, p = simular(eps, identidad)
        print(f"  {eps:<5}  {'sí' if identidad else 'no':9s}  {g:5d}  {p:6d}  {g - p:5d}   {p / max(g, 1):.3f}")
