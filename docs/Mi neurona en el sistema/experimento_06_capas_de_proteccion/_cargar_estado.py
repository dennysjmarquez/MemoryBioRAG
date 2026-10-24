"""Lee el estado guardado de la neurona de una DB (solo lectura) sin pasar por la huella.
Solo para diagnóstico: el motor nunca carga así."""
import io
import json
import os
import sqlite3
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
import numpy as np  # noqa: E402
import core.memory.neurona as N  # noqa: E402


def cargar(ruta):
    cur = sqlite3.connect(f"file:{os.path.abspath(ruta)}?mode=ro", uri=True).cursor()
    d = json.loads(cur.execute("SELECT valor FROM neurona_estado WHERE clave='pesos'").fetchone()[0])
    campeon = {k: np.array(v) for k, v in d["campeon"].items()} if d.get("campeon") else None
    z = np.load(io.BytesIO(cur.execute("SELECT valor FROM neurona_estado WHERE clave='memoria'").fetchone()[0]))
    meta = json.loads(str(z["meta"]))
    est = N._Estado()
    for nombre in ("estudio", "guardia"):
        for i, m in enumerate(meta[nombre]):
            getattr(est, nombre).append(dict(cat=m["cat"], nodo=m["nodo"], y=m["y"],
                                             X=z[f"{nombre}_X_{i}"], base=z[f"{nombre}_b_{i}"]))
    return N, est, campeon
