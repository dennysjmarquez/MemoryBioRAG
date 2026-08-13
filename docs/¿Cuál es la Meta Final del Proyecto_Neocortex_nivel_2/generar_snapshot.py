#!/usr/bin/env python3
"""
generar_snapshot.py — Reconstrucción determinista del Snapshot de Referencia

Genera la base de datos `scripts/snapshot_prf_real.db` a partir de los datos
fuente versionados (`scripts/casos_qa_baseline_v1.jsonl`) o desde la DB de producción.

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


def validar_db_con_datos(db_path: str) -> bool:
    """Verifica que la base de datos exista Y tenga nodos cargados en largo_plazo."""
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cnt = conn.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'").fetchone()[0]
        conn.close()
        return cnt >= 50
    except Exception:
        return False


def _limpiar_db_incompleta(path: str):
    for ext in ["", "-wal", "-shm"]:
        f = path + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


def main():
    print("=" * 72)
    print("  RECONSTRUCCIÓN DETERMINISTA DEL SNAPSHOT DE REFERENCIA BIORAG")
    print("=" * 72)

    # 1. Si existe una DB viva local en MemoryBioRAG_Data con datos, clonarla vía WAL backup
    live_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", "memory_biorag.db")
    if validar_db_con_datos(live_db):
        print(f"  [+] Fuente primaria viva detectada: {live_db}")
        print(f"  [+] Generando copia aislada en: {SNAPSHOT_PATH} ...")
        _limpiar_db_incompleta(SNAPSHOT_PATH)
        conn_src = sqlite3.connect(live_db)
        conn_src.execute("PRAGMA wal_checkpoint(FULL);")
        conn_dst = sqlite3.connect(SNAPSHOT_PATH)
        conn_src.backup(conn_dst)
        conn_dst.close()
        conn_src.close()

        if validar_db_con_datos(SNAPSHOT_PATH):
            print("  [✔] Snapshot generado desde DB de producción local.")
            return

    # 2. Si no hay DB previa válida, reconstruir desde el JSONL versionado
    print(f"  [+] Reconstruyendo DB desde datos fuertemente tipados: {CASES_FILE}")
    _limpiar_db_incompleta(SNAPSHOT_PATH)

    if not os.path.exists(CASES_FILE):
        print(f"ERROR: {CASES_FILE} no encontrado.")
        sys.exit(1)

    with open(CASES_FILE, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    db = SQLiteMemoryBioRAG(db_path=SNAPSHOT_PATH)

    inserted = 0
    seen_concepts = set()

    # Mapeo de categorías del benchmark QA a categorías válidas del cerebro
    cat_map = {
        "literal": "General",
        "por_tema": "Cognition",
        "sinonimo": "General",
        "typo": "General",
        "variante_gramatical": "General",
        "pregunta_natural": "General",
        "cruce_idioma": "General",
        "dormido": "General"
    }

    for c in cases:
        concept = c.get("concepto_esperado")
        content = c.get("contenido") or f"Contenido representativo para {concept}"
        test_cat = c.get("categoria", "General")
        valid_cat = cat_map.get(test_cat, "General")
        syns = c.get("sinonimos", "")

        if concept and concept not in seen_concepts:
            seen_concepts.add(concept)
            # Usar API pública con categoría válida del cerebro
            db.percibir_corto_plazo(concepto=concept, contenido=content, sinonimos=syns, categoria=valid_cat)
            db.consolidar_concepto(concept)
            inserted += 1

    # Forzar optimización de FTS e índices
    db._poblar_fts()
    db.conn.commit()

    if validar_db_con_datos(SNAPSHOT_PATH):
        print(f"  [✔] Snapshot inicializado exitosamente con {inserted} nodos fuente en: {SNAPSHOT_PATH}")
    else:
        print(f"  [ERROR] La reconstrucción del snapshot falló.")
        _limpiar_db_incompleta(SNAPSHOT_PATH)
        sys.exit(1)


if __name__ == "__main__":
    main()
