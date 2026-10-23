#!/usr/bin/env bash
# Reproduce el experimento 06 (≈ 1 h en 2 CPUs). Nada toca el snapshot ni la DB viva:
# todo corre sobre copias en $LAB. Usa los simuladores del experimento 05.
#   LAB=/ruta/de/trabajo PY=/ruta/python bash correr_validacion.sh
set -u
E="$(cd "$(dirname "$0")" && pwd)"
E5="$E/../experimento_05_neurona_cableada"
REPO="$(cd "$E/../../.." && pwd)"
R="$E/resultados"
LAB="${LAB:-$HOME/lab_neurona}"
PY="${PY:-python3}"
SNAP="$REPO/snapshots/qa_escape_qcr_20260811.db"
export PYTHONHASHSEED=1
mkdir -p "$LAB" "$R/v4" "$R/qa"

qa() {  # qa etiqueta db
  (cd "$REPO" && BIORAG_PATH="$2" BIORAG_QA_METRICS="$R/qa/$1.json" BIORAG_QA_FAILED_CASES="$LAB/$1_fallidos.jsonl" \
     "$PY" scripts/evaluar_qa.py > "$R/qa/$1.txt" 2>&1)
}

# 0) Pruebas automáticas de todas las capas (y del resto del motor).
(cd "$REPO" && "$PY" -m pytest -q tests/) > "$R/pytest.txt" 2>&1

# 1) Neurona cableada sin nada aprendido: debe ser IDÉNTICA a la base.
qa qa_sin_pesos "$SNAP"

# 2) Uso simulado sobre una copia del snapshot (500 consolidaciones) con margen automático.
cp "$SNAP" "$LAB/v4_uso.db"
cd "$E5"
"$PY" simular_uso.py --db "$LAB/v4_uso.db" --ciclos 500 --salida "$R/v4/curva_uso_snapshot.jsonl"
cp "$LAB/v4_uso.db" "$LAB/v4_largo.db"; qa qa_v4_largo "$LAB/v4_largo.db"

# 3) Datos que nunca vio (doc de Python en español) + examen con preguntas humanas.
[ -d "$LAB/pyes" ] || git clone --depth 1 https://github.com/python/python-docs-es.git "$LAB/pyes"
"$PY" -m pip show polib >/dev/null 2>&1 || "$PY" -m pip install polib
rm -f "$LAB/v4_pydocs.db"*
"$PY" construir_db_desconocida.py --docs "$LAB/pyes" --db "$LAB/v4_pydocs.db" \
    --examen "$R/v4/examen_humano_pydocs.jsonl" --traza "$R/v4/construccion_pydocs.jsonl"
cp "$LAB/v4_pydocs.db" "$LAB/v4_pydocs_uso.db"
"$PY" simular_uso.py --db "$LAB/v4_pydocs_uso.db" --ciclos 300 --salida "$R/v4/curva_uso_pydocs.jsonl"
"$PY" examen_humano.py --db "$LAB/v4_pydocs_uso.db" --examen "$R/v4/examen_humano_pydocs.jsonl" \
    --salida "$R/v4/examen_humano_pydocs_tras_uso.json"

# 4) De punta a punta por el MCP: con y sin neurona, mismos nombres y números (solo cambia el orden).
cd "$E"
BIORAG_PATH="$LAB/v4_largo.db" "$PY" mcp_con_y_sin_neurona.py --n 120 --salida "$R/v4/mcp_con_y_sin_neurona.json"
echo "listo: resultados en $R"
