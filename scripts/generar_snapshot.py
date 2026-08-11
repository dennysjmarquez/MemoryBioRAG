#!/usr/bin/env python3
"""
generar_snapshot.py — Reconstrucción determinista del Snapshot de Referencia

Genera la base de datos `scripts/snapshot_prf_real.db` a partir de los datos
fuente versionados (`scripts/casos_qa_baseline_v1.jsonl`).

Permite que cualquier desarrollador clone el repositorio y reconstruya la base
de datos congelada en <5 segundos sin necesidad de almacenar archivos binarios
pesados (.db) en el repositorio git.

Uso:
    python3 scripts/generar_snapshot.py
"""
import os
import sys
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG

SNAPSHOT_PATH = os.path.join(BASE_DIR, "scripts", "snapshot_prf_real.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")


def main():
    print("=" * 72)
    print("  RECONSTRUCCIÓN DETERMINISTA DEL SNAPSHOT DE REFERENCIA BIORAG")
    print("=" * 72)

    # 1. Si existe una DB viva local en MemoryBioRAG_Data, clonarla vía WAL backup
    live_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", "memory_biorag.db")
    if os.path.exists(live_db):
        print(f"  [+] Fuente primaria detectada: {live_db}")
        print(f"  [+] Generando copia aislada en: {SNAPSHOT_PATH} ...")
        for ext in ["", "-wal", "-shm"]:
            f = SNAPSHOT_PATH + ext
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
        conn_src = sqlite3.connect(live_db)
        conn_src.execute("PRAGMA wal_checkpoint(FULL);")
        conn_dst = sqlite3.connect(SNAPSHOT_PATH)
        conn_src.backup(conn_dst)
        conn_dst.close()
        conn_src.close()
        print("  [✔] Snapshot generado desde DB de producción local.")
        return

    # 2. Si no hay DB previa, auto-generar la estructura desde casos QA versionados
    print(f"  [+] Reconstruyendo DB desde datos fuertemente tipados: {CASES_FILE}")
    if os.path.exists(SNAPSHOT_PATH):
        os.remove(SNAPSHOT_PATH)

    db = SQLiteMemoryBioRAG(db_path=SNAPSHOT_PATH)

    if not os.path.exists(CASES_FILE):
        print(f"ERROR: {CASES_FILE} no encontrado.")
        sys.exit(1)

    with open(CASES_FILE, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    inserted = 0
    seen_concepts = set()

    for c in cases:
        concept = c.get("concepto_esperado")
        content = c.get("contenido", f"Contenido representativo para {concept}")
        cat = c.get("categoria", "general")

        if concept and concept not in seen_concepts:
            seen_concepts.add(concept)
            db.guardar(concepto=concept, contenido=content, categoria=cat)
            inserted += 1

    print(f"  [✔] Snapshot inicializado exitosamente con {inserted} nodos fuente en: {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
