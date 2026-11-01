# Informe de medición sintética v2 limitada — 2026-10-31

## Dictamen

La revisión previa al inicio verificó el hash del candidato, gold, manifiesto operativo, las dos fixtures, la revisión de grafo y el informe de repetibilidad. Todas las guardas pasaron. Se registró una aprobación explícita separada de Dennys y se ejecutó el `measure_baseline` real mediante el CLI en modo `synthetic_smoke`, usando build A y copias aisladas por brazo. El comando terminó con código **0**; el informe es `valida=true`, `invalidaciones=[]`. No hubo errores MCP/transporte ni mutaciones inesperadas.

Esto es una medición sintética de una consulta y cinco brazos, **no** la línea base real ni QA completa. Las etiquetas `relacionados_utiles` y `ruido_tonto` siguen no adjudicadas: sus valores genéricos en el informe bruto no se interpretan ni presentan como evaluación de esas categorías. W sigue pendiente.

## Aprobación y hashes verificados antes de iniciar

El candidato original continúa sin aprobación (`synthetic_freeze_candidate_v1`, SHA-256 `11fe45a8d83bef09c0f8e7ffbad774910efbb61c3f5c962c1cc647918c0ace18`). La autorización actual se registró en `evidencia/actual_approval.json` como `synthetic_freeze_approval_v1`, `estado=APROBADO`, `aprobado_por=Dennys`, exclusivamente para `N0/N1/G1/G2/R`. SHA-256 de esa aprobación: `339f0e79688afc0e45a77f260562098ee32e2613402d92e2bd4fad11f6b94dce`.

| Elemento | Hash aprobado/verificado |
|---|---|
| Gold v2 | `5d83616a63be7c73bbea8bb90452091316d7e238835013440a6fd939c13d16d8` |
| Manifiesto operativo build A | `eaa6d4235f07e21daa479433cbe0107b5d5f120a9224a1c2debb3d996c0ad451` |
| Fixture elegida A, hash lógico | `cf9aaf50e0b36007c9c00cc4b7335c47c0d1dda1bd598bef561cdcf9c8bace55` |
| Fixture A, archivo SQLite | `72793a764a131d4ed5d0d8db13fa3e2199abe2b55d03aaedb4c6818bcdb9e14f` |
| Fixture B, comparación lógica | `911a275343d51d2264ccb7dbd6ac423709acde1c7a37b087dedeceddc045ba12` |
| Fixture B, archivo SQLite | `8b7afebd73cd852ab47eb8649a463090f4d6fe50c3f99bdf03816f4e8b86671d` |
| Revisión del grafo | `659e969a0d2c8d666e2be9f83ab9f70857fb144d77546d8732d32a568e3248ae` |
| Repetibilidad | `b19f0810a58843dc37d8bca1df2d4a8c235698097a651ca5eaf34aad5a9cd456` |

Ambas bases estaban presentes, tenían `integrity_check=ok`, 3/3 nodos activos y hashes físicos/lógicos coincidentes con los publicados. Se recomputó la comparación de solo lectura y coincidió con `REPEATABLE_PAIR`, dos construcciones independientes e idéntica estructura auditada. Los hashes lógicos completos de las dos DB siguen siendo distintos, tal como queda explicado en el informe de preparación; no se confundió repetibilidad estructural con identidad de todas las tablas.

La aprobación ligada a esos hashes quedó guardada antes de iniciar los brazos. Los datos completos de verificación previa están en `evidencia/preflight_hash_verification.json`; el manifiesto real de aprobación está en `evidencia/actual_approval.json`.

## Ejecución y resultado

- 1 consulta gold; los cinco brazos planeados y ejecutados: `N0`, `N1`, `G1`, `G2`, `R`.
- 5 llamadas `recordar`, una por brazo. Cada brazo usó su propia copia temporal de build A.
- En el canal `resultados`, `synthetic_cobalt` apareció en los cinco brazos. Esta observación se limita al objetivo explícito de smoke; no adjudica la relevancia de otros canales.
- `call_errors=[]`, errores MCP y de transporte: 0 por brazo; `invalidaciones=[]`.
- En cada copia se registraron únicamente cambios de telemetría en `log_busquedas` y `nodo_accesos_historial`. Las cinco auditorías por fila/campo fueron válidas, sin violaciones ni tablas inesperadas. En los cinco brazos, el diff de aristas fue vacío (sin inserciones, eliminaciones ni actualizaciones).
- Los hashes físicos y lógicos de las fixtures base A y B se volvieron a comprobar después de medir y no cambiaron. Los hashes de cada DB de trabajo aislada están en `evidencia/isolated_arm_database_hashes.json`; las DB binarias no se incluyen en Git.

### Salida exacta del comando `medir`

Código de salida: `0`.

```text
{"estado": "medicion descriptiva; sin umbrales aplicados", "conteo": {"consultas_gold": 1, "brazos_planeados": ["N0", "N1", "G1", "G2", "R"], "brazos_con_llamadas": ["G1", "G2", "N0", "N1", "R"], "llamadas_recordar": 5}, "salida": "/tmp/biorag_v2_clean_pair_y77rdhst/synthetic_v2_measurement_report.json"}
```

El `stderr` íntegro está archivado; son cinco trazas `[TRACE] 1.8 Snap: 1 → ['synthetic_cobalt']`, no excepciones.

## Evidencia, límites y errores de comprobación

La carpeta `docs/medicion_sintetica_v2_limitada_2026-10-31/evidencia/` conserva la aprobación, candidato no aprobado original, gold/manifiestos, hashes verificados, salida CLI, informe, `run_manifest`, respuesta/canales por llamada y snapshots `before`/`after`/`diff` por fila/campo. `SHA256SUMS` verifica los artefactos. El informe CLI y el `run_report.json` persistido representan el mismo objeto JSON.

Para transparencia se registraron errores locales de verificación/archivo, no del harness de medición: un `KeyError` por una ruta de campo mal referenciada en el primer preflight (corregido antes de aprobar; no inició MCP ni escribió DB), un `IndentationError` en el primer postcheck (no llegó a consultar DB) y un `RuntimeError` al faltar la variable `BIORAG_QA_TEMP_ROOT` en el primer armado de evidencia (no inició lectura SQLite). El preflight corregido pasó **antes** de crear la aprobación; el postcheck/archivo corregidos confirmaron que las fixtures base siguen intactas y que los hashes de evidencia verifican. No se repitió MCP para corregirlos. Los tres errores y sus resoluciones están registrados separadamente de los cero errores del run.

No se consultó ni modificó el gold original ni bases originales, no se cambió motor ni ranking y no se ejecutó QA completa. El informe bruto conserva los campos de métricas genéricas; al no estar adjudicadas las etiquetas útiles/ruido, no deben usarse para afirmar resultados en esas categorías. W no se incluyó ni ejecutó.
