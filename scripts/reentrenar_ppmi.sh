#!/bin/bash
set -e

# ================================================================================
# BioRAG — Reentrenamiento FORZADO de vectores PPMI+SVD (Signal #13)
# --------------------------------------------------------------------------------
# Uso:
#   ./scripts/reentrenar_ppmi.sh                       # sobre la DB de producción
#   ./scripts/reentrenar_ppmi.sh scripts/snapshot.db   # sobre cualquier DB
#   BIORAG_PATH=/ruta/memory_biorag.db ./scripts/reentrenar_ppmi.sh
#
# Qué hace: fuerza el FULL reindex espectral (SVD + Retrofitting) sobre la DB
# indicada, regenerando las tablas `tokens` y `nodos` (vectores). No depende de
# las condiciones automáticas (≥7 días Y ≥50 nodos): reentrena YA.
#
# El mecanismo automático (fold-in / full diferido) se documenta en README,
# sección "Reentrenar los vectores PPMI+SVD manualmente (Signal #13)".
# ================================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"

DEFAULT_DB="$PARENT_DIR/MemoryBioRAG_Data/memory_biorag.db"
DB_PATH="${1:-${BIORAG_PATH:-$DEFAULT_DB}}"

if [ ! -f "$DB_PATH" ]; then
    echo "[ERROR] Base de datos no encontrada: $DB_PATH"
    echo "        Uso: ./scripts/reentrenar_ppmi.sh [path_a_db.db]"
    exit 1
fi

echo "================================================================================"
echo "BioRAG — Reentrenamiento FORZADO PPMI+SVD"
echo "================================================================================"
echo "DB: $DB_PATH"
echo ""

BIORAG_DB="$DB_PATH" python3 "$PARENT_DIR/scripts/reentrenar_ppmi.py"

echo "================================================================================"
echo "Reentrenamiento completo."
echo "================================================================================"
