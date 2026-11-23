#!/usr/bin/env python3
"""E2b — la causa general del ruido, medida sobre la API pública del motor.

SOLO DIAGNÓSTICO. No instrumenta nada por dentro: llama a `buscar_por_frase` como
la QA y compara los resultados servidos. Así el número que se publica es el que el
motor da de verdad.

Qué enseña: en una consulta de dos palabras, UNA palabra que no pega deja la
cobertura de alias en 2/3 = 0,633, y eso cruza dos umbrales a la vez:
  * `sinonimos_ratio >= 0.95` deja de cumplirse  -> se pierde el bono en logit
    (core/memory/scoring.py:377), que es el que subía al nodo de 0,34 a 0,61.
  * `sinonimos_ratio < 0.5` deja de cumplirse   -> la compuerta del temático
    (core/memory/search.py:1749) le apaga esa señal.

Uso: python scripts/diagnostico_ruido_causa.py --base snapshot|viva
"""

import argparse
import json
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402

SNAPSHOT = os.path.join(RAIZ, "snapshots", "qa_escape_qcr_20260811.db")
ESPERADO = "v13_2_limpieza_tabla_semantica"

# Consultas: la limpia, la del examen, la del ruido inventado y dos controles.
CONSULTAS = [
    ("limpia", "semánticas embedding"),
    ("examen_0848", "semánticas 849 embedding"),
    ("ruido_inventado", "semánticas zzqx embedding"),
    ("ruido_real", "semánticas embedding julio"),
    ("solo_2_palabras_ok", "limpieza semántica tabla embedding"),
]


def _copia(base):
    origen = SNAPSHOT if base == "snapshot" else "/tmp/viva.db"
    destino = f"/tmp/e2b_causa_{base}.db"
    for e in ("", "-wal", "-shm"):
        if os.path.exists(destino + e):
            os.remove(destino + e)
    shutil.copyfile(origen, destino)
    return destino


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, choices=["snapshot", "viva"])
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    db = SQLiteMemoryBioRAG(db_path=_copia(args.base))
    db.cursor.execute("UPDATE largo_plazo SET estado='activo' WHERE concepto=?", (ESPERADO,))
    db.conn.commit()

    salida = {"base": args.base, "esperado": ESPERADO, "consultas": {}}
    for etiqueta, consulta in CONSULTAS:
        res, total = db.buscar_por_frase(
            consulta, profundidad="activos", limite=50, ignore_peso_sinaptico=True
        )
        fila = [[r[0], round(r[4], 4)] for r in res]
        pos = [r[0] for r in res]
        salida["consultas"][etiqueta] = {
            "consulta": consulta,
            "palabras": len(consulta.split()),
            "candidatos": total,
            "puesto_esperado": (pos.index(ESPERADO) + 1) if ESPERADO in pos else None,
            "score_esperado": next((round(r[4], 4) for r in res if r[0] == ESPERADO), None),
            "top5": fila[:5],
        }
        p = salida["consultas"][etiqueta]["puesto_esperado"]
        s = salida["consultas"][etiqueta]["score_esperado"]
        print(f"{etiqueta:<20} {consulta:<34} puesto={p} score={s} candidatos={total}", flush=True)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
        print(f"guardado en {args.json}")
    os.remove(f"/tmp/e2b_causa_{args.base}.db")


if __name__ == "__main__":
    main()
