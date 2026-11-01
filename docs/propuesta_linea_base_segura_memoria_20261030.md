# Propuesta: línea base segura de cómo recuerda BioRAG

**Fecha:** 2026-10-30
**Estado:** solo diseño; pendiente de auditoría y autorización expresa de Dennys para medir.
**Rama prevista:** `arena/9a54babb-memorybiorag`
**Alcance:** observar recuperación principal, pistas, ruido, grafo, espejo de asociaciones y estados de memoria antes de proponer reparaciones. No ejecutar, no cambiar motor/ranking y no tocar bases originales.

> **Regla de interpretación:** el ruido útil no se mata. Una arista, su tipo, su peso o una coincidencia de nombre no bastan para declarar inútil una asociación.

## 1. Aprovechar el trabajo existente

Esta propuesta no reinicia la investigación ni sustituye sus artefactos:

- Reutiliza como gold inicial y protocolo de canales los 88 episodios/224 consultas, sus etiquetas y el arnés descritos en `docs/qa_intuicion_asociaciones_propuesta_20261030.md`, `docs/implementacion_qa_intuicion_asociaciones_e1.md` y `scripts/casos_qa_intuicion_asociaciones_e1.jsonl`.
- Conserva A/B/C1/C2 y D/D-inv para separar resultados principales, asociaciones serializadas, contexto BFS y efecto del orden/estado de sesión. Sus brazos actuales no miden ráfaga forzada ni el despertar profundo; esos recorridos se añaden como condiciones separadas, no se mezclan con ellos.
- Sigue `docs/revision_trazabilidad_sinapsis_rafaga_despertar_20261030.md`: `sinapsis` es la fuente canónica; `largo_plazo.asociaciones` es un espejo CSV que algunos escritores actualizan y otros no; ráfaga y `deep=True` pueden mutar estados/pesos; el tipo de una arista no siempre es procedencia inmutable.
- Conserva los límites de la comparación aprobada, `docs/informe_comparacion_prefijo_aristas_mcp_20261030.md` y su JSON: los cambios se observaron en el intervalo MCP de `consolidar`, sin atribución a subfunciones internas. No se repite esa comparación ni se le asigna causalidad nueva.

El gold congelado y el arnés existente están documentados como preparados pero no ejecutados. La presente propuesta tampoco los ejecuta.

## 2. Tres ejes que no se deben colapsar

### A. Resultado y relevancia semántica

Etiquetar por separado:

1. **Objetivo principal:** recuerdo que responde a la pregunta; medir únicamente dentro de `resultados`.
2. **Pista útil:** recuerdo lateral que aporta un paso, condición o evidencia para resolver la tarea.
3. **Serendipia útil:** recuerdo no pedido literalmente que abre una conexión pertinente y defendible.
4. **Neutral/contextual:** relacionado pero no accionable para esta pregunta.
5. **Ruido tonto:** irrelevante, distractor o engañoso.

Usar evidencia literal del recuerdo, juicio respecto de la consulta y la rúbrica ya propuesta. Una arista o una palabra común no cambia una etiqueta. Los controles negativos se mantienen separados de positivos y de las métricas del objetivo.

### B. Tres representaciones del grafo/estado

En cada corte registrar separadamente:

- **Grafo directo `sinapsis`:** filas dirigidas, orientación, tipo, peso, `creado_en`, `ultimo_uso`; además, pares normalizados A—B para comparar estructura sin borrar la diferencia de dirección/tipo.
- **`sinapsis_latentes`:** mantener como tabla/capa independiente, con origen, destino, saltos, peso atenuado, PMI y dimensión compartida. No contarla como arista directa ni mezclarla con BFS de `sinapsis`.
- **Espejo CSV `largo_plazo.asociaciones`:** guardar su contenido bruto por nodo y derivar, sin escribir, el conjunto de vecinos que resultaría de consultar ambas direcciones de `sinapsis`. Informar diferencias, nodos ausentes, nombres huérfanos y truncamiento de serialización por separado. No llamar a la función de sincronización durante la observación.
- **Estado del recuerdo:** para cada concepto, estado activo/dormido, peso sináptico del nodo y marcas temporales pertinentes. Informar transiciones y su magnitud aparte de las aristas.

Los snapshots son solo de la fixture temporal. Una diferencia en el espejo no significa que la arista canónica desapareció; una arista canónica no garantiza que el espejo esté actualizado.

### C. Tres rutas de recuperación independientes

Cada condición parte de una copia limpia de la misma fixture inicial, salvo la diferencia de estado declarada para el brazo de despertar. No usar una salida para escoger la consulta siguiente.

