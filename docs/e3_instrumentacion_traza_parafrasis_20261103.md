# E3: instrumentación pasiva de la ruta de paráfrasis MCP

**Fecha:** 2026-11-03. Seguimiento en tres pares sintéticos con MCP stdio real. El objetivo era separar la expresión FTS ejecutada, los candidatos internos/orígenes y la respuesta final. No se modificó código fuente de `core/`, no se descartó ningún candidato/pista y no se abrió una base original.

## Método de instrumentación

`scripts/qa_stdio_server_trace_paraphrase.py` se usa como launcher QA aislado. En el proceso hijo, envuelve en tiempo de ejecución `SQLiteMemoryBioRAG.buscar_por_frase`, registra un snapshot pasivo de sus parámetros y captura `MATCH` FTS mediante `sqlite3.Connection.set_trace_callback`; luego llama el método original con los mismos argumentos y devuelve la misma lista de resultados y el mismo total, sin mutarlos. La telemetría privada conserva hashes de las entradas, expresiones FTS, candidatos y etiqueta de origen; los resultados finales MCP se registran aparte. La instrumentación no modifica ni parchea el motor en disco.

Cada uno de tres pares se ejecutó en copias idénticas: launcher normal y launcher instrumentado, con las mismas variables de entorno, DMN apagada para no añadir una variable de grafo, apertura MCP por `sustantivos` y una llamada `recordar`. Las seis solicitudes de búsqueda se compararon en ambos modos; las respuestas y trazas públicas coincidieron entre baseline e instrumentación en **3/3 pares**. No cambió el grafo durante apertura o búsqueda en estas copias sin aristas.

## Resultados agregados

| Medida | Resultado |
|---|---:|
| Pares de consulta (paráfrasis / control sin ella) | 3 |
| Llamadas MCP totales (apertura + búsqueda, ambos launchers) | 24 |
| Flags MCP `isError` | 0 |
| Baseline e instrumentación con igual salida MCP/traza | 3/3 pares |
| Pares en que solo el brazo con paráfrasis devolvió el objetivo | 0 |
| Pares con objetivo en ambos brazos / ninguno | 2 / 1 |

### Separación por etapa observada

- **Par de consulta distante:** el control FTS5 directo no encontró el objetivo por el query, mientras que el término de paráfrasis sí. La expresión `MATCH` combinada, capturada durante `buscar_por_frase`, incorporó el objetivo al pool interno con origen registrado como `literal` y score de origen `0.0`; MCP finalmente no lo devolvió. En el control sin paráfrasis no entró ese candidato. Esto demuestra que, en este fixture, una coincidencia proveniente de la alternativa de paráfrasis puede entrar al pool combinado con etiqueta interna `literal`. Como el resultado fue suprimido antes de la respuesta MCP, **no demuestra que un resultado entregado al usuario haya sido atribuido incorrectamente** ni identifica por sí solo qué puerta final lo excluyó.
- **Otros dos pares:** cuando MCP devolvió el objetivo, el origen interno capturado fue `simbolico` (scores de origen `0.8333` y `0.6667` respectivamente), tanto con paráfrasis como sin ella. Los controles emparejados también devolvieron el objetivo sin paráfrasis; por ello no son positivos específicos de esa vía. La traza MCP pública `capa_parafrasis` fue `0.0` en ambos resultados.
- En consecuencia, ahora se separan tres hechos antes mezclados: FTS directo del término, pertenencia al pool de búsqueda con la etiqueta interna registrada, y presencia en el JSON final MCP. Esta fixture no produce un resultado devuelto solo por paráfrasis.

La lectura estática de `core/memory/search.py` es compatible con la observación: el primer fallback ejecuta el `fts_match` combinado y etiqueta sus hits como `literal`; una asignación posterior `parafrasis` está en otra rama. La instrumentación aporta un ejemplo sintético de candidato de la alternativa etiquetado como `literal`, pero no generaliza a otras consultas ni acredita un defecto operacional real. **No se hace cambio al motor ni se propone uno.**

## Evidencia y reproducción

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python scripts/diagnosticar_traza_interna_parafrasis_e3.py \
  --evidence-dir .private_evidence/e3_paraphrase_internal_trace_20261103_run02
