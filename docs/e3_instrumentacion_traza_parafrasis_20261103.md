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

La corrida nueva `run04` se guardó en `.private_evidence/e3_paraphrase_internal_trace_20261103_run04/`. En el caso distante, la primera sentencia MATCH del query base era `SELECT COUNT(*)`: devolvió una fila escalar con conteo 0 (cero documentos coincidentes, no cero filas SQL); un MATCH posterior combinado devolvió el objetivo. Las sondas de esa expresión combinada mostraron que la rama de query no lo encontró y la rama de paráfrasis sí. La rama de `sustantivos_clave` también queda medida por separado. El objetivo apareció en el pool con origen `literal`, score 0.0, pero no en la respuesta MCP. Los otros dos pares siguen sin positivo diferencial. Baseline e instrumentación coincidieron en salida/traza en 3/3 pares, con 0 flags MCP y sin deltas de grafo.

Esta atribución más fina responde al hueco de observación, pero no es un cambio de motor ni un test completo de todas las combinaciones FTS: las sondas son contrafactuales (una rama cada vez), dentro de una sola fixture y un único SQL/filtro original. No se extrapola el resultado ni se descartan paráfrasis o asociaciones. El análisis histórico por commits y la emulación limitada de la política antigua están en `docs/e3_historical_paraphrase_evolution_20261103.md`; E3 permanece abierto, E4 en espera.

**Corrida de cierre del arnés: `run07`.** Se repitió baseline/instrumentación después de hacer que la clasificación de ramas requiera coincidencia con la forma FTS esperada de query/variantes. Las alternativas de fallback que no casan exactamente se registran como `auxiliary_fts_branch_n`, evitando etiquetarlas falsamente como paráfrasis por su posición dentro de un OR. Persisten los mismos agregados (3/3 equivalentes, 0 errores MCP); el caso distante continúa atribuyendo la fila del MATCH 2 a `paraphrase_1`, no a la query base. Evidencia completa privada en `.private_evidence/e3_paraphrase_internal_trace_20261103_run07/`; `run04`/`run05`/`run06` previas se conservan intactas.

## Seguimiento: punto exacto de exclusión y corrección de COUNT (run de etapas)

La solicitud de auditoría aclaró correctamente que la primera consulta es un `SELECT COUNT(*)`. Se comprobó en la copia sintética nueva: esa sentencia devuelve **una fila SQL** cuyo valor escalar es **0**. Por tanto, “el primer MATCH devolvió cero filas” era incorrecto; la forma precisa es “el conteo del query base fue cero (cero documentos coincidentes)”. La frase anterior se corrigió arriba. En otro `COUNT(*)` auxiliar posterior se observó igualmente una fila con valor 0.

En `.private_evidence/e3_paraphrase_search_stages_20261103_run02/` el rastreo runtime por etapas y la observación de SQL del filtro aclaran dónde se pierde el nodo sintético:

1. El MATCH combinado devolvió la fila objetivo; al sondear sus ramas, query base dio cero candidatos y `paraphrase_1` dio el objetivo. El boost de `sustantivos_clave` no lo devolvió.
2. El candidato siguió presente en el pool `todos`, con origen lateral `literal`. El scoring lo conservó en `resultados_con_hibrido` con score 0.0686.
3. La query de la fixture tenía un solo token de búsqueda. En el filtro final de palabra de una sola palabra (`PALABRA_INICIO_ANCHO`, `core/memory/search.py:2081–2100`), el origen `literal` hizo que el candidato entrara en `literal_results`. La consulta del guardia recibió el concepto como candidato pero devolvió cero filas válidas; la lista `resultados_con_hibrido` quedó sin él. La traza ve la transición en la línea siguiente a la asignación del filtro (en el checkout medido, línea 2120).
4. `buscar_por_frase` devolvió `resultados=[]` con `total=1` (total del pool anterior al filtro), y ausencia del objetivo en `last_pagina_resultados`. MCP no lo eliminó de una lista no vacía: su rama `if not resultados` (`core/mcp_server/search.py`) generó la respuesta de contingencia con `total=0` y `resultados=[]`.

**Conclusión acotada:** en esta copia, el candidato quedó fuera **dentro de `buscar_por_frase`**, en el filtro final de prefijo para consultas de una palabra, no en una etapa posterior de serialización MCP. La secuencia observada es compatible con que el hit de paráfrasis combinado se etiquetó como `literal`, y por eso se sometió al filtro del token original. No se propone alterar ese comportamiento: falta probar otras clases de consulta y confirmar por separado la semántica deseada. Este diagnóstico no generaliza a corpus real ni decide si las etiquetas/orígenes deben cambiar.

El nuevo runner añade trazas por etapa, count escalar y filas del guardia de prefijo solo en el launcher QA runtime. La corrida final `.private_evidence/e3_paraphrase_search_stages_20261103_run03/` afirma automáticamente el recorrido sintético: MATCH por variante → pool → puntuación → filtro de prefijo vacío → retorno interno vacío → contingencia MCP. Baseline/instrumentado siguió equivalente en 3/3 pares, hubo 0 errores MCP y ningún delta de grafo. `run02` previo permanece intacto. Evidencia completa permanece privada; no se tocaron `core/`, motor ni bases originales.
