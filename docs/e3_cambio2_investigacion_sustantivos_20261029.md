# E3 Cambio 2 — guardar sustantivos exactos, comparar también sin marcas

**Estado: SOLO INVESTIGACIÓN. No se modifica el motor ni se migran datos.** El archivo `docs/e3_cambio2_propuesta_no_aplicar_20261029.patch` es un esquema de diff documental, deliberadamente no ejecutable. Cualquier implementación requiere revisión y OK explícito de Dennys, diff de código definitivo, pruebas y QA.

## 1. Hallazgo principal

El normalizador actual de `sustantivos_clave` hace más que quitar tildes latinas: `core/memory/constants.py:286-311` normaliza identidad, pasa cada término por `_quitar_acentos` y deduplica **después** de plegarlo. `core/stemmer_es.py:43-46` define ese plegado como NFKD seguido de eliminar todos los caracteres con clase combinatoria distinta de cero. Así se pierden distinciones escritas con marcas y pueden colisionar términos antes de almacenarse o contarse.

Ejemplo reproducible con Python `unicodedata`:

| Entrada | Forma guardada hoy por el normalizador | Consecuencia |
|---|---|---|
| `ガラス` (ga-ra-su) | `カラス` | Se pierde dakuten de `ガ` |
| `カラス` (ka-ra-su) | `カラス` | Colisiona con `ガラス` |
| `ガラス,カラス` | `カラス` | Dos claves pasan a ser una antes de contar/deduplicar |
| `café` | `cafe` | Se conserva la equivalencia histórica buscada |
| `क़िला` | `किला` | Se pierde nukta y puede colisionar con la forma sin nukta |

La normalización de identidad aprobada en Cambio 1 hace NFC y plegado acotado de ancho; **no elimina estas marcas**. La pérdida ocurre en el paso posterior de `normalizar_sustantivos_clave`.

## 2. Mapa de dónde se eliminan marcas y quién usa esas formas

### Sustantivos clave — afecta directamente almacenamiento, conteo y búsqueda

- **Almacenamiento/deduplicación:** `core/memory/constants.py:286-311`, expuesto como `normalizar_sustantivos_clave` por `core/memory_store.py`. Tras identidad, lowercase y división por comas, aplica `_quitar_acentos`; protege explícitamente `ñ`, pero no otras marcas. La deduplicación y, luego, las comprobaciones del mínimo/máximo se hacen sobre el resultado plegado.
- **Validación:** `core/mcp_server/_shared.py:93-99` comprueba longitudes/categorías sin plegar por sí misma, pero recibe los términos ya normalizados. Las rutas de MCP `recordar`/`buscar`, `aprender`/`guardar` y `agregar_sustantivos` llaman el normalizador antes de validar/entregar.
- **Persistencia:** `core/mcp_server/write.py` entrega ese resultado a `percibir_corto_plazo`; `core/memory/ingest.py:41-52,82-95` documenta y conserva la premisa de que el valor ya viene normalizado. La consolidación copia/fusiona el campo (`core/memory/consolidation.py:248-290,321-326`). Por eso se deben probar ambos almacenes, corto y largo plazo.
- **Comparación en búsqueda:** `core/memory/search.py:392-401` vuelve a aplicar `_quitar_acentos` a los sustantivos clave de la consulta y genera un `MATCH` sobre la columna FTS dedicada, con peso BM25 de 4.0. `core/mcp_server/search.py:207-253,484-498` normaliza y valida el argumento antes de pasarlo. Cambiar solo la escritura no basta: los recuerdos viejos ya contienen la forma plegada.
- **Indexación/filtros posteriores:** FTS5 trigram indexa el texto guardado de `largo_plazo.sustantivos_clave` (esquema y triggers en `core/memory/schema.py:1000-1059`). La búsqueda también usa ese campo en QCR/prefijo y metadatos (`core/memory/search.py:1526-1542,1919-1929,2073-2097`). Cualquier alias debe integrarse de modo que esos filtros no eliminen candidatos recuperados por la vía aproximada.
- **Otros consumidores:** el autoexamen deriva sustantivos con el normalizador (`core/memory/neurona_examen.py:187-197`); `core/memory/neurona.py:633` los pasa como señal de búsqueda. Deben probarse por compatibilidad, sin ensanchar inadvertidamente el alcance a otras neuronas o dimensiones.
- **Ruta de actualización distinta:** `biorag_actualizar`, `core/mcp_server/write.py:1010-1087`, escribe sustantivos en largo plazo mediante el mismo normalizador, pero no comparte el recorrido de validación completo de `aprender` ni `agregar_sustantivos`. Auditoría de Cambio 1 ya la señaló como pendiente porque tampoco pliega ancho de manera consistente. Mantenerla como tarea separada, con pruebas propias; esta investigación no la corrige.

