#!/bin/bash
set -e

# ================================================================================
# BioRAG — Despertar la neurona (práctica acelerada sobre los recuerdos existentes)
# --------------------------------------------------------------------------------
# Uso:
#   ./scripts/despertar_neurona.sh                         # sobre la DB de producción
#   ./scripts/despertar_neurona.sh ruta/copia.db           # sobre cualquier DB
#   ./scripts/despertar_neurona.sh ruta/copia.db --ciclos 300
#   ./scripts/despertar_neurona.sh --estado                # solo mirar (no escribe)
#   ./scripts/despertar_neurona.sh --olvidar --si          # volver a los pesos a mano
#   BIORAG_PATH=/ruta/memory_biorag.db ./scripts/despertar_neurona.sh
#
# Qué hace: repite N veces lo mismo que corre la neurona tras cada consolidación
# (neurona.practicar), con las mismas protecciones. Solo escribe `neurona_estado`.
# Hace un respaldo de la DB antes (API backup de SQLite) salvo --sin-respaldo.
#
# Documentado en README, sección "La Neurona de BioRAG" -> "Despertar la neurona".
# ================================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"

DEFAULT_DB="$PARENT_DIR/MemoryBioRAG_Data/memory_biorag.db"
DB_PATH="${BIORAG_PATH:-$DEFAULT_DB}"
if [ -n "$1" ] && [ "${1#-}" = "$1" ]; then
    DB_PATH="$1"
    shift
fi

if [ ! -f "$DB_PATH" ]; then
    echo "[ERROR] Base de datos no encontrada: $DB_PATH"
    echo "        Uso: ./scripts/despertar_neurona.sh [path_a_db.db] [--ciclos N] [--estado] [--olvidar --si]"
    exit 1
fi

"${PYTHON:-python3}" "$PARENT_DIR/scripts/despertar_neurona.py" "$DB_PATH" "$@"
