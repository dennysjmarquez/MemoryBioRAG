#!/usr/bin/env bash
# Corre el QA oficial de punta a punta: pesos base y luego cada archivo de pesos dado.
# Uso (desde cualquier sitio):  bash correr_qa_motor.sh etiqueta=ruta.npz ...
set -u
E="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$E/../../.." && pwd)"
PY="${PY:-python3}"
cd "$REPO"
export BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db PYTHONHASHSEED=1
for par in "$@"; do
  et="${par%%=*}"; pz="${par#*=}"
  if [ "$pz" = "base" ]; then
    "$PY" "$E/qa_con_neurona.py" --etiqueta "$et" > "$E/resultados/qa_motor_$et.txt" 2>&1
  else
    "$PY" -u "$E/qa_con_neurona.py" --etiqueta "$et" --pesos "$E/$pz" ${MODO:+--modo $MODO} > "$E/resultados/qa_motor_$et.txt" 2>&1
  fi
  echo "terminado $et (exit $?)"
done