### Otros usos de quitar marcas — fuera del cambio propuesto

| Ubicación | Uso visible | Tratamiento propuesto |
|---|---|---|
| `core/stemmer_es.py:43-46,166-185,250-286` | Stemming ES/EN y puente entre formas (`stem`, fallback). | No tocar: es normalización interna del stemmer, no persistencia de SK. Probar no regresión. |
| `core/memory/search.py:150-161` | Comparación de stopwords en la consulta. | No tocar en esta propuesta. |
| `core/memory/scoring.py:412-422` | Tokens sin marcas para Jaccard de reordenamiento. | No tocar; no usar esta salida para persistir ni contar SK. |
| `core/fallback_simbolico.py:25-46` y consumidores | Coincidencia simbólica, stopwords y traducción/lemmas. | No tocar; es una capa aproximada separada y puede introducir sus propias colisiones. |
| `core/neurona_asociativa.py:95-96`, `core/memory/escala.py:45-46` | Normalización de rasgos/texto para funciones neuronales o de escala. | No tocar en Cambio 2. |
| `core/srl_extractor.py:32-34` | Forma normalizada de palabras para extraer roles. | No tocar en Cambio 2. |
| `core/lexical_learning.py:36-50` | Índice de episodios léxicos mediante expresión normalizada. | No tocar ni migrar; evaluar por separado si el alcance futuro lo requiere. |

**Distinción importante:** estos consumidores hacen equivalencia aproximada local para sus fines; no demuestran que sea seguro destruir la identidad original de una etiqueta. Cambio 2 se limita a la representación/consulta de `sustantivos_clave` y no cambia el texto del recuerdo, sus sinónimos, nombre, stemming, SRL, aprendizaje léxico ni neuronas.

## 3. Propuesta: preservar lo escrito, mantener idéntica la comparación de ranking

**Condición de diseño:** la distinción exacta/aproximada se usa para preservar, contar y deduplicar etiquetas; **no crea dos niveles de relevancia**. En el ranking, la comparación sin marcas debe aportar exactamente lo mismo que aporta hoy. `café`/`cafe` y los datos históricos sin marcas no pueden perder peso, posición o elegibilidad por el cambio. No se da precedencia, bono, desempate ni peso adicional a la etiqueta exacta. Cualquier futuro orden por exactitud sería otro cambio independiente, medido y autorizado por separado.

1. **Al guardar:** después de la identidad Unicode ya aprobada, preservar las marcas del término en NFC y normalizar solo aspectos no semánticos acordados (minúsculas, espacios periféricos, separadores). Deduplicar y contar por cadena exacta marcada, no por forma sin marcas: `ガラス,カラス` son **dos** etiquetas; dos copias idénticas de `ガラス` siguen contando una. Validar el límite de términos sobre ese conjunto preservado.
2. **Índice de ranking compatible:** preservar el campo fuente `sustantivos_clave` en tablas SQLite. En la columna SK que consume el mismo FTS/ranker actual, indexar una **proyección derivada** de cada fila: equivalencia histórica por término, con deduplicación de claves proyectadas. Proyectar la consulta con la misma regla. Así `ガラス` y `カラス` guardados juntos conservan dos etiquetas fuente, pero la columna de ranking contiene una sola clave histórica `カラス`; `café`/`cafe` proyectan una vez a `cafe`. Mantener el mismo índice/columna FTS, pesos BM25 (SK 4.0), fórmula, top-k y demás reglas; no añadir una señal de coincidencia exacta.
3. **Identidad frente a proyección:** la clave FTS aproximada sirve para equiparar consultas/candidatos y mantener el ranking de hoy; nunca se escribe de vuelta en el campo fuente, ni se usa para deduplicar o contar las etiquetas guardadas. La exactitud no aporta score, desempate, precedencia ni nivel separado. Cualquier ranking por exactitud sería un cambio aparte que requeriría autorización y medición.
4. **Compatibilidad legacy e índice:** no reescribir ni fusionar filas de memoria. La proyección FTS puede requerir reconstruir solo el índice derivado o añadir una ruta equivalente de actualización; antes debe comprobarse el ciclo de vida, coste y atomicidad de triggers. Filas legacy ya plegadas conservan la misma proyección efectiva y candidatos que hoy; las etiquetas perdidas son irrecuperables. No inferir etiquetas originales.
5. **Regla de compatibilidad por verificar:** no asumir que `NFKD` + borrar todos los combining marks equivale en todos los casos a la semántica efectiva del camino actual (en particular `ñ`, caracteres de marcas combinatorias y comportamiento FTS). Antes de implementar, demostrar que la proyección de cada valor guardado y la proyección de consulta reproducen la expresión/campo de ranking actual, incluso para datos directos/legacy. Si no, definir un helper explícito compatible, separado del valor persistido.
6. **Rutas:** un futuro cambio debe cubrir `recordar`/`buscar`, `aprender`/`guardar`, `agregar_sustantivos`, ingestión/consolidación, triggers/indexación FTS, QCR y autoexamen sin cambiar otros usos de `_quitar_acentos`. `actualizar` MCP queda pendiente separado, no se incluye ni se declara resuelto por compartir helpers.

