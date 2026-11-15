#!/usr/bin/env python3
"""Control E2d del 0848 en snapshot: con/sin observador y con/sin palabras extra.

No modifica el motor ni la fuente. Dos copias frescas ejecutan las mismas cuatro
consultas, en el mismo orden. El observador solo lee la señal del esperado y
llama a la fórmula original. La prueba no atribuye sus resultados a la viva.

    BIORAG_NEURONA=0 BIORAG_NO_LOG=1 python scripts/diagnostico_0848_e2d.py
"""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.memory_store import SQLiteMemoryBioRAG
from core.memory.search import buscar_por_frase
from scripts.censo_tematico_e2d import leer_media

SOURCE = ROOT / "snapshots" / "qa_escape_qcr_20260811.db"
EXPECTED = "v13_2_limpieza_tabla_semantica"
QUERIES = (
    "semánticas embedding",
    "semánticas 849 embedding",
    "semánticas zzqx embedding",
    "semánticas 849 embedding zzqx",
)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if os.environ.get("BIORAG_NEURONA") != "0" or os.environ.get("BIORAG_NO_LOG") != "1":
        raise RuntimeError("usar BIORAG_NEURONA=0 y BIORAG_NO_LOG=1")
    if any(Path(str(SOURCE) + ext).exists() for ext in ("-wal", "-journal")):
        raise RuntimeError("la fuente tiene WAL o journal: immutable no los incorpora")
    antes = sha256(SOURCE)
    results = {}
    recorded = []
    original = SQLiteMemoryBioRAG._calcular_score_hibrido

    def observed(self, **kw):
        frame = sys._getframe(1)
        while frame is not None and frame.f_code is not buscar_por_frase.__code__:
            frame = frame.f_back
        if frame is not None and frame.f_locals.get("concepto") == EXPECTED:
            locales = frame.f_locals
            estado, media, pares = leer_media(locales, float(kw.get("tematico_score", 0.0) or 0.0))
            recorded.append({
                "ratio": kw["sinonimos_ratio"],
                "tematico": kw["tematico_score"],
                "compuerta": estado,
                "media_previa": media,
                "pares": pares,
            })
        return original(self, **kw)

    try:
        for modo in ("sin_observador", "con_observador"):
            with tempfile.TemporaryDirectory(prefix="e2d_control_0848_") as tmp:
                src = sqlite3.connect(SOURCE.as_uri() + "?mode=ro&immutable=1", uri=True)
                dst = sqlite3.connect(str(Path(tmp) / "copia.db"))
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()
                db = SQLiteMemoryBioRAG(db_path=str(Path(tmp) / "copia.db"))
                SQLiteMemoryBioRAG._calcular_score_hibrido = observed if modo == "con_observador" else original
                results[modo] = []
                for query in QUERIES:
                    rows, total = db.buscar_por_frase(
                        query, profundidad="activos", limite=5, ignore_peso_sinaptico=True
                    )
                    top5 = [[r[0], r[4]] for r in rows]
                    position = next((i for i, r in enumerate(rows, 1) if r[0] == EXPECTED), None)
                    results[modo].append({
                        "consulta": query, "total": total, "puesto": position, "top5": top5
                    })
                db.conn.close()
    finally:
        SQLiteMemoryBioRAG._calcular_score_hibrido = original

    if antes != sha256(SOURCE):
        raise RuntimeError("la fuente cambió de SHA durante la prueba")
    if results["sin_observador"] != results["con_observador"]:
        raise RuntimeError("el observador alteró los resultados; control inválido")
    if len(recorded) != len(QUERIES):
        raise RuntimeError(f"se esperaban {len(QUERIES)} señales, se observaron {len(recorded)}")
    print("Snapshot: top-5 y puntuaciones idénticos con y sin observador:", True)
    for row, extra in zip(results["con_observador"], recorded):
        print(json.dumps({"consulta": row["consulta"], "puesto": row["puesto"], **extra}, ensure_ascii=False))


if __name__ == "__main__":
    main()
