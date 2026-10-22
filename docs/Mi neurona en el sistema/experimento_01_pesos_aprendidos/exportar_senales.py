"""Exporta las señales de TODOS los candidatos de cada caso QA (solo lectura).

Es el paso 1 del experimento: para cada una de las 921 consultas del QA guarda
exactamente lo que recibe `_calcular_score_hibrido` por cada candidato del pool
(las ~17 entradas de la "neurona" actual) y el score que devolvió.

Uso (desde la raíz del repo):
    PYTHONHASHSEED=1 python "docs/Mi neurona en el sistema/experimento_01_pesos_aprendidos/exportar_senales.py"
    # opcional: --limite 20 (solo los primeros N casos, para una prueba rápida)
    #           --salida ruta.jsonl.gz

Garantías:
- Trabaja sobre una COPIA del snapshot congelado en el directorio temporal del
  sistema; el snapshot `snapshots/qa_escape_qcr_20260811.db` se abre en modo
  solo lectura y nunca se modifica.
- Mismos parámetros que `scripts/evaluar_qa.py` (peso sináptico OFF, limite=5,
  profundo para dormido/negativo, restauración de estado/peso entre casos).
- Con PYTHONHASHSEED=1 reproduce el QA oficial: R@1 91.89 / R@5 100.

Por qué PYTHONHASHSEED: el motor hoy NO es determinista entre procesos
(search.py arma un `set` y similitud_conceptual.py toma los 10 primeros en orden
de hash). Sin semilla fija el caso 0513 entra o sale del top-5 según el proceso.
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
REPO = Path(os.environ.get("BIORAG_REPO", AQUI.parents[2]))
sys.path.insert(0, str(REPO))

ap = argparse.ArgumentParser()
ap.add_argument("--salida", default=None)
ap.add_argument("--limite", type=int, default=None)
args = ap.parse_args()

semilla = os.environ.get("PYTHONHASHSEED")
if semilla is None:
    print("AVISO: PYTHONHASHSEED no está fijado; el resultado puede variar entre procesos.", file=sys.stderr)
salida = Path(args.salida) if args.salida else AQUI / "datos" / f"pools_semilla{semilla or 'aleatoria'}.jsonl.gz"
salida.parent.mkdir(parents=True, exist_ok=True)

SNAP = REPO / "snapshots" / "qa_escape_qcr_20260811.db"
DB = Path(tempfile.gettempdir()) / f"biorag_neurona_pools_{semilla or 'r'}.db"
for ext in ("", "-wal", "-shm"):
    p = Path(str(DB) + ext)
    if p.exists():
        p.unlink()
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
    """Llama a la fórmula real y guarda sus entradas y su salida."""
    s = scoring._calcular_score_hibrido(db, **kw)
    kw = dict(kw)
    kw["_score"] = s
    capturas.append(kw)
    return s


db._calcular_score_hibrido = _envoltura

# Mismas 3 etiquetas obsoletas que resuelve scripts/evaluar_qa.py contra este snapshot.
OBSOLETAS = {
    "0268": "lección:_guardar_todo_lo_importante_inmediatamente_y_no_esperar",
    "0368": "plugin_biorag-remember_v8.4_-_solo_session.idle_y_sin_conteo_de_edits",
    "0371": "plugin_v7.1_fix:_session.idle_es_un_event_y_no_un_hook",
}
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


casos = [json.loads(l) for l in open(REPO / "scripts" / "casos_qa_baseline_v1.jsonl", encoding="utf-8") if l.strip()]
if args.limite:
    casos = casos[: args.limite]
t0 = time.time()
with gzip.open(salida, "wt", encoding="utf-8") as out:
    for i, caso in enumerate(casos):
        cat, q = caso["categoria"], caso["query"]
        esperado = OBSOLETAS.get(caso["id"], caso.get("concepto_esperado"))
        if cat == "dormido" and esperado:
            db.cursor.execute("UPDATE largo_plazo SET estado='dormido' WHERE concepto=?", (esperado,))
            db.conn.commit()
        elif esperado:
            db.cursor.execute("UPDATE largo_plazo SET estado='activo' WHERE concepto=?", (esperado,))
            db.conn.commit()
        profundidad = "profundo" if (caso.get("deep") or cat in ("dormido", "negativo")) else "activos"
        capturas.clear()
        res, _total = db.buscar_por_frase(q, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        pool = [r[1] for r in (db.last_todos or [])]
        candidatos, vistos = [], set()
        for conc, kw in zip(pool, capturas):
            if conc in vistos:
                continue
            vistos.add(conc)
            kw = {k: (float(v) if isinstance(v, (int, float, bool)) else v) for k, v in kw.items()}
            kw["c"] = conc
            candidatos.append(kw)
        out.write(json.dumps({"id": caso["id"], "cat": cat, "q": q, "exp": esperado,
                              "top": [r[0] for r in res], "cands": candidatos}, ensure_ascii=False) + "\n")
        restaurar()
        if i % 100 == 0:
            print(f"{i}/{len(casos)} {time.time() - t0:.0f}s", flush=True)
print(f"FIN {len(casos)} casos en {time.time() - t0:.0f}s -> {salida}", flush=True)
