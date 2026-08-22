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

# 2. Snapshot de evaluación por defecto (protección contra mutación de DB en vivo)
DEFAULT_SNAPSHOT="$PARENT_DIR/snapshots/qa_escape_qcr_20260811.db"
if [ -z "$BIORAG_PATH" ]; then
    if [ -f "$DEFAULT_SNAPSHOT" ]; then
        export BIORAG_PATH="$DEFAULT_SNAPSHOT"
        echo "BIORAG_PATH no definido -> Usando snapshot oficial: $DEFAULT_SNAPSHOT"
    else
        echo "AVISO: No se encontró snapshot oficial en $DEFAULT_SNAPSHOT. Se usará la configuración por defecto."
    fi
else
    echo "Usando BIORAG_PATH configurado: $BIORAG_PATH"
fi

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

