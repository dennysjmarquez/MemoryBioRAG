#!/usr/bin/env bash
set -u
cd "/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha"
L=/home/user/lab_neurona/e07
PY=/home/user/.biorag-venv/bin/python
export PYTHONHASHSEED=1 BIORAG_NEURONA=0
corre () {  # etiqueta, args...
  local et=$1; shift
  cp /home/user/MemoryBioRAG/snapshots/qa_escape_qcr_20260811.db $L/ab.db; rm -f $L/ab.db-wal $L/ab.db-shm
  BIORAG_PATH=$L/ab.db $PY evaluar_camino_mcp.py --salida $L/ab_$et.json "$@" > $L/ab_$et.txt 2>&1
  echo "$et ok"
}
corre mano
corre sin_todo --quitar peso,sustantivos,parafrasis,dims,pool
for q in peso sustantivos parafrasis dims pool; do corre sin_$q --sin literal --quitar $q; done
echo "todo ok"
