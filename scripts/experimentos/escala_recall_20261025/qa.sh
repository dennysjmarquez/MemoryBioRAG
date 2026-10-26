#!/bin/bash
# uso: qa.sh <etiqueta> <db>   — QA oficial (evaluar_qa.py), fórmula sola, sobre una COPIA
cd /home/user/MemoryBioRAG
export PATH=/home/user/.biorag-venv/bin:$PATH PYTHONPATH=/home/user/MemoryBioRAG PYTHONHASHSEED=1 BIORAG_NEURONA=0
export BIORAG_PATH="$2" BIORAG_ESCALA="${ESC:-1}" BIORAG_QA_FAILED_CASES=/tmp/v/fallos_$1.jsonl BIORAG_QA_METRICS=/tmp/v/met_$1.json BIORAG_QA_GATE=0
python3 scripts/evaluar_qa.py > /tmp/v/qa_$1.txt 2>&1
echo "QA_FIN $1 rc=$?" >> /tmp/v/qa_$1.txt
