#!/usr/bin/env bash
# Reproduce TODO el experimento 05 (≈ 1 h en 2 CPUs). Nada toca el snapshot ni la DB viva:
# todo corre sobre copias en $LAB.
#   LAB=/ruta/de/trabajo PY=/ruta/python bash correr_validacion.sh
set -u
E="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$E/../../.." && pwd)"
R="$E/resultados"
LAB="${LAB:-$HOME/lab_neurona}"
PY="${PY:-python3}"
SNAP="$REPO/snapshots/qa_escape_qcr_20260811.db"
export PYTHONHASHSEED=1
mkdir -p "$LAB" "$R"

qa() {  # qa etiqueta db
  (cd "$REPO" && BIORAG_PATH="$2" BIORAG_QA_METRICS="$R/$1.json" BIORAG_QA_FAILED_CASES="$LAB/$1_fallidos.jsonl" \
     "$PY" scripts/evaluar_qa.py > "$R/$1.txt" 2>&1)
}

# 0) QA con la neurona cableada pero sin nada aprendido: debe ser IDÉNTICO a la base.
#    (La base con el código sin cambios se corre igual desde un worktree del commit anterior.)
qa qa_01_cableada_sin_pesos "$SNAP"

# 1) Uso real simulado sobre una copia del snapshot: consolidaciones hasta el primer techo…
cp "$SNAP" "$LAB/uso.db"
cd "$E"
"$PY" simular_uso.py --db "$LAB/uso.db" --ciclos 700 --parar-en-techo --salida "$R/curva_uso_snapshot.jsonl"
cp "$LAB/uso.db" "$LAB/techo1.db"; qa qa_03_v2_primer_techo_sin_campeon "$LAB/techo1.db"
# …y 400 consolidaciones más (despierta cuando juntó preguntas nuevas).
"$PY" simular_uso.py --db "$LAB/uso.db" --ciclos 400 --salida "$R/curva_uso_snapshot_continuacion.jsonl"
cp "$LAB/uso.db" "$LAB/largo.db"; qa qa_04_v2_474_consolidaciones "$LAB/largo.db"

# 2) Datos que nunca vio: DB nueva desde cero (doc de Python en español) + examen humano.
[ -d "$LAB/pyes" ] || git clone --depth 1 https://github.com/python/python-docs-es.git "$LAB/pyes"
"$PY" -m pip show polib >/dev/null 2>&1 || "$PY" -m pip install polib
rm -f "$LAB/pydocs.db"*
"$PY" construir_db_desconocida.py --docs "$LAB/pyes" --db "$LAB/pydocs.db" \
    --examen "$R/examen_humano_pydocs.jsonl" --traza "$R/construccion_pydocs.jsonl"
"$PY" examen_humano.py --db "$LAB/pydocs.db" --examen "$R/examen_humano_pydocs.jsonl" \
    --salida "$R/examen_humano_pydocs_tras_construir.json"
cp "$LAB/pydocs.db" "$LAB/pydocs_uso.db"
"$PY" simular_uso.py --db "$LAB/pydocs_uso.db" --ciclos 300 --salida "$R/curva_uso_pydocs.jsonl"
"$PY" examen_humano.py --db "$LAB/pydocs_uso.db" --examen "$R/examen_humano_pydocs.jsonl" \
    --salida "$R/examen_humano_pydocs_tras_uso.json"
echo "listo: resultados en $R"
