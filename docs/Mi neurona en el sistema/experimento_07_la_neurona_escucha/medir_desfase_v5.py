"""¿La neurona estudia EXACTAMENTE lo que después sirve? Medición sobre consultas reales.

Para N casos del QA y cada camino (agente / crudo):
  1. autoexamen: `neurona._preguntar` (en silencio) -> vista guardada para estudiar;
  2. servicio: la MISMA búsqueda hecha en serio -> vista que recibe `reordenar`
     (capturada con un espía, antes de reordenar).
Desfase = casos donde difieren los nombres, las señales X o la base. Antes (v4,
experimento 06/lectura) el top-5 estudiado y el servido diferían en 46.7 % de los casos.

Uso (COPIA de una DB con campeón): BIORAG_NEURONA=1 python medir_desfase_v5.py --db copia.db --n 150
"""
import argparse
import json
import os
import random
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
os.environ["BIORAG_NO_LOG"] = "1"

import numpy as np  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--salida", default="")
    a = ap.parse_args()
    from core.memory import neurona as N
    from core.memory.neurona_examen import sustantivos_de
    from core.memory_store import SQLiteMemoryBioRAG
    c = SQLiteMemoryBioRAG(os.path.abspath(a.db))
    if N.estado(c).campeon is None:   # sin campeón no se sirve con vista: uno neutro (corrección 0)
        N.estado(c).campeon = {"W": np.zeros((N.OCULTAS, len(N.F_SIG))), "b": np.zeros(N.OCULTAS),
                               "v": np.zeros(N.OCULTAS)}
    casos = [json.loads(l) for l in open(os.path.join(REPO, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8")]
    casos = [x for x in casos if x.get("concepto_esperado") and x["categoria"] not in ("negativo", "dormido")]
    random.Random(0).shuffle(casos)
    vistas, real = [], N.reordenar

    def espia(self, frase, pagina, v):
        vistas.append(v)
        return real(self, frase, pagina, v)
    N.reordenar = espia
    res = {m: dict(comparados=0, sin_vista=0, distintos=0) for m in N.MODOS}
    for x in casos[:a.n]:
        q, gold = x["query"], x["concepto_esperado"]
        for modo in N.MODOS:
            caso = N._preguntar(c, gold, q, x["categoria"], modo, 10)
            if modo == "agente":
                kw = dict(limite=30, convergencia_limite=10, sustantivos_clave_boost=sustantivos_de(q) or None)
            else:
                kw = dict(limite=5, ignore_peso_sinaptico=True)
            vistas.clear()
            c.buscar_por_frase(q, profundidad="activos", **kw)
            v = vistas[-1] if vistas else None
            if caso is None or v is None:
                res[modo]["sin_vista"] += 1   # la respuesta no estaba en la vista: no hay caso que comparar
                continue
            res[modo]["comparados"] += 1
            igual = (v["nombres"][caso["y"]] == gold and np.array_equal(v["X"], caso["X"])
                     and np.array_equal(v["base"], caso["base"]))
            res[modo]["distintos"] += int(not igual)
    for m, r in res.items():
        r["desfase_%"] = round(100.0 * r["distintos"] / max(1, r["comparados"]), 2)
    print(json.dumps(res, indent=1))
    if a.salida:
        json.dump(res, open(a.salida, "w"), indent=1)


if __name__ == "__main__":
    main()