| Condición | Parámetros MCP propuestos | Qué observa | Qué excluye |
|---|---|---|---|
| **N — normal** | `deep=False`, `forzar_rafaga=False`, sin `rafaga_palabras`, `context_window=0`. | Recuperación normal y objetivo principal; respuesta lateral puede conservar `asociados=True` para observar asociaciones sin hacerlas ranking. Reutiliza A/B de E1: A con salida asociativa apagada, B con salida asociativa encendida, mismo query y copia equivalente. | No fuerza ráfaga, no expande BFS y no activa búsqueda profunda de dormidos. |
| **G — contexto activo** | Igual que N, con `context_window=1` y, en subbrazo separado, `2`; `deep=False`. | Vecinos de `sinapsis` visibles por BFS y pistas que aparecen en `contexto_expandido`. Se apoya en C1/C2 de E1. | No lo interpreta como despertar; el BFS normal filtra dormidos. No atribuye una ruta real de dos saltos si MCP no devuelve traza de ruta. |
| **R — ráfaga sin despertar** | `forzar_rafaga=True`, lista `rafaga_palabras` fija y preaprobada, `deep=False`, `context_window=0`; copia limpia verificada con **todos** sus nodos activos antes de la llamada. Sin consolidación ni daemon/sleep-cycle durante la recuperación. | Capa de ráfaga, candidatos, posibles inserciones/refuerzos en `sinapsis`, espejo y diffs MCP. La ausencia comprobada de dormidos y de procesos que los duerman evita que esta condición mida despertares. | No lo mezcla con N ni G; no mide rescate de dormidos. Si cualquier nodo cambia a dormido o hay una mutación de estado no prevista, la corrida R queda contaminada. No inferir que todo resultado de ráfaga produce `rafaga_rememb`: si el par ya existe, el código refuerza peso y conserva el tipo. |
| **W — despertar por búsqueda profunda/BFS** | `deep=True`, `context_window=1` (y, si se aprueba, otro subbrazo de 2); sin `rafaga_palabras`, `forzar_rafaga=False`. | Descubrimiento y transición de un nodo dormido alcanzable desde una semilla activa, usando el recorrido profundo separado de ráfaga. | No combinar con R. La fixture debe impedir coincidencia léxica directa del objetivo dormido; si aparece en `resultados` por búsqueda profunda directa, etiquetar ese caso como tal, no como rescate BFS. |
| **R+W — interacción, opcional** | Ráfaga con un nodo dormido en una copia distinta. | Solo si en el futuro Dennys autoriza medir la interacción: documenta conjuntamente ráfaga y despertar propio de ráfaga. | Nunca mezclar con R ni W al calcular un efecto puro; reportar como brazo combinado aparte. No es requisito para la primera línea base. |

Los valores de `asociados`, `context_window` y `deep` deben constar en cada invocación. La serialización de asociaciones no se presentará como cambio de ranking sin comparación pareada de `resultados`.

### Prerrequisito no resuelto para W

El gold E1 descrito hasta ahora construye recuerdos mediante MCP, pero no establece por sí solo un estado dormido intencional. En la inspección anterior tampoco se identificó una herramienta MCP explícita para dormir nodos. **W permanece pendiente y fuera de la línea base que se congele por ahora:** todavía no hay un método reproducible, aislado y autorizado para preparar ese estado. No se sustituirá por un `UPDATE` SQL, ni por repetir consolidaciones que podrían cambiar otras aristas/estados, ni se contará como resultado. Primero deberá proponerse y auditarse un procedimiento que deje el nodo dormido conectado en una fixture temporal, con verificación de solo lectura y sin tocar DB original; hasta entonces no se ejecuta ni se congela W.

## 3. Construcción aislada y fijación de condiciones

