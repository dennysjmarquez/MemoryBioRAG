# E3 — evolución histórica de paráfrasis y atribución de candidatos

**3 nov 2026 · revisión de historial y pruebas sintéticas.** Solo se revisaron fuentes versionadas y se ejecutaron sondas sobre bases sintéticas/copias temporales. No se cambió `core/`, no se abrió ninguna base original, no se borraron ni fusionaron paráfrasis/asociaciones y no se propone un cambio del motor. E3 sigue abierto; E4 no se inicia.

## Conclusión breve

La búsqueda explícita por paráfrasis no ha tenido una sola arquitectura durante todo el historial. En `0bf6e2be` el MCP ejecutaba por separado la query original y cada variante, penalizaba cada resultado no original por `0.95` y reunía candidatos por concepto usando el mejor score. Desde `e5a40e0` se centralizó la lista de variantes en `buscar_por_frase` y se formó un único `MATCH` FTS5 con alternativas OR: dejó de existir la penalización y el merge externo por llamada, y las variantes pasaron a compartir la puntuación de una búsqueda combinada. Después evolucionaron la expansión semántica, los filtros, la generación automática, la convergencia multicampo y la normalización Unicode. Por tanto, una traza actual no describe por sí sola la ruta de 0bf.

La corrección de auditoría se atendió con observación runtime más fina: ahora se registran las filas que devuelve cada sentencia `MATCH` realmente ejecutada y se hacen sondas SELECT auxiliares, en la misma copia, para cada rama query/paráfrasis/campo de una sentencia OR. En el positivo sintético distante, la sentencia combinada devolvió el objetivo; la rama query no lo encontró y la rama de paráfrasis sí. La etiqueta interna final continuó diciendo `literal` y MCP no devolvió ese candidato. Esto demuestra que, en esa fixture, la etiqueta de origen no basta para atribuir la rama; no demuestra un fallo general ni un resultado real mal etiquetado.

## Evolución en el historial

| Fecha / commit | Cambio observado en el código | Alcance y lectura limitada |
|---|---|---|
| Padre `fc09eac` → `0bf6e2b` (28 jun) | El padre no tenía el argumento MCP `parafrasis`. `0bf6e2b` lo agrega a `recordar` y `buscar`: string de variantes separadas por coma. Primero llama la búsqueda original; con variantes vuelve a llamar para `[query] + variantes` (por eso repite la original), multiplica scores de variantes por `0.95`, fusiona por concepto si el score es mejor, ordena y recorta a `limite`. | Era un bucle de llamadas independientes y un merge externo; no era una consulta FTS combinada. La documentación de agente pedía generar 3–5 variantes. En el código de este commit no hay gate de score para ejecutar paráfrasis. `CHANGELOG.md` dice que `PARAFRASIS_THRESHOLD` fue eliminado, pero `docs/PARAFRASIS.md` aún muestra una fila con ese umbral: contradicción documental dentro del propio commit. El `0.95` sí está en la ruta MCP. |
| `e5a40e0` (4 jul) | Añade `parafrasis_list` a `buscar_por_frase`; construye una expresión FTS5 `OR` con la frase y las variantes. En MCP reemplaza el ciclo separado y el merge con una sola llamada a `buscar_por_frase`. El comentario dice explícitamente “UNA sola query FTS5 OR (en vez de N queries)”. | Cambio semántico además de reducción de llamadas: desaparecen del flujo el cálculo separado por variante y el factor `0.95`; las variantes comparten una evaluación FTS5. El título del commit es amplio; el comentario y diff evidencian la intención de agrupar/evitar N consultas, pero no prueban por sí solos que cada efecto en ranking fuera deseado o validado. En el mismo commit, un bloque de `test_memory.py` “prueba” el factor calculando una expresión ternaria local sobre palabras artificiales: no ejecuta `recordar`, `buscar_por_frase` ni el merge; no valida que el motor aplique el factor. |
| `77e68be` / `a3389ce` (8 jul) | En la búsqueda se documenta que la agente pasa sinónimos directamente; deja de expandir cada paráfrasis vía tabla `semantica`. En normal se forman alternativas fraseadas OR; en `modo_estricto` cada variante puede convertirse en un grupo AND unido por OR. | “Variante proporcionada” y “expansión de la tabla semántica” pasan a ser rutas distintas. No todas las variantes comparten necesariamente la misma forma de FTS entre modo normal y estricto. |
| `4d7f4be` (12 jul) | Añade limpieza de stopwords/longitud de la lista antes de parte de la búsqueda. | Las variantes pueden llegar a otras fases como una lista filtrada; los argumentos del MCP no equivalen necesariamente, carácter por carácter, a todas las expresiones internas. |
| `06e9d91` (22 jul) | Si el agente no entregaba variantes, agrega una autoexpansión desde asociaciones PMI (hasta diez términos) y dimensiones. | Aparece una ruta implícita distinta de la paráfrasis explícita. |
| `20bbf36` (23 oct) | Apaga por defecto la auto-paráfrasis/auto-dimensiones tras mediciones de recall; deja un opt-in por entorno y orden determinista cuando se habilita. | En el código actual la auto-paráfrasis requiere `BIORAG_MCP_AUTO_PARAFRASIS=1`; por defecto no se inventan variantes si el agente no las pasa. Las explícitas se siguen dividiendo y transmitiendo. La prueba `tests/test_mcp_auto_expansion.py` verifica ambos comportamientos. |
| `0f11350` (3 oct) | La convergencia multicampo incorpora la query y las paráfrasis filtradas como conjuntos alternativos; toma la mejor cobertura por campo para no diluirla por unión. | Es otra forma de influencia de paráfrasis sobre ranking posterior, separada de qué filas devuelve FTS. `tests/test_evidence_convergence.py::test_parafrasis_se_evalua_como_alternativa_sin_diluir_consulta` comprueba esa regla de scoring. |
| `c695310` (29 oct) | Aplica identidad Unicode NFC a query y variantes antes de la búsqueda; persisten sanitización y separación por comas. | Cambia la normalización de la entrada, no el hecho de que no haya procedencia por variante en el resultado FTS. `tests/test_identidad_unicode_cambio1.py` comprueba límites y propagación normalizada. |
| `90225d1`, `03774b2` (refactors) | Extraen la capa MCP a `core/mcp_server/search.py` y la búsqueda del store a `core/memory/search.py`. | Son los módulos actuales; el refactor de ubicación no debe leerse como creación de una nueva política de paráfrasis. Revisé el comportamiento por historia de símbolos y diffs, no solo por los nombres actuales. |

