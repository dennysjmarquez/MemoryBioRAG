"""Paso 2 del experimento 04: pasa cada pregunta del examen por el motor REAL y guarda
lo que ve cada aguja de cada candidato (solo lectura).

Es el mismo procedimiento que `experimento_01_pesos_aprendidos/exportar_senales.py`
(mismos parámetros que `scripts/evaluar_qa.py`), generalizado para cualquier
archivo de casos y para correr en partes en paralelo.

Uso (desde la raíz del repo):
    PYTHONHASHSEED=1 python ".../exportar_pools.py" --casos datos/examen_autogenerado.jsonl \
        --parte 0 --partes 2 --salida datos/pools_examen_p0.jsonl.gz

Garantías: trabaja sobre una COPIA temporal del snapshot; el snapshot se abre en
modo solo lectura y nunca se modifica.
"""
import argparse
import gzip
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[2]
sys.path.insert(0, str(REPO))

ap = argparse.ArgumentParser()
ap.add_argument("--casos", required=True)
ap.add_argument("--salida", required=True)
ap.add_argument("--parte", type=int, default=0)
ap.add_argument("--partes", type=int, default=1)
args = ap.parse_args()
os.environ["BIORAG_NO_LOG"] = "1"

SNAP = REPO / "snapshots" / "qa_escape_qcr_20260811.db"
DB = Path(tempfile.gettempdir()) / f"biorag_exp04_{os.getpid()}.db"
src = sqlite3.connect(SNAP.resolve().as_uri() + "?mode=ro", uri=True)
dst = sqlite3.connect(DB)
src.backup(dst)
dst.close()
src.close()

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from core.memory import scoring  # noqa: E402

db = SQLiteMemoryBioRAG(str(DB))
capturas = []


def _envoltura(**kw):
    s = scoring._calcular_score_hibrido(db, **kw)
    kw = dict(kw)
    kw["_score"] = s
    capturas.append(kw)
    return s


db._calcular_score_hibrido = _envoltura
estado_inicial = {c: (e, p) for c, e, p in db.cursor.execute(
    "SELECT concepto, estado, peso_sinaptico FROM largo_plazo")}


def restaurar():
    cambios = []
    for c, e, p in db.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall():
        o = estado_inicial.get(c)
        if o and (o[0] != e or o[1] != p):
            cambios.append((o[0], o[1], c))
    if cambios:
        db.cursor.executemany("UPDATE largo_plazo SET estado=?, peso_sinaptico=? WHERE concepto=?", cambios)
        db.conn.commit()


casos = [json.loads(l) for l in open(args.casos, encoding="utf-8") if l.strip()]
casos = casos[args.parte::args.partes]
t0 = time.time()
with gzip.open(args.salida, "wt", encoding="utf-8") as out:
    for i, caso in enumerate(casos):
        cat, q, esperado = caso["categoria"], caso["query"], caso.get("concepto_esperado")
        if esperado:
            db.cursor.execute("UPDATE largo_plazo SET estado='activo' WHERE concepto=?", (esperado,))
            db.conn.commit()
        profundidad = "profundo" if caso.get("deep") else "activos"
        capturas.clear()
        res, _ = db.buscar_por_frase(q, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        pool = [r[1] for r in (db.last_todos or [])]
        cands, vistos = [], set()
        for conc, kw in zip(pool, capturas):
            if conc in vistos:
                continue
            vistos.add(conc)
            kw = {k: (float(v) if isinstance(v, (int, float, bool)) else v) for k, v in kw.items()}
            kw["c"] = conc
            cands.append(kw)
        out.write(json.dumps({"id": caso["id"], "cat": cat, "q": q, "exp": esperado,
                              "top": [r[0] for r in res], "cands": cands}, ensure_ascii=False) + "\n")
        restaurar()
        if i % 100 == 0:
            print(f"{i}/{len(casos)} {time.time() - t0:.0f}s", flush=True)
print(f"FIN {len(casos)} casos en {time.time() - t0:.0f}s -> {args.salida}", flush=True)
db.conn.close()
for ext in ("", "-wal", "-shm"):
    try:
        os.unlink(str(DB) + ext)
    except OSError:
        pass