1. Partir del gold E1 existente, no inventar etiquetas después de ver respuestas. Congelar consultas, etiquetas, nombres y hash del gold antes de construir la plantilla.
2. Hacer un **preflight de nombres sin escribir**. Aplicar a cada nombre la misma normalización de identidad que usa el ingreso MCP; exigir unicidad después de normalizar y registrar la forma original y normalizada. Calcular también tokens y posibles solapamientos con la regla actual de `co_nombre` (`core/sinapsis.py:195-221`: palabras de nombre de ≥4 letras, exclusión de stopwords, al menos dos términos, solapamiento ≥0,30 y límite de candidatos). Marcar pares con riesgo de vínculo automático y posibles prefijos compartidos; no renombrarlos automáticamente ni declarar ruido por ese patrón. Es una lista de expectativas, no reemplaza el grafo observado: candidatos pueden ser omitidos por límites, estado, orden o vínculos anteriores.
3. Construir la fixture sintética con el recorrido MCP real ya propuesto: preflight → `aprender` → `consolidar` → `vincular`. Guardar una instantánea de solo lectura en cada límite de llamada MCP, además de la plantilla final. Diferencias por etapa indican cuándo apareció o cambió una fila; no atribuir a una subfunción interna de una llamada consolidada. Incluir todos los enlaces automáticos por nombre, tokens, sinónimos/PMI, coocurrencia y DMN, además de los explícitos. No asumir que los enlaces gold son el grafo completo ni que `tipo` es procedencia inmutable.
4. Antes de congelar, validar en la fixture: unicidad de conceptos, `PRAGMA integrity_check`, filas dirigidas completas de `sinapsis` con tipos/pesos, `sinapsis_latentes` por separado, estado de los nodos y comparación del espejo CSV con vecinos derivados de ambas direcciones del grafo. Confirmar por consulta dirigida que la captura no quedó truncada. Revisar las rutas mínimas del grafo real, incluidos todos los enlaces automáticos. Si un atajo cambia la distancia declarada, **no borrar ni desactivar la conexión**: documentar el caso y, antes de congelar el gold, reclasificarlo a su distancia real o sustituirlo por un episodio semánticamente revisado que sí cumpla el estrato; conservar el episodio/cambio y la razón en el registro de preflight. Una conexión `co_nombre` o de otro tipo no se descarta por su etiqueta.
5. Repetir la construcción en una segunda fixture temporal independiente con nombres, orden, reloj y entorno fijos; comparar nodos, direcciones, tipo/peso, estado y espejo (normalizar solo campos temporales cuya igualdad no esté garantizada). Si hay diferencias estructurales, no congelar como baseline pareado hasta caracterizar la variación o limitar explícitamente la comparación a una plantilla materializada, reportando que no se probó repetibilidad. No escoger la construcción que dé el resultado de búsqueda preferido.
6. Verificada la preflight y repetibilidad, congelar la plantilla con hashes y crear copias temporales independientes por consulta×condición (o bloques según el control D/D-inv ya diseñado). Ninguna condición comparte estado mutable. Cada servidor MCP stdio debe apuntar exclusivamente a una ruta bajo `BIORAG_QA_TEMP_ROOT`; registrar y validar `BIORAG_PATH`. Proceso separado por condición/copia, reloj y variables deterministas según el arnés E1 (`PYTHONHASHSEED=0`, estado DMN temporal exclusivo y neurona según brazo autorizado). Capturar JSON-RPC crudo/parseado, stderr/warnings, tiempos e `query_id`.
7. No llamar durante recuperación a `feedback`, `desvincular`, herramientas de escritura, consolidación ni sincronización de asociaciones. La ráfaga se invoca solo en R/R+W explícitamente etiquetados.

La propuesta de E1 estima 2.168 invocaciones MCP para construir su fixture y correr A/B/C1/C2/D/D-inv, según sus conteos. Esta propuesta añade R y W (y, si se autorizara, R+W), por lo que **no** reutiliza ese total como conteo completo: el total futuro se recalcularía por consulta, copia, brazo, error y reintento antes de ejecutar.

## 4. Captura antes/después y regla de contaminación

Para cada consulta y copia temporal, tomar un snapshot de solo lectura:

- **Antes de fixture:** identidad/hashes de la DB plantilla y versiones/commit/configuración.
- **Después de construir fixture, antes de recuperar:** hashes de tablas; filas completas de `sinapsis`, `sinapsis_latentes`, `largo_plazo` (solo claves, estado/peso/tiempo y espejo CSV) y dimensiones necesarias para auditar ruta; métricas de nodos/aristas y diferencias `sinapsis`↔espejo.
- **Inmediatamente antes y después de cada llamada MCP de recuperación:** hash por tabla y diffs fila/columna, mismos conjuntos canónicos y mismo estado de nodo. Guardar JSON-RPC y respuesta cruda enlazados por `query_id`.
- **Después de cada condición:** recalcular grafos/rutas y diferencias espejo/canónico desde copia temporal, nunca desde la DB viva o snapshot original.

Antes de ejecutar habría que cerrar una whitelist de mutaciones esperadas cotejada con la versión exacta de código. La política ya propuesta para E1 permite únicamente las escrituras de telemetría/actividad que el código confirme. Para R, aceptar solo los diffs explícitamente previstos por el recorrido de ráfaga (posible arista insertada o refuerzo del peso/tipo existente; SDM dirty según corresponda); para W, solo transiciones de estado/peso/tiempo previstas y telemetría. En N/G no se acepta mutación de grafo ni estado. Una escritura no prevista contamina esa corrida: se conserva el diff, no se borra ni se corrige en sitio, y no se amplían retrospectivamente las reglas de aceptación.

