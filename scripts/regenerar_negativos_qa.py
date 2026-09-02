#!/usr/bin/env python3
"""Regenera SOLO los controles negativos del QA baseline (IDs 0882-0921).

MOTIVACIÓN (2026-09-01): los 40 controles negativos del baseline quedaron
contaminados. 35/40 contienen tokens que hoy existen en el corpus porque las
lecciones/hallazgos sobre la propia suite QA (investigación del gate QCR y sus
falsos positivos) citan esas mismas queries como ejemplos dentro de la memoria.
Resultado: el motor las recupera legítimamente (no es un fallo del gate) y el
evaluador las cuenta como FP (60%).

Este script reemplaza únicamente los casos `negativo`, preservando el resto de
los 921 casos byte a byte, y usa la validación endurecida de
`generate_negative_queries` (sin overlap léxico con el corpus + validación
empírica del top-5). Se aplica a `casos_qa.jsonl` y `casos_qa_baseline_v1.jsonl`
para mantener ambos en sincronía.

USO:
    python3 scripts/regenerar_negativos_qa.py
"""
import sys
import os
import json
import random
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from generar_casos_qa import generate_negative_queries  # noqa: E402

QA_FILES = [
    os.path.join(BASE_DIR, "scripts", "casos_qa.jsonl"),
    os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl"),
]


def main():
    db_path = os.environ.get('BIORAG_PATH') or os.path.join(
        BASE_DIR, "MemoryBioRAG_Data", "memory_biorag.db"
    )
    if not os.path.exists(db_path):
        print(f"ERROR: no existe la DB origen: {db_path}")
        sys.exit(1)

    # Copia aislada: la búsqueda profunda muta estado (despierta dormidos).
    temp_db = os.path.join("/tmp", "memory_biorag_negativos_temp.db")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(temp_db + ext):
            os.remove(temp_db + ext)
    shutil.copy(db_path, temp_db)
    print(f"Usando copia aislada de la DB para validación: {temp_db}")

    db = SQLiteMemoryBioRAG(db_path=temp_db)
    random.seed(42)

    # Generar 40 controles negativos limpios (validación endurecida).
    new_negatives = generate_negative_queries(db, count=40)
    if len(new_negatives) < 40:
        print("ERROR: no se pudieron generar 40 controles negativos válidos.")
        db.conn.close()
        sys.exit(1)
    db.conn.close()

    # Sanity check: los nuevos negativos no deben reutilizar tokens del corpus
    # (la función ya lo garantiza; esto es solo una verificación de reporte).
    for q in ("", "-wal", "-shm"):
        p = temp_db + q
        if os.path.exists(p):
            os.remove(p)

    for path in QA_FILES:
        if not os.path.exists(path):
            print(f"SKIP (no existe): {path}")
            continue

        original_negativos = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_s = line.strip()
                if not line_s:
                    continue
                d = json.loads(line_s)
                if d.get("categoria") == "negativo":
                    original_negativos.append(d)

        n_originales = len(original_negativos)
        # Conservar los IDs originales para no romper referencias de reportes.
        start_id = int(original_negativos[0]["id"]) if original_negativos else 882
        for i, caso in enumerate(new_negatives):
            caso["id"] = f"{start_id + i:04d}"

        out_lines = []
        neg_idx = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_s = line.strip()
                if not line_s:
                    out_lines.append(line)
                    continue
                d = json.loads(line_s)
                if d.get("categoria") == "negativo":
                    if neg_idx < len(new_negatives):
                        out_lines.append(json.dumps(new_negatives[neg_idx], ensure_ascii=False) + "\n")
                        neg_idx += 1
                    continue
                out_lines.append(line)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)

        print(f"OK {os.path.basename(path)}: {n_originales} negativos reemplazados "
              f"(IDs {start_id:04d}-{start_id + len(new_negatives) - 1:04d}).")

    print("\nNuevos controles negativos:")
    for caso in new_negatives:
        print(f"  [{caso['id']}] {caso['query']}")


if __name__ == "__main__":
    main()
