#!/usr/bin/env python3
"""
Smoke test riguroso y determinista para Spec 006: Convergencia Multi-Campo.
Ejecuta las 3 consultas clave sobre una única copia temporal de la DB,
registrando hash de DB (SHA256), commit git, flags de entorno y top-5 con orígenes.
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# Iniciar entorno defensivo
os.environ["BIORAG_DMN_SINTESIS_ACTIVA"] = "0"
os.environ["BIORAG_NO_LOG"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.memory import constants
from core.memory_store import SQLiteMemoryBioRAG

PROD_DB = ROOT / "MemoryBioRAG_Data" / "memory_biorag.db"
QUERIES = [
    "cual es la ultima version de biorag",
    "version actual biorag",
    "ultima version de biorag",
]


def _calcular_sha256(ruta: Path) -> str:
    """Calcula el hash SHA256 del archivo de base de datos."""
    sha = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def _obtener_git_commit() -> str:
    """Obtiene el commit actual del repositorio git."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "desconocido"


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


def ejecutar_smoke(output_file: str = "smoke_006_reporte.json"):
    if not PROD_DB.exists():
        print(f"ERROR: No se encontró la DB de producción en {PROD_DB}", file=sys.stderr)
        sys.exit(1)

    db_hash = _calcular_sha256(PROD_DB)
    git_commit = _obtener_git_commit()
    tmp_db = _copia_segura(PROD_DB)

    flags_entorno = {
        "BIORAG_CONVERGENCIA_ACTIVA": os.environ.get("BIORAG_CONVERGENCIA_ACTIVA", "0"),
        "CONVERGENCIA_ACTIVA_CONST": bool(constants.CONVERGENCIA_ACTIVA),
        "BIORAG_CONVERGENCIA_ALPHA": os.environ.get("BIORAG_CONVERGENCIA_ALPHA", "0.5"),
        "CONVERGENCIA_ALPHA_CONST": float(constants.CONVERGENCIA_ALPHA),
        "BIORAG_DMN_SINTESIS_ACTIVA": os.environ.get("BIORAG_DMN_SINTESIS_ACTIVA", "0"),
        "BIORAG_NO_LOG": os.environ.get("BIORAG_NO_LOG", "1"),
    }

    resultados_queries = []

    try:
        os.environ["BIORAG_PATH"] = tmp_db
        cerebro = SQLiteMemoryBioRAG(db_path=tmp_db)

        for query in QUERIES:
            resultados, total = cerebro.buscar_por_frase(query, limite=5, preview_chars=120)
            origenes = getattr(cerebro, "last_origen_scores", {}) or {}
            
            top_5 = []
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

            resultados_queries.append({
                "query": query,
                "total_encontrados": total,
                "top_5": top_5
            })

        cerebro.cerrar_sistema()

        payload = {
            "metadata": {
                "db_path": str(PROD_DB),
                "db_sha256": db_hash,
                "git_commit": git_commit,
                "flags": flags_entorno
            },
            "queries": resultados_queries
        }

        output_path = ROOT / "scripts" / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"Smoke test generado en: {output_path}")
        print(f"  DB SHA256: {db_hash[:16]}... | Commit: {git_commit[:8]} | Convergencia: {flags_entorno['CONVERGENCIA_ACTIVA_CONST']}")
        for q_res in resultados_queries:
            print(f"\n  Query: '{q_res['query']}' (Total: {q_res['total_encontrados']})")
            for item in q_res["top_5"]:
                print(f"    #{item['posicion']} [{item['score']:.4f}] {item['concepto']} (origen: {item['origen']})")

    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)


def main():
    out_file = sys.argv[1] if len(sys.argv) > 1 else "smoke_006_baseline.json"
    ejecutar_smoke(out_file)


if __name__ == "__main__":
    main()
