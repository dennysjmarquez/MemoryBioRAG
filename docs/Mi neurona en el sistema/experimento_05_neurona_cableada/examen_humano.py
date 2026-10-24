"""Examen con preguntas escritas por humanos: pesos a mano vs neurona aprendida.

Corre cada pregunta dos veces sobre la MISMA DB (en una copia temporal, solo
lectura en la práctica: BIORAG_NO_LOG=1): con BIORAG_NEURONA=0 (motor de
siempre) y con BIORAG_NEURONA=1 (con el campeón que la neurona aprendió sola).
Reporta R@1, R@5, MRR y los casos ganados/perdidos.

Uso:
  python examen_humano.py --db construida.db --examen examen_humano.jsonl [--salida res.json]
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
os.environ["BIORAG_NO_LOG"] = "1"


def rango(db, q, esperado):
    res, _ = db.buscar_por_frase(q, limite=5, ignore_peso_sinaptico=True)
    nombres = [r[0] for r in res[:5]]
    return nombres.index(esperado) + 1 if esperado in nombres else None


def metricas(rangos):
    n = len(rangos)
    return dict(n=n, r1=round(100 * sum(r == 1 for r in rangos) / n, 2),
                r5=round(100 * sum(r is not None for r in rangos) / n, 2),
                mrr=round(sum(1 / r for r in rangos if r) / n, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--examen", required=True)
    ap.add_argument("--salida")
    a = ap.parse_args()
    casos = [json.loads(l) for l in open(a.examen, encoding="utf-8") if l.strip()]
    tmp = tempfile.mkdtemp()
    copia = os.path.join(tmp, "examen.db")
    shutil.copy(a.db, copia)

    from core.memory_store import SQLiteMemoryBioRAG
    from core.memory import neurona
    db = SQLiteMemoryBioRAG(db_path=copia)
    print("neurona:", json.dumps(neurona.resumen(db), ensure_ascii=False, default=str)[:400], flush=True)

    out = {}
    for modo in ("0", "1"):
        os.environ["BIORAG_NEURONA"] = modo
        out[modo] = [rango(db, c["query"], c["esperado"]) for c in casos]
    os.environ.pop("BIORAG_NEURONA", None)

    def ok(r):
        return r == 1
    gana = [c["query"] for c, a0, a1 in zip(casos, out["0"], out["1"]) if not ok(a0) and ok(a1)]
    pierde = [c["query"] for c, a0, a1 in zip(casos, out["0"], out["1"]) if ok(a0) and not ok(a1)]
    rep = dict(a_mano=metricas(out["0"]), neurona=metricas(out["1"]),
               gana=len(gana), pierde=len(pierde), casos_ganados=gana, casos_perdidos=pierde,
               salen_del_top5=sum(1 for a0, a1 in zip(out["0"], out["1"]) if a0 and not a1))
    print(json.dumps({k: v for k, v in rep.items() if not k.startswith("casos")}, ensure_ascii=False))
    if a.salida:
        json.dump(rep, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
