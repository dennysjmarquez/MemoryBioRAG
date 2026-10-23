#!/usr/bin/env bash
# Pipeline v5 (experimento 07): mismo protocolo que v4 + QA por el camino MCP.
set -u
L=/home/user/lab_neurona
E="/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_05_neurona_cableada"
E7="/home/user/MemoryBioRAG/docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha"
R="$E7/resultados/v5"
PY=/home/user/.biorag-venv/bin/python
export PYTHONHASHSEED=1
mkdir -p "$R"; cd "$E"
rm -f $L/v5_*.db*
cp /home/user/MemoryBioRAG/snapshots/qa_escape_qcr_20260811.db $L/v5_uso.db
$PY simular_uso.py --db $L/v5_uso.db --ciclos 500 --salida "$R/curva_uso_snapshot.jsonl" > $L/v5_sim.log 2>&1
cp $L/v5_uso.db $L/v5_largo.db; cp $L/v5_uso.db $L/v5_mcp.db; echo "sim ok"
bash $L/qa_db.sh v5_largo $L/v5_largo.db &
QA=$!
$PY construir_db_desconocida.py --docs $L/pyes --db $L/v5_pydocs.db --examen "$R/examen_humano_pydocs.jsonl" --traza "$R/construccion_pydocs.jsonl" > $L/v5_pydocs.log 2>&1
cp $L/v5_pydocs.db $L/v5_pydocs_uso.db
$PY simular_uso.py --db $L/v5_pydocs_uso.db --ciclos 300 --salida "$R/curva_uso_pydocs.jsonl" > $L/v5_simpy.log 2>&1
$PY examen_humano.py --db $L/v5_pydocs_uso.db --examen "$R/examen_humano_pydocs.jsonl" --salida "$R/examen_humano_pydocs_tras_uso.json" > $L/v5_ex.log 2>&1
echo "pydocs ok"
wait $QA; echo "qa ok"
cd "$E7"
cp $L/v5_pydocs.db $L/v5_pydocs_mano.db
BIORAG_PATH=$L/v5_pydocs_mano.db BIORAG_NEURONA=0 $PY evaluar_camino_mcp.py --casos "$R/examen_humano_pydocs.jsonl" --salida "$R/mcp_pydocs_mano.json" > $L/e07/mcp_pydocs_mano.txt 2>&1
cp $L/v5_pydocs_uso.db $L/v5_pydocs_mcp.db
BIORAG_PATH=$L/v5_pydocs_mcp.db BIORAG_NEURONA=1 $PY evaluar_camino_mcp.py --casos "$R/examen_humano_pydocs.jsonl" --salida "$R/mcp_pydocs_v5.json" > $L/e07/mcp_pydocs_v5.txt 2>&1
echo "mcp pydocs ok"
BIORAG_PATH=$L/v5_mcp.db BIORAG_NEURONA=1 $PY evaluar_camino_mcp.py --salida "$R/mcp_v5.json" > $L/e07/mcp_v5.txt 2>&1
echo "todo ok"
