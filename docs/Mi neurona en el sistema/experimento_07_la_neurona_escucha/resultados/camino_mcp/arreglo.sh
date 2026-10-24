#!/usr/bin/env bash
set -u
cd "/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha"
L=/home/user/lab_neurona/e07
PY=/home/user/.biorag-venv/bin/python
EX="/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_06_capas_de_proteccion/resultados/v4/examen_humano_pydocs.jsonl"
export PYTHONHASHSEED=1 BIORAG_NEURONA=0
corre () {  # etiqueta, db, args...
  local et=$1 db=$2; shift 2
  cp $db $L/ab.db; rm -f $L/ab.db-wal $L/ab.db-shm
  BIORAG_PATH=$L/ab.db $PY evaluar_camino_mcp.py --salida $L/ab_$et.json "$@" > $L/ab_$et.txt 2>&1
  echo "$et ok"
}
S=/home/user/MemoryBioRAG/snapshots/qa_escape_qcr_20260811.db
P=/home/user/lab_neurona/v4_pydocs.db
corre py_mano $P --casos "$EX"
corre py_sin_parafrasis_dims $P --casos "$EX" --quitar parafrasis,dims
corre py_sin_parafrasis $P --casos "$EX" --quitar parafrasis
corre py_sin_dims $P --casos "$EX" --quitar dims
corre py_sin_todo $P --casos "$EX" --quitar peso,sustantivos,parafrasis,dims,pool
corre sin_parafrasis_dims $S --quitar parafrasis,dims
echo "fin"
