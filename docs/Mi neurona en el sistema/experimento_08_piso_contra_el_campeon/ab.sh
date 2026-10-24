#!/usr/bin/env bash
# Experimento 08 — una corrida del A/B: práctica determinista + QA oficial + camino MCP.
#   ab.sh <etiqueta> <árbol de código> [variables extra, ej. BIORAG_NEURONA_TOL_CAMPEON=1]
# A = árbol de HEAD (antes del cambio). B = árbol con el piso contra el campeón.
# Siempre sobre una COPIA nueva del snapshot; nunca dos evaluaciones pesadas a la vez.
set -u
ET="$1"; ARBOL="$2"; shift 2
E8="$(cd "$(dirname "$0")" && pwd)"
R="$E8/resultados"; T=/tmp/q/e08
PY=${PYTHON:-/home/user/.biorag-venv/bin/python}
mkdir -p "$R" "$T"
export PYTHONHASHSEED=1 BIORAG_NEURONA_PRESUPUESTO_S=1000 "$@"
rm -f "$T/$ET".db*
cp /home/user/MemoryBioRAG/snapshots/qa_escape_qcr_20260811.db "$T/$ET.db"
$PY "$E8/practicar_ab.py" --repo "$ARBOL" --db "$T/$ET.db" --ciclos 500 \
    --salida "$R/curva_$ET.jsonl" 2>&1 | grep -v "^\[PMI\]\|^\[TRACE\]" > "$R/practica_$ET.txt"
echo "practica $ET ok"
cp "$T/$ET.db" "$T/${ET}_mcp.db"
(cd "$ARBOL" && BIORAG_PATH="$T/$ET.db" $PY scripts/evaluar_qa.py > "$T/qa_$ET.txt" 2>&1)
grep -A40 "BIORAG QA EVALUATION REPORT" "$T/qa_$ET.txt" | head -24 > "$R/qa_oficial_$ET.txt"
grep "\[GATE\]" "$T/qa_$ET.txt" >> "$R/qa_oficial_$ET.txt"
echo "qa $ET ok"
(cd "$ARBOL/docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha" && \
  BIORAG_PATH="$T/${ET}_mcp.db" BIORAG_NEURONA=1 $PY evaluar_camino_mcp.py --salida "$R/mcp_$ET.json" \
  2>&1 | grep -v "^\[PMI\]\|^\[TRACE\]" | tail -30 > "$R/mcp_$ET.txt")
echo "mcp $ET ok"
