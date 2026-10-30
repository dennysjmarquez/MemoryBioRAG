# E3 Cambio 2 — aplicación v2 y resultados

**Base de publicación:** `47f7f607d4d0f5a5ac6c4d10c3449fbd2d8d511a`  
**Diff aplicado:** `docs/e3_cambio2_aplicado_20261029.patch`  
**SHA-256 del diff final:** `abcc91be892e3ea7eaf9a5148d59a79c75ad9f6135da27e4491a94c442c9a817`  
**SHA-256 del patch v2 aprobado:** `82fa44297624cc65b5d46f7c461340a49eabe40adb345f9ddc3d5246150e0bb9`  
**QA viva usada:** `/tmp/viva_e3a.db`, SHA-256 `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a`. Ni el SQL ni la base se incluyen en este cambio.

La percepción con sustantivos vacíos **conserva** las etiquetas plegadas y exactas existentes en corto plazo. Si el concepto es nuevo, la etiqueta exacta queda `NULL`. No se fusionan etiquetas entre notas. No se tocó FTS, triggers, `MATCH`/BM25, búsqueda, backfill ni datos históricos.

## 1. QA oficiales de snapshot

Entorno de las corridas v2: `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, fuente `snapshots/qa_escape_qcr_20260811.db` con SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`; el evaluador trabajó sobre copias temporales. La cadena literal de las invocaciones snapshot no sobrevivió a la caché efímera; comandos de reproducción con esa configuración:

Normal:
```bash
PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. /home/user/.cache/e3-cambio2-apply/venv/bin/python scripts/evaluar_qa.py
```

Con ruido:
```bash
PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" BIORAG_QA_RUIDO=zzqx BIORAG_QA_TEMATICO_CENSO=1 NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. /home/user/.cache/e3-cambio2-apply/venv/bin/python scripts/evaluar_qa.py
```

La salida textual de ambas corridas v2 coincidió exactamente con B3 en global, categorías, QA honesta y censo; FP `0/40`. Los archivos canónicos de comparación B3 están en `docs/e3b3_snapshot_normal_20261028.log` y `docs/e3b3_snapshot_ruido_20261028.log` (JSON asociados del mismo nombre). Las salidas v2 de snapshot se guardaron en caché efímera y no sobrevivieron a la reconstrucción de la candidata; los resultados completos por categoría se transcriben a continuación, sin atribuir los logs canónicos de B3 como logs crudos de la corrida v2.

### Snapshot normal — salida de métricas

```text
GLOBAL SUMMARY (Retrieval) | 875 | R@5 100.00% | R@1 93.14% | MRR 0.9573 | 0 casos fuera del top 5
GLOBAL SUMMARY (Noise/FP) | 40 | FP 0/40 (0.00%)
cruce_idioma        n=8   R@5 100.00% R@1 62.50% MRR 0.7396 fuera_top5=0
 dormido            n=65  R@5 100.00% R@1 100.00% MRR 1.0000 fuera_top5=0
 literal            n=487 R@5 100.00% R@1 99.59% MRR 0.9979 fuera_top5=0
 por_tema           n=65  R@5 100.00% R@1 69.23% MRR 0.8041 fuera_top5=0
 pregunta_natural   n=65  R@5 100.00% R@1 96.92% MRR 0.9846 fuera_top5=0
 sinonimo           n=55  R@5 100.00% R@1 56.36% MRR 0.7221 fuera_top5=0
 typo               n=65  R@5 100.00% R@1 92.31% MRR 0.9564 fuera_top5=0
 variante_gramatical n=65 R@5 100.00% R@1 93.85% MRR 0.9628 fuera_top5=0
QA honesta R@5: 865 casos, 100.00%, 0 fallos fuera del top 5.
QA honesta R@1: 853 casos, 95.31%, MRR 0.9718.
[GATE] OK — métricas dentro de los umbrales de la baseline oficial (código 0).
```

### Snapshot con ruido — salida de métricas