```

Los archivos completos —incluidos textos sintéticos, expresiones `MATCH`, candidatos y snapshots— quedan solo en `.private_evidence/e3_paraphrase_internal_trace_20261103_run02/`. SHA-256: `stdio_cases_full.json` = `fd7a9238d5c141ee00a23563f4d00ae4a412ebb37083a6021cdc3f505363757f`; `synthetic_manifest.json` = `e642cada4b5752304cdb9318646c3baad3b246c8654362ecabc5681c961f06f4`. No se suben a Git ni se incluyen los términos de consulta en este agregado público.

Los snapshots abarcan las nueve tablas de grafo completas del harness y la proyección `largo_plazo(concepto, asociaciones)`; **no son copia completa de SQLite**. `py_compile` de ambos scripts y la corrida terminaron correctamente; la suite completa reportó 824 pruebas y 2 subtests pasados.

## Límites y siguiente paso E3

La equivalencia baseline/instrumentación está comprobada solo para estos seis brazos y no demuestra ausencia de efectos del wrapper fuera de ellos. La etiqueta `literal` es la clasificación actual del código, no una verdad independiente; la prueba identifica una diferencia entre canal de entrada y etiqueta interna en una copia, pero no valida la semántica de la clasificación en corpus general. No se acepta fallo general ni se concluye que la traza pública deba cambiarse. E3 sigue abierto; no se cambia el motor y cualquier cambio futuro requiere diff, evidencia adicional y autorización explícita.

## Actualización tras la corrección de atribución de la auditora (run04)

La instrumentación de `run02` descrita arriba capturaba sentencias `MATCH` ejecutadas y pool final, pero no las filas de cada sentencia. No bastaba para afirmar qué consulta concreta incorporó un candidato. Sin sobrescribir `run02`, `scripts/qa_stdio_server_trace_paraphrase.py` se amplió con un proxy runtime del cursor: conserva la consulta original y observa las filas/conceptos que el motor ya lee; luego ejecuta sondas `SELECT` auxiliares, de solo lectura y sobre la misma copia, para aislar cada rama query/paráfrasis/boost del `MATCH` OR. El SQL de la llamada original y los resultados de esas sondas quedan diferenciados en la telemetría privada.

La corrida nueva `run04` se guardó en `.private_evidence/e3_paraphrase_internal_trace_20261103_run04/`. En el caso distante, el primer MATCH del query base devolvió cero filas; un MATCH posterior combinado devolvió el objetivo. Las sondas de esa expresión combinada mostraron que la rama de query no lo encontró y la rama de paráfrasis sí. La rama de `sustantivos_clave` también queda medida por separado. El objetivo apareció en el pool con origen `literal`, score 0.0, pero no en la respuesta MCP. Los otros dos pares siguen sin positivo diferencial. Baseline e instrumentación coincidieron en salida/traza en 3/3 pares, con 0 flags MCP y sin deltas de grafo.

Esta atribución más fina responde al hueco de observación, pero no es un cambio de motor ni un test completo de todas las combinaciones FTS: las sondas son contrafactuales (una rama cada vez), dentro de una sola fixture y un único SQL/filtro original. No se extrapola el resultado ni se descartan paráfrasis o asociaciones. El análisis histórico por commits y la emulación limitada de la política antigua están en `docs/e3_historical_paraphrase_evolution_20261103.md`; E3 permanece abierto, E4 en espera.

**Corrida de cierre del arnés: `run07`.** Se repitió baseline/instrumentación después de hacer que la clasificación de ramas requiera coincidencia con la forma FTS esperada de query/variantes. Las alternativas de fallback que no casan exactamente se registran como `auxiliary_fts_branch_n`, evitando etiquetarlas falsamente como paráfrasis por su posición dentro de un OR. Persisten los mismos agregados (3/3 equivalentes, 0 errores MCP); el caso distante continúa atribuyendo la fila del MATCH 2 a `paraphrase_1`, no a la query base. Evidencia completa privada en `.private_evidence/e3_paraphrase_internal_trace_20261103_run07/`; `run04`/`run05`/`run06` previas se conservan intactas.