### Sonda sintética de base mixta — predicción que debe verificarse

Base mínima con cuatro filas y los mismos demás campos/estado/score: fila legacy `ave` con SK `カラス`, fila nueva `vidrio` recibida como `ガラス`; fila legacy `cafe_antiguo` con SK `cafe`, fila nueva `cafe_nuevo` recibida como `café`. Los nombres de fila solo identifican fixtures, no cambian la consulta. El ranking de esta sonda se restringe al conjunto de dos filas del par consultado; en cada par se fijan idénticos los demás campos y un desempate estable por ID.

| Consulta (SK) | Antes: SK efectiva de las dos filas | Rangos antes | Propuesta: guardado exacto | Clave de ranking propuesta | Rangos propuestos |
|---|---|---|---|---|---|
| `ガラス` | `カラス` / `カラス` | ave 1, vidrio 2 (empate de score; desempate ID) | `カラス` / `ガラス` | `カラス` / `カラス` | ave 1, vidrio 2 (mismo empate/peso) |
| `カラス` | `カラス` / `カラス` | ave 1, vidrio 2 (empate de score; desempate ID) | `カラス` / `ガラス` | `カラス` / `カラス` | ave 1, vidrio 2 (mismo empate/peso) |
| `cafe` | `cafe` / `cafe` | antiguo 1, nuevo 2 (empate de score; desempate ID) | `cafe` / `café` | `cafe` / `cafe` | antiguo 1, nuevo 2 (mismo empate/peso) |
| `café` | `cafe` / `cafe` | antiguo 1, nuevo 2 (empate de score; desempate ID) | `cafe` / `café` | `cafe` / `cafe` | antiguo 1, nuevo 2 (mismo empate/peso) |

**Interpretación:** antes las etiquetas distintas colapsan durante la escritura, por lo que ambas filas almacenan la misma etiqueta; tras la propuesta se preservan `カラス`/`ガラス` y `cafe`/`café`, pero su clave de ranking sigue siendo la equivalencia histórica, deduplicada por fila. Cada par continúa con dos resultados de igual peso y el mismo orden estable. Son **rangos esperados de un fixture controlado**, no una medición del motor ni una afirmación de que todos los rankings de producción sean invariantes. La prueba implementada deberá registrar scores sin redondear, empates, rangos e IDs; si aparece cualquier diferencia de ranking, la propuesta todavía no satisface el requisito.

En control aislado con SQLite 3.40.1, FTS5 `trigram` no equiparó automáticamente las variantes japonesas, latinas ni devanagari citadas; no se debe confiar en un plegado implícito del tokenizer. `unicode61` de otra tabla (que no incluye SK) sí equiparó `café`/`cafe` y `क़िला`/`किला`, pero no `ガラス`/`カラス`. La clave de comparación compatible debe ser explícita y medirse con la versión de SQLite de CI/instalación; el microcontrol no sustituye QA.

## 4. Riesgos de base existente

