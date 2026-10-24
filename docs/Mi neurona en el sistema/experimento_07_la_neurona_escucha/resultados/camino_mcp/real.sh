#!/usr/bin/env bash
# Código REAL (arreglo del MCP aplicado, sin interceptor): mano y v4, QA + pydocs.
set -u
cd "/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha"
L=/home/user/lab_neurona/e07
PY=/home/user/.biorag-venv/bin/python
EX="/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_06_capas_de_proteccion/resultados/v4/examen_humano_pydocs.jsonl"
export PYTHONHASHSEED=1
corre () {  # etiqueta, neurona, db, args...
  local et=$1 nn=$2 db=$3; shift 3
  cp $db $L/ab.db; rm -f $L/ab.db-wal $L/ab.db-shm
  BIORAG_NEURONA=$nn BIORAG_PATH=$L/ab.db $PY evaluar_camino_mcp.py --salida $L/real_$et.json "$@" > $L/real_$et.txt 2>&1
  echo "$et ok"
}
corre py_mano 0 /home/user/lab_neurona/v4_pydocs.db --casos "$EX"
corre py_v4 1 /home/user/lab_neurona/v4_pydocs_uso.db --casos "$EX"
corre mano 0 /home/user/MemoryBioRAG/snapshots/qa_escape_qcr_20260811.db
corre v4 1 /home/user/lab_neurona/v4_largo.db
echo "fin"