```text
GLOBAL SUMMARY (Retrieval) | 875 | R@5 96.80% | R@1 86.63% | MRR 0.9116 | 28 casos fuera del top 5
GLOBAL SUMMARY (Noise/FP) | 40 | FP 0/40 (0.00%)
cruce_idioma        n=8   R@5 62.50% R@1 50.00% MRR 0.5625 fuera_top5=3
dormido             n=65  R@5 98.46% R@1 95.38% MRR 0.9692 fuera_top5=1
literal             n=487 R@5 99.38% R@1 91.38% MRR 0.9509 fuera_top5=3
por_tema            n=65  R@5 95.38% R@1 67.69% MRR 0.7974 fuera_top5=3
pregunta_natural    n=65  R@5 98.46% R@1 93.85% MRR 0.9590 fuera_top5=1
sinonimo            n=55  R@5 81.82% R@1 50.91% MRR 0.6285 fuera_top5=10
typo                n=65  R@5 93.85% R@1 90.77% MRR 0.9231 fuera_top5=4
variante_gramatical n=65  R@5 95.38% R@1 84.62% MRR 0.8974 fuera_top5=3
QA honesta R@5: 865 casos, 97.34%, 23 fallos fuera del top 5.
QA honesta R@1: 853 casos, 88.63%, MRR 0.9281.
[GATE] FALLADO por baseline histórica (R@5 96.80% < 97.00%, 28 > 24; código 1).
```

El código 1 de ruido es el resultado histórico de B3, no una regresión de Cambio 2: ambas corridas ruido coinciden exactamente con B3, incluidas las métricas por categoría y el FP `0/40`.

### QA honesta por categoría — snapshots

| Categoría | Normal R@5 (n) | Normal R@1 (n) | Ruido R@5 (n) | Ruido R@1 (n) |
|---|---:|---:|---:|---:|
| cruce_idioma | 100.00% (8) | 62.50% (8) | 62.50% (8) | 50.00% (8) |
| dormido | 100.00% (65) | 100.00% (65) | 98.46% (65) | 95.38% (65) |
| literal | 100.00% (487) | 99.59% (487) | 99.38% (487) | 91.38% (487) |
| por_tema | 100.00% (65) | 69.23% (65) | 95.38% (65) | 67.69% (65) |
| pregunta_natural | 100.00% (65) | 96.92% (65) | 98.46% (65) | 93.85% (65) |
| sinonimo | 100.00% (45; 14 apartados) | 87.88% (33; 28 apartados) | 88.89% (45; 14 apartados) | 78.79% (33; 28 apartados) |
| typo | 100.00% (65) | 92.31% (65) | 93.85% (65) | 90.77% (65) |
| variante_gramatical | 100.00% (65) | 93.85% (65) | 95.38% (65) | 84.62% (65) |
| **Global honesta** | **100.00% (865; 0 fallos)** | **95.31% (853; MRR 0.9718)** | **97.34% (865; 23 fallos)** | **88.63% (853; MRR 0.9281)** |

## 2. QA oficiales vivas

### Comandos exactos

Normal:
```bash
set -o pipefail
export PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_PATH=/tmp/viva_e3a.db BIORAG_QA_ORIGEN=/tmp/viva_e3a.db BIORAG_QA_DB_VIVA=/tmp/viva_e3a.db
export BIORAG_QA_TEMP_DB=/tmp/e3c2_viva_normal_work.db BIORAG_QA_METRICS=/tmp/e3c2_viva_normal.json BIORAG_QA_FAILED_CASES=/tmp/e3c2_viva_normal_fallos.jsonl BIORAG_DMN_ESTADO_PATH=/tmp/e3c2_dmn_viva_normal.json
export NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=.
/home/user/.cache/e3-cambio2-apply/venv/bin/python scripts/evaluar_qa.py > /tmp/e3c2_viva_normal.log 2>&1
status=$?
printf 'EXIT_CODE=%s\nLOG=/tmp/e3c2_viva_normal.log\n' "$status"
exit "$status"
```

Con ruido:
```bash
set -o pipefail
export PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_PATH=/tmp/viva_e3a.db BIORAG_QA_ORIGEN=/tmp/viva_e3a.db BIORAG_QA_DB_VIVA=/tmp/viva_e3a.db
export BIORAG_QA_TEMP_DB=/tmp/e3c2_viva_ruido_work.db BIORAG_QA_METRICS=/tmp/e3c2_viva_ruido.json BIORAG_QA_FAILED_CASES=/tmp/e3c2_viva_ruido_fallos.jsonl BIORAG_DMN_ESTADO_PATH=/tmp/e3c2_dmn_viva_ruido.json
export BIORAG_QA_RUIDO=zzqx BIORAG_QA_TEMATICO_CENSO=1
export NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=.
/home/user/.cache/e3-cambio2-apply/venv/bin/python scripts/evaluar_qa.py > /tmp/e3c2_viva_ruido.log 2>&1
status=$?
printf 'EXIT_CODE=%s\nLOG=/tmp/e3c2_viva_ruido.log\n' "$status"
exit "$status"
```

