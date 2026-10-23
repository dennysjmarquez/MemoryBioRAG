"""Aplica al QA (motor real, modo top5) las reglas elegidas con el examen, sin re-correr el motor.

Lee el registro `resultados/qa_motor_<etiqueta>_top.jsonl`, que guarda la lista final
del motor ANTES de reordenar y la corrección de la neurona para cada nodo. Con eso se
reproduce exactamente el reordenamiento de `qa_con_neurona.py` con cualquier ε.
Uso: python reglas_en_qa.py top5_A_R2_s7 [ε ...]
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[2]
sys.path.insert(0, str(AQUI))
import escala  # noqa: E402

et = sys.argv[1]
epsilones = [float(x) for x in sys.argv[2:]] or [0, 1, 2, 3]
casos = [json.loads(l) for l in open(REPO / "scripts" / "casos_qa_baseline_v1.jsonl", encoding="utf-8")]
R = [json.loads(l) for l in open(AQUI / "resultados" / f"qa_motor_{et}_top.jsonl", encoding="utf-8")]
B = [json.loads(l) for l in open(AQUI / "resultados" / "qa_motor_base_top.jsonl", encoding="utf-8")]
assert len(R) == len(casos) == len(B)


def reordenar(r, eps, identidad, q):
    if "pre" not in r:
        return r["top"]
    pre, cs = r["pre"], r["c"]
    conocidas = [c for c in cs if c is not None]
    relleno = float(np.mean(conocidas)) if conocidas else 0.0
    claves = [escala.g(min(max(s, 1e-4), 50.0)) + (c if c is not None else relleno) for (_, s), c in zip(pre, cs)]
    orden = sorted(range(len(pre)), key=lambda i: (-claves[i], i))
    cambia_1 = orden[0] != 0 and (claves[orden[0]] - claves[0]) > eps
    if identidad and pre[0][0].lower() == q.strip().lower():
        cambia_1 = False
    if not cambia_1:  # el #1 de hoy se queda; el resto se reordena igual
        orden = [0] + [i for i in orden if i != 0]
    return [pre[i][0] for i in orden]


print(f"{et}: reglas aplicadas sobre la lista final del motor (top-5)")
print("  ε     identidad   R@1     gana  pierde   pierde (casos)")
for identidad in (False, True):
    for eps in epsilones:
        gana, pierde, ok = [], [], 0
        cat_ok, cat_n = collections.Counter(), collections.Counter()
        for c, r, b in zip(casos, R, B):
            e = c.get("concepto_esperado")
            if not e:
                continue
            assert r["q"] == c["query"]
            top = reordenar(r, eps, identidad, c["query"])
            # comprobación: con ε=0 y sin identidad se reproduce exactamente la corrida
            if eps == 0 and not identidad:
                assert top == r["top"], c["id"]
            uno, b1 = top[:1] == [e], b["top"][:1] == [e]
            gana += [c["id"]] if uno and not b1 else []
            pierde += [c["id"]] if b1 and not uno else []
        n_ok = sum(1 for c, r, b in zip(casos, R, B) if c.get("concepto_esperado")
                   and reordenar(r, eps, identidad, c["query"])[:1] == [c["concepto_esperado"]])
        n = sum(1 for c in casos if c.get("concepto_esperado"))
        print(f"  {eps:<5} {'sí' if identidad else 'no':9s}  {n_ok / n * 100:6.2f}  {len(gana):5d}  {len(pierde):6d}   {pierde}")
print("  (R@1 aquí incluye los 6 'ambiguo' con su etiqueta original: no es el R@1 oficial; "
      "gana/pierde sí son comparables)")
