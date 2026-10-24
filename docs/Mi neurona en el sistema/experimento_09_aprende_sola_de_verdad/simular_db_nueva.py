#!/usr/bin/env python3
"""Experimento 09 — una DB NUEVA que crece como la de un tercero: cada "sesión" guarda N
recuerdos (aprender → corto plazo) y consolida UNA vez (ciclo_sueno_consolidacion), que es
cuando la neurona practica. Nadie busca nada: es el caso más duro (el motor duerme por LTD
los recuerdos que no se usan, y la neurona tira las preguntas de los dormidos).

Los recuerdos salen del snapshot canónico (solo lectura) en orden de creación.

Uso:
  PYTHONHASHSEED=1 REPO=<árbol de código> BIORAG_PATH=/tmp/x \
      python simular_db_nueva.py <recuerdos_por_sesion> <sesiones> <db_nueva.db>
"""
import contextlib
import io
import os
import sqlite3
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("REPO", os.path.join(AQUI, "..", "..", "..")))
SNAP = os.path.join(os.path.abspath(os.path.join(AQUI, "..", "..", "..")), "snapshots", "qa_escape_qcr_20260811.db")
sys.path.insert(0, REPO)
os.chdir(REPO)

POR_SESION, SESIONES, DB = int(sys.argv[1]), int(sys.argv[2]), os.path.abspath(sys.argv[3])
if os.sep + "snapshots" + os.sep in DB:
    sys.exit("[ERROR] la DB nueva no puede estar en snapshots/")
if os.path.exists(DB):
    os.remove(DB)
src = sqlite3.connect(f"file:{SNAP}?mode=ro", uri=True)
filas = src.execute(
    "SELECT concepto, contenido, COALESCE(sinonimos,''), COALESCE(sustantivos_clave,'') "
    "FROM largo_plazo WHERE estado='activo' ORDER BY creado_en, id").fetchall()

from core.memory import neurona  # noqa: E402
from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    cb = SQLiteMemoryBioRAG(DB)
i = 0
for s in range(1, SESIONES + 1):
    t = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        for _ in range(POR_SESION):
            c, ct, sy, sk = filas[i]
            i += 1
            cb.percibir_corto_plazo(c, ct, sy, "General", None, sustantivos_clave=sk)
        cb.ciclo_sueno_consolidacion()
    r = neurona.resumen(cb)
    print(f"sesion {s:3d} recuerdos {i:4d} estudio {r['estudio']:3d} guardia {r['guardia']:3d} "
          f"ciclos {r['ciclos']} campeon {r['campeon']} ult {r.get('ultimo', {}).get('nuevas')} "
          f"{time.time() - t:.1f}s", flush=True)
