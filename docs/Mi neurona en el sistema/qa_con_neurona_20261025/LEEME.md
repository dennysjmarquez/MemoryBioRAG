# La neurona en la QA: evidencia (2026-10-25)

Salidas literales (sin las líneas de traza `[PMI]`/`[TRACE]`) de las corridas que validan el
cambio de `scripts/evaluar_qa.py` + `scripts/qa_neurona.py`. Todas en la misma máquina
(2 núcleos), con `PYTHONHASHSEED=1` y sobre copias del snapshot oficial
`snapshots/qa_escape_qcr_20260811.db` (sha256 `104dd290…9796`, sin cambios al final).

| Archivo | Corrida | Resultado |
|---|---|---|
| `r0.txt` | Código anterior (`a72d1f0`), snapshot | R@5 100 · R@1 91.89 · MRR 0.950 · FP 0/40 · GATE OK |
| `r2.txt` | Código nuevo, snapshot; "DB viva" = copia entrenada | tabla idéntica a `r0`; aviso "Tu neurona está ACTIVA en tu DB viva" + `--con-neurona` |
| `entrenar_copia_despertar.txt` | `despertar_neurona.py` sobre una copia (500 prácticas) | 10 aprobaciones, 0 retiros; control 68.7 % → 86.7 % |
| `r3.txt` | Código nuevo, esa copia entrenada | fórmula sola = `r0` en todas las categorías; con neurona R@1 94.40 · MRR 0.966 |
| `r4.txt` | La misma copia con `BIORAG_NEURONA=0` | tabla = `r0` = columna "fórmula sola" de `r3` |
| `r5.txt` | Código nuevo, snapshot, `--con-neurona` | R@1 91.89 → 94.97 · MRR 0.950 → 0.970 · 27 suben al 1er lugar, 0 bajan |
| `r6.txt` | `run_qa_suite.sh --qa-only --con-neurona`, respuesta **n** (terminal simulada con `script`) | pregunta, no entrena; tabla idéntica a `r0` |
| `entrenar_copia_5min.txt` | `despertar_neurona.py --minutos 5` sobre otra copia | 111 prácticas, 3 aprobaciones, 0 retiros |
| `r7.txt` | `run_qa_suite.sh --qa-only` sobre esa copia (sin `--con-neurona`) | no entrena; R@1 91.89 → 95.20 · MRR 0.950 → 0.971 |
| `r8.txt` | `evaluar_qa.py --con-neurona --minutos 5`, respuesta **s** | pregunta, entrena 110 prácticas, sigue: R@1 91.89 → 94.97 |

Los `*_metrics.json` son el `qa_metrics.json` de cada corrida (bloque `neurona` incluido desde `r2`).
`r0_metrics.json` no tiene ese bloque: es el código anterior.

Comandos (desde la raíz del repo; `/tmp/qa/snap.db` y `/tmp/qa/snap_train.db` son copias del snapshot):

Las corridas 6–8 se hicieron después de un reinicio del entorno (venv reconstruido), con el
script `validar.sh` cuyos comandos son, en orden:

```bash
printf 'n\n' | BIORAG_PATH=/tmp/qa/snap.db script -qec "./scripts/run_qa_suite.sh --qa-only --con-neurona" /dev/null
python scripts/despertar_neurona.py /tmp/qa/snap_train.db --sin-respaldo --minutos 5
BIORAG_PATH=/tmp/qa/snap_train.db ./scripts/run_qa_suite.sh --qa-only
printf 's\n' | BIORAG_PATH=/tmp/qa/snap.db BIORAG_QA_ORIGEN=snapshots/qa_escape_qcr_20260811.db script -qec "python scripts/evaluar_qa.py --con-neurona --minutos 5" /dev/null
```

Corridas 1–5:

```bash
# r0 / r2 (r2 con BIORAG_QA_ORIGEN=snapshots/... y BIORAG_QA_DB_VIVA=/tmp/qa/snap_train.db)
PYTHONHASHSEED=1 BIORAG_PATH=/tmp/qa/snap.db python scripts/evaluar_qa.py
# copia entrenada
python scripts/despertar_neurona.py /tmp/qa/snap_train.db --sin-respaldo
# r3 / r4
PYTHONHASHSEED=1 BIORAG_PATH=/tmp/qa/snap_train.db python scripts/evaluar_qa.py
BIORAG_NEURONA=0 PYTHONHASHSEED=1 BIORAG_PATH=/tmp/qa/snap_train.db python scripts/evaluar_qa.py
# r5
PYTHONHASHSEED=1 BIORAG_PATH=/tmp/qa/snap.db BIORAG_QA_ORIGEN=snapshots/qa_escape_qcr_20260811.db python scripts/evaluar_qa.py --con-neurona
```