Salidas de consola completas y JSON medidos: [`e3c2_viva_normal_20261029.log`](e3c2_viva_normal_20261029.log), [`e3c2_viva_normal_20261029.json`](e3c2_viva_normal_20261029.json), [`e3c2_viva_ruido_20261029.log`](e3c2_viva_ruido_20261029.log), [`e3c2_viva_ruido_20261029.json`](e3c2_viva_ruido_20261029.json).

### Viva normal

```text
GLOBAL SUMMARY (Retrieval) | 875 | R@5 99.20% | R@1 91.09% | MRR 0.9432
GLOBAL SUMMARY (Noise/FP) | 40 | FP 0/40 (0.00%)
7 casos fuera del top 5 en el conteo global (igual que B3).
QA honesta R@5: 861 casos, 99.88%, 1 fallo [0848].
QA honesta R@1: 850 casos, 93.53%, MRR 0.9622.
[GATE] OK — métricas dentro de los umbrales de la baseline oficial (código 0).
```

| Categoría | n | R@5 | R@1 | MRR | Casos fuera top 5 |
|---|---:|---:|---:|---:|---:|
| cruce_idioma | 8 | 100.00% | 62.50% | 0.7708 | 0 |
| dormido | 65 | 100.00% | 100.00% | 1.0000 | 0 |
| literal | 487 | 100.00% | 99.38% | 0.9969 | 0 |
| por_tema | 65 | 98.46% | 63.08% | 0.7687 | 1 |
| pregunta_natural | 65 | 100.00% | 95.38% | 0.9744 | 0 |
| sinonimo | 55 | 89.09% | 52.73% | 0.6506 | 6 |
| typo | 65 | 100.00% | 87.69% | 0.9308 | 0 |
| variante_gramatical | 65 | 100.00% | 83.08% | 0.9090 | 0 |

### Viva con ruido

```text
GLOBAL SUMMARY (Retrieval) | 875 | R@5 95.31% | R@1 85.71% | MRR 0.8990 | 41 casos fuera del top 5
GLOBAL SUMMARY (Noise/FP) | 40 | FP 0/40 (0.00%)
QA honesta R@5: 861 casos, 96.63%, 29 fallos fuera del top 5.
QA honesta R@1: 850 casos, 88.12%, MRR 0.9215.
[GATE] FALLADO por baseline histórica (R@5 95.31% < 97.00%; código 1).
```

| Categoría | n | R@5 | R@1 | MRR | Casos fuera top 5 |
|---|---:|---:|---:|---:|---:|
| cruce_idioma | 8 | 62.50% | 62.50% | 0.6250 | 3 |
| dormido | 65 | 98.46% | 98.46% | 0.9846 | 1 |
| literal | 487 | 98.56% | 91.38% | 0.9463 | 7 |
| por_tema | 65 | 92.31% | 56.92% | 0.7190 | 5 |
| pregunta_natural | 65 | 100.00% | 96.92% | 0.9846 | 0 |
| sinonimo | 55 | 67.27% | 45.45% | 0.5370 | 18 |
| typo | 65 | 96.92% | 90.77% | 0.9333 | 2 |
| variante_gramatical | 65 | 92.31% | 80.00% | 0.8590 | 5 |

La QA viva con ruido también coincide con B3 en métricas globales, categorías, QA honesta, censo temático y FP `0/40`. El código de salida 1 corresponde al gate histórico, también presente en B3.

## 3. Comparación con B3

Se contrastaron R@5, R@1, MRR, categorías, QA honesta, FP y censo temático. La salida íntegra del comparador está en [`e3c2_comprobar_igualdad_qa_b3_20261029.log`](e3c2_comprobar_igualdad_qa_b3_20261029.log): el comparador oficial B2/B3 imprime `IGUAL` en los cuatro escenarios; además, las corridas viva v2 se compararon directamente con `comprobar_escenario` del mismo módulo y ambas dan `IGUAL`.

