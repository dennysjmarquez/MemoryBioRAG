"""Ranking servido con una neurona YA entrenada: mismas búsquedas, se anota todo."""
import contextlib
import io
import json
import os
import random
import sys

REPO, DB, SALIDA = sys.argv[1:4]
sys.path.insert(0, REPO)
os.chdir(REPO)
from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from core.memory import neurona  # noqa: E402
from core.memory.neurona_examen import sustantivos_de  # noqa: E402

casos = [json.loads(l) for l in open(os.path.join(REPO, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8") if l.strip()]
casos = [c for c in casos if c.get("categoria") not in ("negativo", "ambiguo")]
random.Random(7).shuffle(casos)
qs = [c["query"] for c in casos][:300]
with contextlib.redirect_stdout(io.StringIO()):
    db = SQLiteMemoryBioRAG(DB)
r = neurona.resumen(db)
out = {"campeon": r["campeon"], "margen": r.get("margen"), "res": []}
for q in qs:
    for camino, kw in (("crudo", dict(limite=5, ignore_peso_sinaptico=True)),
                       ("agente", dict(limite=30, convergencia_limite=10,
                                       sustantivos_clave_boost=sustantivos_de(q) or None))):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            res = db.buscar_por_frase(q, profundidad="activos", **kw) or []
        def limpio(v):
            if isinstance(v, float):
                return round(v, 6)
            if isinstance(v, (list, tuple)):
                return [limpio(z) for z in v]
            if isinstance(v, dict):
                return {str(k): limpio(z) for k, z in sorted(v.items(), key=lambda t: str(t[0]))}
            if isinstance(v, (int, str, bool)) or v is None:
                return v
            return repr(v)
        fila = limpio(list(res[:10]))
        out["res"].append([camino, q, fila])
json.dump(out, open(SALIDA, "w"), ensure_ascii=False)
print("campeon", r["campeon"], "margen", r.get("margen"), "busquedas", len(out["res"]))