- **Colisiones irreversibles ya persistidas:** distintas etiquetas pudieron convertirse en una durante la deduplicación previa. Ejemplo demostrado por las pruebas B1/B3: entrada `ガラス,カラス` queda como un solo `カラス`; el motor no puede inferir que hubo dos.
- **Recuerdos distintos hoy indistinguibles por SK:** una fila originalmente etiquetada ガラス y otra カラス pueden tener la misma etiqueta almacenada. La búsqueda por alias devolvería candidatos de ambos; medir FP y posición, no solo recall.
- **Candidatos y orden:** si la proyección no replica exactamente el campo SK que consume hoy FTS/QCR, puede alterar candidatos, saturar overfetch/top-k o afectar abstención y capas posteriores. No usar una marca de coincidencia exacta para ordenar ni aplicar bono, multiplicador o cambio de umbral; comparar puestos y scores para confirmar equivalencia.
- **Conteo/validación cambia intencionalmente:** al dejar de colapsar, algunas entradas hoy consideradas duplicadas pueden superar límites; entradas como `ガラス,カラス` pasan de un único término a dos. Casos 1–10 y entradas inválidas deben medirse antes de cambiar los errores del protocolo.
- **Scripts/consumidores:** autoexamen y herramientas que esperan `[a-z0-9_ñ]` o que normalizan y luego cuentan podrían rechazar/esconder marcas aunque el MCP principal las conserve. Auditar esos contratos; no ensanchar neuronas/dimensiones por accidente.
- **Tokenización Unicode/FTS:** combinar marcas, NFD/NFC y transliteraciones pueden comportarse de forma distinta por tokenizer y versión SQLite. Probar grafemas precompuestos y descompuestos, varias escrituras y signos sin asumir equivalencia de FTS.
- **Privacidad y alcance de censo:** no publicar términos, títulos ni filas de la base viva. Publicar únicamente cifras agregadas y hashes autorizados; sondeos con contenido sintético.
- **Sin migración automática:** preservar intactas filas legacy. Una eventual herramienta de reparación/censo sería una tarea aparte, solo en copia o modo lectura; no reescribir snapshots ni bases vivas durante esta propuesta.

## 5. Plan de medición previo a cualquier aplicación

**A. Controles unitarios de normalización/contaje** (fixtures sintéticos):
- exactos: `café` vs `cafe`, `ガラス` vs `カラス`, `क़िला` vs `किला`, `ñandú` vs `nandu`, NFC vs secuencia NFD, `ガ` precompuesto vs kana + U+3099;
- verificar que `normalizar_sustantivos_clave("ガラス,カラス")` futuro conserva dos formas exactas y que el conteo/validación ocurre después de deduplicación exacta;
- conservar signos/comas separadoras, ancho y reglas Unicode aprobadas por Cambio 1; probar entradas en MCP recordar/buscar/aprender/guardar/agregar y consolidación.

**B. Sonda de búsqueda pareada** (DB sintética, ambas filas gold separadas): guardar etiquetas exactas `ガラス` y `カラス`, y pares `café`/`cafe`, `क़िला`/`किला`; añadir filas simuladas legacy en las que la marca ya se perdió. Consultar cada forma marcada/no marcada con query/SK y registrar coincidencia de origen solo como diagnóstico; nunca usarla para ponderar/ordenar. Comparar resultados por ID, score sin redondear, rangos/R@1/R@5/MRR, falsos positivos, rechazos y estabilidad de orden inverso. Incluir consulta con varios sustantivos y claves proyectadas repetidas.

**C. Censo de compatibilidad de bases** (copias privadas en solo lectura): contar, sin exportar valores, (a) filas y términos SK; (b) términos con marcas `Mn/Mc/Me`; (c) cuántos cambian bajo la función histórica; (d) colisiones entre etiquetas distintas al plegar; (e) duplicados dentro del mismo campo antes/después; (f) cobertura FTS y frecuencia de candidatos exactos/solo alias. Separar corto/largo y snapshot/viva, reportar agregados por escritura/categoría solo si no revelan contenido. No migrar, no actualizar triggers, no escribir snapshot.

**D. Evaluación de recuperación**: baseline frente a candidato en casos por ID y por categoría, directo y MCP; normal y ruido, con hubs ON/OFF donde aplique. Registrar todos los rangos por caso (la QA oficial actual solo entrega agregados/fallos), exact-match/alias-match, R@1/R@5, MRR, FP por categoría y rechazos. Añadir casos deliberados de colisión, datos legacy y consulta sin marca. Mantener los protocolos/umbrales vigentes y revertir cualquier pérdida de rango/recall o aumento FP según autorización. No interpretar el resultado 0/921 de Cambio 1 como evidencia de mejora: solo fue un piso de no regresión.

**E. Escrituras y compatibilidad:** volver a medir la batería MCP de guardados (referencia Cambio 1: 69/80) con cada escritura exacta preservada; validar consolidación, dedup exacta, límites y lecturas. Probar `actualizar` aparte y documentar el resultado como pendiente independiente hasta que Dennys autorice ese subcambio.

No se ejecutó censo de bases ni QA en esta investigación; los pasos anteriores son un plan, no resultados.

## 6. Límites y decisión pendiente

Esta investigación identifica el borrado destructivo al normalizar y plantea separar la etiqueta preservada de una clave de búsqueda aproximada. No demuestra aún beneficios de ranking ni seguridad en la base viva. La vuelta `sin marcas` es necesariamente ambigua para escrituras en que las marcas distinguen palabras. **No hay cambio de motor autorizado aquí**; el siguiente paso es que Dennys revise este análisis y el esquema de diff y decida si autoriza una propuesta de implementación y su medición.
