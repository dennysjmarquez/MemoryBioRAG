#!/bin/bash
set -e

# Directorio raíz del proyecto
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"

# 1. Cargar .env.local si existe (para variables y overrides locales)
if [ -f "$PARENT_DIR/.env.local" ]; then
    echo "Cargando variables desde .env.local..."
    set -a
    # shellcheck disable=SC1091
    source "$PARENT_DIR/.env.local"
    set +a
fi

# 2. Resolver DB origen: BIORAG_PATH explícito del entorno > DB viva del repo
if [ -n "$BIORAG_PATH" ]; then
    SRC_DB="$BIORAG_PATH"
    echo "Usando BIORAG_PATH explícito como origen: $SRC_DB"
else
    SRC_DB="$PARENT_DIR/MemoryBioRAG_Data/memory_biorag.db"
    echo "BIORAG_PATH no definido -> Usando DB viva del repo: $SRC_DB"
fi

if [ ! -f "$SRC_DB" ]; then
    echo "ERROR: No existe la base de datos origen: $SRC_DB" >&2
    exit 1
fi

# 3. Crear copia aislada para toda la suite (protección total: original nunca se toca)
QA_DB="$PARENT_DIR/MemoryBioRAG_Data/memory_biorag_qa_run.db"
echo "Creando copia aislada para la suite: $QA_DB"
rm -f "$QA_DB" "$QA_DB-wal" "$QA_DB-shm"
python3 -c "
import sqlite3
src = sqlite3.connect('$SRC_DB')
dst = sqlite3.connect('$QA_DB')
# usar checkpoint en modo solo-lectura (no reescribe el archivo principal):
src.execute('PRAGMA wal_checkpoint(PASSIVE);')
src.backup(dst)
src.close()
dst.close()
"

# 4. Exportar BIORAG_PATH a la copia para TODOS los hijos
export BIORAG_PATH="$QA_DB"
echo "BIORAG_PATH exportado a copia aislada: $BIORAG_PATH"

# 5. Función de limpieza
cleanup() {
    echo "Limpiando copia temporal..."
    rm -f "$QA_DB" "$QA_DB-wal" "$QA_DB-shm"
}
trap cleanup EXIT

echo "================================================================================"
echo "          INICIANDO SUITE INTEGRAL DE CALIDAD Y REGRESIÓN BIORAG"
echo "================================================================================"

# Opción para regenerar la baseline si se solicita
if [ "$1" == "--generate-baseline" ] || [ "$1" == "generate" ]; then
    echo "Regenerando QA baseline..."
    python3 "$PARENT_DIR/scripts/generar_casos_qa.py"
    cp "$PARENT_DIR/scripts/casos_qa.jsonl" "$PARENT_DIR/scripts/casos_qa_baseline_v1.jsonl"
    echo "Baseline regenerada y almacenada en casos_qa_baseline_v1.jsonl."
    shift
fi

# Flag para correr solo pruebas rápidas/unitarias
if [ "$1" == "--unit" ] || [ "$1" == "-u" ] || [ "$1" == "--quick" ]; then
    RUN_QA_921=false
    shift
else
    RUN_QA_921=true
fi

# Flag para correr solo evaluación QA 921
if [ "$1" == "--qa-only" ]; then
    RUN_UNIT=false
    shift
else
    RUN_UNIT=true
fi

if [ "$RUN_UNIT" = true ]; then
    echo ""
    echo "─── [1/4] TESTS UNITARIOS (Pytest) ─────────────────────────────────────────────"
    python3 -m pytest "$PARENT_DIR/tests/" -v

    echo ""
    echo "─── [2/4] INVARIANTES DE SCORING HÍBRIDO (Monotonía y Preservación) ────────────"
    python3 "$PARENT_DIR/scripts/test_regresion_scoring.py"

    echo ""
    echo "─── [3/4] SUITE CONCEPT HUB (Búsqueda Semántica Pura sin Overlap Léxico) ───────"
    python3 "$PARENT_DIR/scripts/test_concept_hub.py"
fi

if [ "$RUN_QA_921" = true ]; then
    echo ""
    echo "─── [4/4] EVALUACIÓN GLOBAL QA (921 Casos de Regresión) ────────────────────────"
    python3 "$PARENT_DIR/scripts/evaluar_qa.py" "$@"
fi

echo ""
echo "================================================================================"
echo "          SUITE DE EVALUACIÓN BIORAG FINALIZADA CON ÉXITO"
echo "================================================================================"