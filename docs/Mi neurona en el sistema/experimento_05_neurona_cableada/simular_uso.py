"""Simula el uso real de la neurona cableada: N consolidaciones seguidas.

Cada ciclo llama a `neurona.practicar(db, recien_consolidados)`, exactamente lo
que hacen `consolidar_concepto` y el ciclo de sueño después de guardar. Usa la
configuración por defecto del motor (2 recuerdos x 2 preguntas, tope 3 s).
Si no se pasan conceptos, la neurona repasa recuerdos viejos al azar (como en
una DB existente donde casi no entra nada nuevo).

Escribe una línea JSON por ciclo (curva de aprendizaje + latencia).
NUNCA usar sobre la DB viva ni el snapshot congelado: trabaja sobre una COPIA.

Uso:
  python simular_uso.py --db /ruta/copia.db --ciclos 400 --salida curva.jsonl
"""
import argparse
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
os.environ["BIORAG_NO_LOG"] = "1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--ciclos", type=int, default=400)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--parar-en-techo", action="store_true",
                    help="cortar cuando la neurona entra en 'tranquila (techo)'")
    a = ap.parse_args()
    congelado = os.path.realpath(os.path.join(REPO, "snapshots"))
    if os.path.realpath(a.db).startswith(congelado) or os.path.realpath(a.db).endswith("memory_biorag.db"):
        sys.exit("Esto modifica la DB: usá una copia, no el snapshot ni la DB viva.")

    from core.memory_store import SQLiteMemoryBioRAG
    from core.memory import neurona

    db = SQLiteMemoryBioRAG(db_path=os.path.abspath(a.db))
    t0 = time.time()
    with open(a.salida, "w", encoding="utf-8") as f:
        for i in range(a.ciclos):
            res = neurona.practicar(db, [])
            fila = dict(ciclo=i + 1, t=round(time.time() - t0, 1), **res)
            f.write(json.dumps(fila, ensure_ascii=False, default=float) + "\n")
            f.flush()
            if a.parar_en_techo and str(res.get("fase", "")).startswith("tranquila (techo)"):
                break
    print(json.dumps(neurona.resumen(db), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