### Camino actual, por separado de los caminos históricos

En `core/mcp_server/search.py`, el MCP separa la string recibida en variantes (o deja la lista vacía por defecto) y llama una vez al método actual. En `core/memory/search.py`, las variantes se filtran en una etapa, se construye un `fts_match` combinado (frase y variantes OR; con `sustantivos_clave` puede agregarse otra rama OR), y hay fallbacks y scoring posteriores. El método también usa las variantes en convergencia multicampo. En consecuencia:

- La sentencia FTS combinada puede incluir varias fuentes semánticas en un mismo resultado SQL. Capturar el SQL y luego el pool final no identifica qué rama produjo una fila.
- El origen lateral `last_origen_scores` no es una identidad de variante. El caso observado donde el objetivo vino de la alternativa de paráfrasis terminó con origen `literal`, score 0.0.
- La respuesta MCP final se decide después del pool y del ranking/filtros. Un candidato en filas FTS o en el pool no implica que haya sido retornado.
- Los 0.95 puntos del camino histórico no deben interpretarse como una propiedad del motor actual.

## Pruebas y resultados emparejados

### Instrumentación de sentencia → filas → rama

`qa_stdio_server_trace_paraphrase.py` envuelve temporalmente el cursor de las llamadas actuales a `buscar_por_frase`; no parchea archivos de `core/`. Para cada `MATCH` captura SQL, expresión, filas/conceptos efectivamente obtenidos por la llamada original. En consultas OR, hace sondas SELECT separadas, solo de lectura, con el mismo SQL y filtros y una rama de la expresión MATCH a la vez. Así distingue consulta base, variantes y boost de `sustantivos_clave` en estas fixtures. Las sondas son instrumentación contrafactual de rama: se etiquetan por separado, no se hacen pasar por filas de una llamada histórica ni por una escritura del motor.

Runner reproducible: `scripts/diagnosticar_traza_interna_parafrasis_e3.py`. Corrida nueva: `.private_evidence/e3_paraphrase_internal_trace_20261103_run07/` (índice privado; no subir). Tres pares sintéticos, brazo baseline e instrumentado: **24 herramientas MCP**, **12 búsquedas**, 0 flags MCP de error; respuesta, traza pública y scores emparejados coincidieron en 3/3 pares; snapshots del grafo iguales.

