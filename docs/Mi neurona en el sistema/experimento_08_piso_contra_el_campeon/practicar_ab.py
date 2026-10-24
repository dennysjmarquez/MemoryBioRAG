#!/usr/bin/env python3
"""Experimento 08 — driver A/B: corre N ciclos de práctica (lo mismo que corre tras cada
consolidación) con el código de un árbol dado y anota cada ciclo en JSONL.

Para que A y B sean comparables de verdad, el presupuesto de tiempo por ciclo se pone
alto (BIORAG_NEURONA_PRESUPUESTO_S, por defecto aquí 1000 s): así ninguna pregunta se
salta por lentitud de la máquina y la corrida es determinista (mismas semillas, mismo
examen). Con el presupuesto normal de 3 s, dos corridas del MISMO código ya difieren.

Uso:
  PYTHONHASHSEED=1 python practicar_ab.py --repo <árbol de código> --db <copia.db> \
      --ciclos 500 --salida curva.jsonl
"""
import argparse
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="árbol de código a usar (A = HEAD, B = cambio)")
    ap.add_argument("--db", required=True, help="COPIA de la DB (nunca el snapshot ni la viva)")
    ap.add_argument("--ciclos", type=int, default=500)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    repo, db_path = os.path.abspath(a.repo), os.path.abspath(a.db)
    if os.sep + "snapshots" + os.sep in db_path:
        sys.exit("[ERROR] usá una copia, no el snapshot")
    os.environ.setdefault("BIORAG_NEURONA_PRESUPUESTO_S", "1000")
    os.chdir(repo)
    sys.path.insert(0, repo)
    from core.memory_store import SQLiteMemoryBioRAG
    from core.memory import neurona

    db = SQLiteMemoryBioRAG(db_path=db_path)
    t0 = time.time()
    try:
        with open(a.salida, "w", encoding="utf-8") as f:
            for i in range(1, a.ciclos + 1):
                tc = time.time()
                r = neurona.practicar(db, [])
                fila = {"ciclo": i, "s": round(time.time() - tc, 3)}
                fila.update({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
                             if isinstance(v, (int, float, str, bool)) or v is None})
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
                f.flush()
                if r.get("fase") == "ascenso" or r.get("retiro") or r.get("veto_campeon"):
                    print(f"ciclo {i:4d} fase={r.get('fase')} margen={r.get('margen')} "
                          f"retiro={r.get('retiro', False)} veto_campeon={r.get('veto_campeon', False)}", flush=True)
        print(json.dumps(neurona.resumen(db), ensure_ascii=False, default=str))
        print(f"{a.ciclos} ciclos en {time.time() - t0:.0f} s")
    finally:
        try:
            db.cerrar_sistema()
        except Exception:
            pass


if __name__ == "__main__":
    main()