No usar solo el hash global como atribución. Conservar fila por fila origen/destino/tipo/peso antes/después; como un tipo puede ser reemplazado por otro escritor y algunos mecanismos no sincronizan el espejo, los snapshots delimitan el intervalo MCP, pero no siempre identifican una subfunción interna exacta. Sin traza explícita de ruta en la respuesta MCP, informar **«no atribuible»** para el recorrido interno; no deducirlo de una BFS offline.

## 5. Métricas separadas

### Objetivo principal

- R@1, R@5 y MRR@5, solo sobre `resultados`; cobertura del objetivo en cualquier canal se informa aparte y no se convierte retroactivamente en acierto principal.
- Comparación pareada N-A/N-B para confirmar si encender la serialización lateral cambia o no IDs/orden de resultados.

### Pistas y ruido

Por `asociaciones_enriquecidas`, `asociaciones` plana, `contexto_expandido` y unión deduplicada, publicar por separado:

- recall de pistas útiles y cobertura de episodios con al menos una pista útil;
- precisión de utilidad lateral entre elementos juzgables;
- serendipia útil;
- ruido tonto visible por consulta y canal, separando resultado principal de canal lateral;
- abstención y falsos positivos en controles negativos.

El gold no convierte una pista útil en ruido por no ser el objetivo literal. Una arista o el peso no determinan juicio humano.

### Grafo, espejo y estado

- Nuevas, reforzadas, borradas o reorientadas filas directas, sin agrupar tipos diferentes.
- Cambios de `tipo` aparte de cambios de peso; notas si el tipo previo era reemplazable.
- Discrepancias entre vecinos derivados de `sinapsis` y nombres en el espejo CSV; no llamar “reparada” a una diferencia solo porque aparece en una ruta de sincronización.
- Nodos activos/dormidos antes/después, cambios de peso y marca temporal, y si el nodo apareció en `resultados` o `contexto_expandido`.
- Resultados y trazas de búsqueda normal, ráfaga, deep/BFS y posible interacción en tablas distintas. No sumar los recalls o despertares de esos brazos en un único número.

Latencia, bytes, salida truncada, fallos MCP, número de intentos y reintentos también se reportan por condición; no se omiten fallidas.

## 6. Qué puede comprobar la línea base

Si se aprueba y ejecuta bajo estas guardas, puede comprobarse para **esa fixture y esas consultas**:

- qué retornó MCP en `resultados` y en cada canal lateral, y el rango del objetivo principal;
- qué aristas directas cambiaron dentro del intervalo de una llamada y qué campos del espejo/estado cambiaron;
- si la ráfaga fue invocada según el MCP, qué registros recuperó, y qué transición de estado/arista ocurrió en su brazo;
- si deep/BFS expuso o despertó un dormido en el diseño controlado, siempre que la respuesta/captura permita atribuir el canal;
- divergencias entre `sinapsis` y el espejo CSV, y efectos reproducibles de las condiciones en copias equivalentes;
- valoraciones semánticas de utilidad/ruido de candidatos ciegos a brazo/score mediante la rúbrica y anotación independiente ya propuestas.

## 7. Qué quedará sin demostrar

- Que el tipo o peso de una arista establezca su verdad, calidad, utilidad general o causa original.
- Qué subfunción interna creó una fila dentro de una operación MCP que ejecuta varios mecanismos, salvo que exista traza explícita; los cambios por intervalo solo atribuyen a la llamada MCP.
- Que un shortest path encontrado offline sea el camino que realmente recorrió la búsqueda. Sin `trazabilidad.rutas_expansion` suficiente, su atribución es «no atribuible».
- Que una condición mejore otras bases, idiomas, datos reales o tareas no incluidas; una fixture sintética no sustituye producción.
- Que ver una transición de dormido a activo pruebe por sí sola la utilidad de la pista, o que no verla pruebe inutilidad de la conexión.
- Que el efecto de R sea equivalente al fallback natural: el brazo forzado observa la ruta de ráfaga de modo controlado; el fallback condicional debe ser una condición distinta, reportada con sus parámetros.
- Que R+W identifique efectos puros; es solo interacción y se mantiene separada.

## 8. Condiciones para pasar de diseño a ejecución

Requieren autorización expresa de Dennys: correr cualquier MCP de medición, construir o modificar una fixture temporal para producir dormidos, ejecutar ráfaga forzada/fallback, ejecutar `deep=True`, QA completa o ampliar el gold. Antes de ese permiso, quedan pendientes la auditoría de la propuesta, el cierre de la whitelist exacta por versión y la solución reproducible para preparar la condición W. No se propone reparar ni desactivar ningún mecanismo.
