#!/usr/bin/env bash
# Experimento 09 — A/B completo. A = código de v34.0 (2 recuerdos x 2 preguntas por
# consolidación), B = v34.1 (8 x 7 dentro de 3 s + repasar primero el grupo del examen
# al que más le faltan preguntas). Nunca dos evaluaciones pesadas a la vez.
#   correr.sh <árbol A> <árbol B>
#   (A: mkdir -p /tmp/q/e09/base && git archive 55dc8f5 | tar -x -C /tmp/q/e09/base
#       y copiar MemoryBioRAG_Data/nltk_data)
set -u
A="$1"; B="$2"
E9="$(cd "$(dirname "$0")" && pwd)"; R="$E9/resultados"; T=/tmp/q/e09
PY=${PYTHON:-/home/user/.biorag-venv/bin/python}
SNAP="$(cd "$E9/../../.." && pwd)/snapshots/qa_escape_qcr_20260811.db"
mkdir -p "$R" "$T/nueva"
export PYTHONHASHSEED=1
# 1) DB nueva que crece: 80 sesiones, usuario normal (5 recuerdos/sesión) y ligero (2)
for cfg in "antes $A" "despues $B"; do set -- $cfg
  for ps in 5 2; do
    REPO=$2 BIORAG_PATH=$T/nueva $PY "$E9/simular_db_nueva.py" $ps 80 "$T/nueva/sim_$1_$ps.db" > "$R/sim_$1_$ps.txt" 2>&1
  done
done
# 2) Snapshot canónico: despertar 17 min (mismo tiempo para los dos) + QA oficial + camino MCP
for cfg in "antes $A" "despues $B"; do set -- $cfg
  rm -f "$T/$1".db*; cp "$SNAP" "$T/$1.db"
  (cd $2 && PYTHON=$PY ./scripts/despertar_neurona.sh "$T/$1.db" --minutos 17 --ciclos 100000 --sin-respaldo > "$R/despertar_$1.txt" 2>&1)
  cp "$T/$1.db" "$T/$1_mcp.db"
  (cd $2 && BIORAG_PATH="$T/$1.db" $PY scripts/evaluar_qa.py > "$T/qa_$1.txt" 2>&1)
  grep -A40 "BIORAG QA EVALUATION REPORT" "$T/qa_$1.txt" | head -24 > "$R/qa_oficial_$1.txt"
  grep "\[GATE\]" "$T/qa_$1.txt" >> "$R/qa_oficial_$1.txt"
  (cd "$2/docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha" && \
    BIORAG_PATH="$T/$1_mcp.db" BIORAG_NEURONA=1 $PY evaluar_camino_mcp.py --salida "$R/mcp_$1.json" \
    2>&1 | grep -v "^\[PMI\]\|^\[TRACE\]" | tail -30 > "$R/mcp_$1.txt")
done
echo TODO_OK