`run04`, `run05` y `run06` se conservaron sin sobrescritura como iteraciones previas del arnés. En el caso distante sintético, el primer MATCH (query base) no devolvió el objetivo. Un MATCH posterior, que agrupaba query, paráfrasis y boost de etiquetas, sí devolvió la fila objetivo. Las sondas separadas de ese mismo MATCH identificaron la rama query sin fila y la rama paráfrasis con la fila; el objetivo no apareció en la respuesta MCP. El pool final anotó origen `literal`, score 0.0. En los dos pares restantes el objetivo ya aparecía en controles sin paráfrasis (origen `simbolico`), de modo que no son positivos diferenciales. Las ramas de fallback que no coinciden exactamente con una variante declarada se etiquetan como `auxiliary_fts_branch_n`, no se atribuyen a la paráfrasis. Se reportan asociaciones causales solo dentro de la sentencia/snapshot sintéticos observados.

La instrumentación es una ampliación de la evidencia anterior, no una reescritura retroactiva: la corrida `run02` conserva sus hashes y resultados; `run04`–`run07` están en directorios privados nuevos. Capturar cada fila de sentencia y separar ramas fue el punto que faltaba en la observación de `e38b752`.

### Comparación sintética de política de agregación

`scripts/diagnosticar_agregacion_historica_parafrasis_e3.py` emula el bucle MCP de 0bf —llamada inicial, llamada repetida para query, llamada para variante, factor 0.95 y merge por concepto— sobre el **search core actual** y compara con una sola llamada actual con `parafrasis_list`. Resultado far_query: el emulador por llamadas separadas incluyó el objetivo con score 0.06707; la llamada combinada actual no lo incluyó en ese core. En los pares cercano y cobertura mixta ambas políticas internas incluyeron el objetivo, pero con scores distintos. Salida íntegra privada: `.private_evidence/e3_paraphrase_historical_policy_20261103_run01/`.

**Límite explícito:** esta es una prueba de la política externa de llamadas/agregación, no la ejecución del binario/core de 0bf ni una comparación histórica end-to-end. El ranker y los datos del emulador son actuales. El diff histórico sirve para confirmar el flujo antiguo; esta prueba sintética muestra que la arquitectura importa y da una señal para diseñar una reproducción histórica real, no permite concluir que el antiguo motor habría generado exactamente los mismos scores/resultados.

### Pruebas de repositorio relevantes y brechas

- `tests/test_mcp_auto_expansion.py`: por defecto no genera variantes; explícitas se pasan; reactivación opt-in es determinista.
- `tests/test_evidence_convergence.py`: trata variantes como alternativas en convergencia y comprueba que no diluyen el score.
- `tests/test_identidad_unicode_cambio1.py`: valida límites/normalización Unicode y propagación del argumento.
- `tests/test_concept_hub_generalizacion.py`: evalúa expansión del Concept Hub y recuperación semántica sin parámetro `parafrasis`; evidencia una ruta de expansión distinta.
- `test_memory.py` conserva una aserción local sobre el número 0.95, pero es una simulación del ternario y no prueba el pipeline. En cambio, el pipeline cambió en `e5a40e0` y retiró la penalización externa. No usar esa aserción como prueba del comportamiento actual.
- La instrumentación actual añadió una comprobación de equivalencia baseline/instrumentada y atribución de candidatos por sentencia/rama en copias, pero no existe prueba unitaria que cubra todos los fallbacks, filters, modos estrictos, variantes múltiples, vecinos/context window o candidatos cuyo score provenga de ranking posterior.

La batería completa de 824 tests y 2 subtests había pasado antes de esta nueva instrumentación (commit `e38b752`). En esta entrega, `py_compile` y `git diff --check` pasaron; el runner final `run07` confirmó 3/3 equivalentes, 0 errores MCP y sin cambios de grafo; el emulador de política histórica completó sus tres fixtures sintéticas. Además se ejecutaron 48 pruebas seleccionadas de convergencia, autoexpansión e identidad Unicode: **48 passed** (DB de prueba bajo `/tmp`, fixtures QA propias y copias temporales). No se redirigió ni abrió ninguna base original.

## Qué queda pendiente

1. Revisar/medir con fixture sintético la misma consulta bajo rutas históricas completas (incluido el search core y esquema de cada revisión) si se necesita afirmar resultados históricos de extremo a extremo; el emulador actual no sustituye esa ejecución.
2. Ampliar ramas instrumentadas a múltiples variantes, modo estricto, filtros temporales/categoría, fallback Unicode y casos con contexto, verificando equivalencia baseline en cada uno.
3. Distinguir candidate inclusion SQL, causa del score, selección final/top-k, y emisión MCP. No convertir `literal`, `parafrasis` ni cualquier otro origen lateral en causalidad si la traza de rama no lo respalda.
4. Conservar todas las variantes y asociaciones en cada artefacto; no adjudicar verdad, eliminar pistas, escoger política de retención/fusión ni modificar el motor sin autorización.

E3 continúa abierto. No se inicia E4 ni se aplica un parche del motor.
