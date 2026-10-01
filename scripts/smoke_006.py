#!/usr/bin/env python3
"""
Smoke test baseline para Spec 006: Convergencia Multi-Campo.
Ejecuta búsquedas sobre una copia temporal y segura de la base de datos de producción
para capturar la posición de los nodos sin modificar la base original.
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# Iniciar entorno defensivo
os.environ["BIORAG_DMN_SINTESIS_ACTIVA"] = "0"
os.environ["BIORAG_NO_LOG"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.memory_store import SQLiteMemoryBioRAG

PROD_DB = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"
OUTPUT_PATH = ROOT / "scripts" / "smoke_006_antes.json"

QUERY = "cual es la ultima version de biorag"


def _copia_segura(ruta_original: Path) -> str:
    """Crea una copia temporal de la DB usando SQLite backup en modo solo lectura."""
    fd, tmp_path = tempfile.mkstemp(suffix="_smoke006.db")
    os.close(fd)
    
    src = sqlite3.connect(f"file:{ruta_original}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp_path)
    src.backup(dst)
    dst.close()
    src.close()
    return tmp_path


def main():
    if not PROD_DB.exists():
        print(f"ERROR: No se encontró la DB de producción en {PROD_DB}", file=sys.stderr)
        sys.exit(1)

    tmp_db = _copia_segura(PROD_DB)
    try:
        os.environ["BIORAG_PATH"] = tmp_db
        cerebro = SQLiteMemoryBioRAG(db_path=tmp_db)
        
        # Realizar búsqueda
        resultados, total = cerebro.buscar_por_frase(QUERY, limite=5, preview_chars=120)
        
        # Estructurar top-5
        top_5 = []
        origenes = getattr(cerebro, "last_origen_scores", {}) or {}
        for i, res in enumerate(resultados[:5], start=1):
            concepto = res[0]
            score = float(res[4])
            origen_info = origenes.get(concepto)
            if origen_info and isinstance(origen_info, (tuple, list)):
                origen = origen_info[0]
            elif len(res) > 6:
                origen = res[6]
            else:
                origen = "literal"
            top_5.append({
                "posicion": i,
                "concepto": concepto,
                "score": score,
                "origen": origen
            })
        
        cerebro.cerrar_sistema()

        payload = {
            "query": QUERY,
            "total_encontrados": total,
            "top_5": top_5
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            
        print(f"Top 5 capturado en {OUTPUT_PATH}:")
        for item in top_5:
            print(f"  #{item['posicion']} [{item['score']:.4f}] {item['concepto']} (origen: {item['origen']})")

    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)


if __name__ == "__main__":
    main()