```text
snapshot_normal IGUAL
viva_normal IGUAL
snapshot_ruido IGUAL
viva_ruido IGUAL
Pendientes: []
Igualdad de las cuatro: True

Comparación directa E3 Cambio 2 v2 vs B3 (helper del mismo comparador):
viva_normal IGUAL
viva_ruido IGUAL
snapshot_normal IGUAL (corrida v2 anterior; comparación de métricas exacta registrada).
snapshot_ruido IGUAL (corrida v2 anterior; comparación de métricas exacta registrada).
```

La igualdad de las dos corridas snapshot v2 (global, categorías, QA honesta, FP y censo) quedó registrada en la ejecución oficial anterior. Sus logs crudos v2 no persistieron cuando se reconstruyó la caché; por eso arriba se transcriben los valores completos cotejados contra los JSON y logs B3, sin presentar los logs canónicos como stdout de la corrida v2 ni reemplazar métricas. Una primera invocación del comparador desde la ruta aislada de caché señaló diferencia de origen porque ancló rutas relativas a esa raíz distinta; el comparador se ejecutó desde la raíz real del repositorio, donde normaliza las rutas B2/B3 correctamente, y dio `Igualdad de las cuatro: True`. No fue una diferencia de R@5/R@1/MRR/FP.

## 4. Suite completa

Comando ejecutado sin `-k`, sin `BIORAG_NEURONA=0` y sin caché de pytest:

```bash
PYTHONHASHSEED=0 python -m pytest -q -p no:cacheprovider tests
```

Se activaron `PATH=/home/user/.cache/e3-cambio2-apply/venv/bin:$PATH`, `PYTHONPATH=.` y `NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data"` para resolver el entorno del proyecto. Salida textual completa: [`e3c2_pytest_20261029.log`](e3c2_pytest_20261029.log).

```text
........................................................................ [  9%]
........................................................................ [ 19%]
........................................................................ [ 28%]
........................................................................ [ 38%]
........................................................................ [ 47%]
........................................................................ [ 57%]
........................................................................ [ 66%]
........................................................................ [ 76%]
........................................................................ [ 85%]
........................................................................ [ 95%]
.....................................                                    [100%]
757 passed in 147.64s (0:02:27)
```

## 5. Multilingüe y guardados MCP (mediciones previas de la misma candidata v2)

- Directa, 132 IDs: 0 rangos peores, 10 mejores, 0 FP nuevos; entre 120 positivos, R@5 `93/120 (77.50%) → 103/120 (85.83%)`, R@1 `91/120 (75.83%) → 101/120 (84.17%)`, MRR `0.7667 → 0.8500`; FP `2/12 → 2/12`.
- MCP brazo A, 132 IDs: 0 rangos peores, 7 mejores, 0 FP nuevos. zh R@5/R@1 pasó de 7 a 12; ja de 6 a 8; ko, ru, en y es no bajaron.
- Guardados MCP: `69/80` en B3 y v2; cero IDs guardados previamente perdidos. Conteos v2: zh 18, ja 15, ko 16, ru 20.

## 6. Diff final exacto y hashes

El diff de publicación completo contra `47f7f60` (patch v2 aprobado más el docstring actualizado) está en [`e3_cambio2_aplicado_20261029.patch`](e3_cambio2_aplicado_20261029.patch). El manifiesto de hashes de los archivos del motor y de los resultados es [`e3_cambio2_sha256_20261029.txt`](e3_cambio2_sha256_20261029.txt). Se verificó `git apply --check` contra un archivo limpio de `47f7f60` y se comprobó que los nueve archivos resultantes son byte a byte iguales a la candidata aplicada.

```text
SHA-256 patch v2 aprobado: 82fa44297624cc65b5d46f7c461340a49eabe40adb345f9ddc3d5246150e0bb9
SHA-256 diff final (v2 + docstring): abcc91be892e3ea7eaf9a5148d59a79c75ad9f6135da27e4491a94c442c9a817
SHA-256 DB viva usada: a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a
```

La base y el SQL permanecen fuera del repositorio. Cambio 2 no incorpora fusión de sustantivos entre notas. PR #12 debe permanecer en draft; no hacer merge.
