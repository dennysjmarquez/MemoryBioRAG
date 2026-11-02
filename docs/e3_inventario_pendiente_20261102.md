# E3 — inventario de trabajo restante y separación de etiquetas

**02 nov 2026 · inventario, sin propuesta de cambio de motor.** No se aplican parches, no se hacen migraciones ni fusiones de datos y no se avanza a E4. Los detalles por consulta, etiquetas gold y crosswalk permanecen fuera de este documento.

## Distinción obligatoria de alcance

Hay dos objetos distintos que no se deben mezclar:

1. **Marcadores de la QA de prueba:** los 14 casos MCP llamados `pendiente hueco 1` son estados de llamadas de prueba que se rechazaron antes de abrir la base. Son 14 casos sin búsqueda ejecutada; no son etiquetas de memoria ni candidatas a fusionarse. Siguen intactos.
2. **Fusión/uso de etiquetas de memoria:** `sustantivos_clave` es metadato de recuerdos. El campo plegado histórico puede colapsar distinciones; existe además `sustantivos_clave_exactos` para conservar la forma NFC. La transferencia de corto a largo plazo trata las dos columnas para el mismo concepto, pero la consulta MCP reduce la entrada a la forma plegada y FTS indexa la columna plegada. La columna exacta no aparece en el `MATCH` de búsqueda. El esquema no retrorellena las filas antiguas. Por tanto, «integrar/fusionar etiquetas» es una cuestión de representación, consulta e historia de datos; no una operación sobre los 14 casos de prueba, ni permiso para fusionar etiquetas entre recuerdos distintos.

El código actual refleja esa separación: el escritor y la consolidación preservan el campo exacto; la ruta de búsqueda sigue consumiendo el plegado. Los documentos históricos de E3 Cambio 2 describen etapas distintas de su propuesta y resultado; para este inventario prevalece el código de `HEAD`, no una frase histórica aislada.

## Sondeo sintético: reemplazo frente a acumulación dentro de un recuerdo

Se ejecutó `scripts/diagnosticar_reemplazo_vs_acumulacion_etiquetas_sinteticas_e3.py`. Creó un esquema vacío temporal, lo copió a dos bases scratch independientes y aplicó cinco actualizaciones al mismo y único recuerdo sintético en cada copia. La rama **reemplazo** usa la consolidación actual. La rama **acumulación** es un contrafactual solo en la copia: tras cada actualización conserva la unión deduplicada de las etiquetas. No se abrió ninguna base del usuario, no se fusionaron recuerdos y no se hizo backfill. Ambas bases terminaron con `PRAGMA integrity_check=ok`.

Las cinco entradas tuvieron tres etiquetas cada una, con una pista estable y dos facetas nuevas por actualización: unión histórica de **11** pistas. Consultamos cada término exclusivamente contra la columna `sustantivos_clave` del FTS5; esto mide recuperabilidad de etiquetas, no ranking/recall del motor completo ni pistas sinápticas/asociaciones.

| Política en la copia | Etiquetas almacenadas | Pistas históricas encontrables por FTS | Pérdida si las cinco facetas siguen siendo válidas | Etiquetas antiguas si solo la última faceta sigue válida |
|---|---:|---:|---:|---:|
| Reemplazo actual | 3 | 3/11 (27,3%) | 8 | 0 |
| Acumulación contrafactual | 11 | 11/11 (100%) | 0 | 8 |

Ambas políticas recuperan 3/3 pistas de la última actualización. El resultado **no adjudica** si las facetas previas siguen describiendo el recuerdo: bajo verdad complementaria, reemplazar pierde cobertura; bajo verdad de supersesión, acumular conserva ocho pistas obsoletas y amplía la activación potencial. La acumulación también llevó el conjunto almacenado a 11, aunque cada entrada individual tenía 3 etiquetas (la validación de escritura acepta 2–10 por entrada). Así que el efecto observado es el trade-off cobertura/deriva, no evidencia de que acumular sea mejor.

El código actual reemplaza el par plegado/exacto al recibir etiquetas no vacías en percepción y consolidación; sin etiqueta entrante conserva las actuales. La herramienta llamada `biorag_agregar_sustantivos` también hace `UPDATE` con la lista entrante, no una unión. No se cambió ese comportamiento. El primer sondeo solo midió pistas de etiqueta en FTS. A continuación se ejecutó una prueba distinta de las rutas MCP.

## Rutas MCP: historial útil/contradicho, etiquetas y vecinos

`scripts/diagnosticar_rutas_mcp_historial_pistas_vecinos_e3.py` registra las funciones MCP y las llama directamente sobre copias SQLite sintéticas. Cada fixture tiene un recuerdo objetivo y dos recuerdos vecinos enlazados por sinapsis manuales. Se probaron dos rutas de escritura (`actualizar`, `agregar_sustantivos`), dos rutas de lectura (`sustantivos`, `recordar`), dos supuestos de historial (faceta histórica aún útil; registro histórico explícitamente contradicho) y las ramas de reemplazo actual y acumulación solo en copia: **8 brazos**. La búsqueda usó `recordar` con `asociados=True` y `context_window=1`.

| Supuesto y política en copia | Pista histórica en FTS de etiquetas | Ruta MCP `recordar` encuentra el objetivo por pista histórica | Nuevas/estables | Vecinos al recuperar el objetivo |
|---|---|---|---|---|
| Historia útil · reemplazo | No (0/1 pista exclusiva) | No | Sí, objetivo en rango 1 | — al no haber objetivo |
| Historia útil · acumulación sintética | Sí (1/1) | Sí, rango 1 | Sí, rango 1 | 2/2 en asociaciones y contexto |
| Historia contradicha · reemplazo | No en etiquetas | **Sí**, rango 1 desde el contenido histórico conservado | Sí, rango 1 | 2/2 en asociaciones y contexto |
| Historia contradicha · acumulación sintética | Sí en etiquetas | **Sí**, rango 1 | Sí, rango 1 | 2/2 en asociaciones y contexto |

`actualizar` y `agregar_sustantivos` dieron estado `ok` y el mismo resultado de escritura en cada brazo: la segunda ruta también reemplaza las etiquetas entrantes, pese a su nombre. `sustantivos` confirmó el estado almacenado. En el caso útil, la pista exclusiva anterior (fixture: puntuación MCP 0,0726 con acumulación) recupera el objetivo solo cuando sigue en las etiquetas; el contenido no repite ese término. En el caso contradictorio, el término histórico ya no está en las etiquetas del brazo de reemplazo, pero `recordar` aún encuentra el nodo porque la narración conservada contiene ambos lados y la contradicción. La variante de acumulación también lo encuentra y puntúa 0,0749 frente a 0,0721 en ese query de fixture. Estos scores son solo diagnósticos locales de la copia, no mediciones generalizables.

En todos los casos donde se recuperó el objetivo, los dos vecinos sintéticos aparecieron tanto en asociaciones enriquecidas como en contexto expandido. **Corrección de alcance:** el arnés anterior llamó directamente a las funciones registradas, no usó el transporte MCP stdio. Las asociaciones manuales iniciales se conservaron, pero al abrir la copia el constructor también añadió una sinapsis `dmn_synthesized`; por ello, la lista de contexto no provenía solo de las aristas sembradas. Las escrituras de etiquetas no borraron vecinos ni recuerdos. Este sondeo directo es evidencia del resultado de sus rutas locales, no evidencia del transporte stdio ni de una causa aislada para todas las pistas vecinas. No se asignó verdad a datos reales ni se aplicó un filtro manual. La ausencia de etiquetas viejas en la rama de reemplazo es solo una observación de esa ruta en la copia; no es una decisión de descartarlas. No se elige una política.

## Verificación por MCP stdio: apertura y orden de consultas

Para separar el handshake, la apertura y las consultas, se ejecutó `scripts/diagnosticar_mcp_stdio_apertura_orden_etiquetas_e3.py` con el servidor FastMCP real sobre copias SQLite temporales. La semilla sintética se creó con síntesis DMN apagada y dos asociaciones manuales bidireccionales ya presentes (4 filas `sinapsis`). Cada hijo usó `scripts/qa_stdio_server_intuicion.py`, que impone la ruta bajo `BIORAG_QA_TEMP_ROOT` y evita lanzar el daemon global; la copia MCP tuvo la síntesis DMN activa. El protocolo `initialize` ocurrió antes de toda herramienta. Luego `sustantivos` fue la primera llamada y abrió la instancia persistente; se capturó el grafo antes/después. Después se llamó una ruta MCP de escritura y se consultó `recordar` en ambos órdenes: pista antigua→nueva y nueva→antigua. Diseño: 2 historiales × 2 cargas de etiquetas (reemplazo o lista acumulada enviada explícitamente) × 2 escrituras × 2 órdenes = **16 sesiones stdio**.

### Causas demostradas en estas copias

- El handshake MCP `initialize` no cambió el grafo. En los 16 brazos, la primera llamada `sustantivos` provocó la apertura y sumó exactamente una fila `dmn_synthesized` (`recuerdo_sintetico_objetivo` → `vecino_sintetico_candidato_dmn`, peso 0,30). Las cuatro filas manuales iniciales siguieron presentes. Esto identifica la síntesis al abrir como causa del cambio total de grafo; no lo causó el orden posterior de consultas.
- Después de `actualizar` o `agregar_sustantivos`, no apareció ninguna arista nueva ni desapareció una inicial. Tampoco se añadieron aristas tras las dos llamadas a `recordar` en ninguna de las dos secuencias.
- En la faceta histórica útil, con contenido idéntico y término antiguo ausente del texto, el reemplazo no recuperó el objetivo por esa consulta; enviar la lista acumulada por MCP sí lo recuperó en rango 1 (score 0,217). La consulta nueva quedó en rango 1 en ambas cargas (0,2167). Es una comparación emparejada de la copia, no una recomendación de política.
- En la faceta contradicha, el término antiguo recuperó el objetivo en rango 1 incluso bajo reemplazo porque el término aparece en el contenido que conserva la contradicción (score 0,0722). Con la lista acumulada el score de ese mismo query subió a 0,2192; la consulta nueva quedó en rango 1 en ambos casos. La presencia de la etiqueta en la carga acumulada afecta el resultado medido, pero el nodo ya era recuperable por texto sin esa etiqueta.
- Los dos vecinos manuales aparecieron en asociaciones enriquecidas cuando el objetivo fue recuperado; el contexto expandido mostró además el vecino DMN automático. Así se separan «asociaciones iniciales preservadas» y «grafo completo tras apertura».
- En este fixture el resultado por rol de consulta (hit, rango y score) fue el mismo al invertir el orden; el snapshot mostró cero aristas nuevas después de cada búsqueda. Las rutas de escritura `actualizar` y `agregar_sustantivos` coincidieron para los mismos valores de entrada. Esto concuerda con `core/memory_store.py` (apertura condicional de `sintetizar_sinapsis_dmn`) y `core/dmn_engine.py` (inserción de tipo `dmn_synthesized`). Los scores del sondeo directo anterior (0,0749/0,0721) no se comparan con estos scores stdio (0,2192/0,0722): difieren el harness, apertura y estado del grafo.

### Observaciones compatibles, no causas generalizables

Que un nodo aparezca con vecinos es compatible con sus aristas manuales conservadas, con la arista DMN creada al abrir y con ambas rutas de contexto/asociaciones; sin una separación temporal, no se atribuye todo a una sola. Que una contradicción histórica aparezca en `recordar` es compatible con coincidencia en contenido; aquí el contraste de etiquetas modula el score en el fixture, no demuestra qué pasaría en otros corpora. La invariancia al invertir dos consultas solo cubre estas 16 copias, dos términos y este estado inicial; no demuestra que el orden nunca importe.

El brazo «lista acumulada» pasó la unión histórica como el valor entrante a la herramienta MCP real. No implementó acumulación automática. No se fusionaron recuerdos, no se descartaron ni adjudicaron etiquetas en datos reales, no se aplicó un parche y E3 continúa abierto.

## Inventario restante de E3 y una hipótesis falsable

La auditoría confirmó la apertura y los resultados por orden **en esta fixture**. Quedan separados estos frentes; ninguno decide reemplazo frente a acumulación:

- **Apertura del MCP:** causa demostrada en la fixture controlada: la primera herramienta que abre el store con DMN activo añade una arista `dmn_synthesized`; el handshake no y las búsquedas probadas tampoco. Falta replicar variando número y densidad de candidatos/vecinos.
- **Escritura de etiquetas:** en las rutas MCP ya probadas, `actualizar` y `agregar_sustantivos` guardan el payload entrante; el segundo nombre no implica unión automática. Falta contrastar otras entradas (aprender/guardar, percepción y consolidación corto→largo) en stdio y distinguir política de actualización de la llamada que originalmente crea el recuerdo.
- **Pista vs vigencia:** una pista histórica puede seguir siendo útil, estar contradicha en el contenido o aparecer solo en el campo de etiquetas. La búsqueda puede recuperar por contenido aun cuando el término ya no esté en etiquetas; el score puede cambiar cuando el término sí está indexado. Esto no adjudica qué afirmación es verdadera.
- **Pistas del grafo:** separar por etapa el grafo sembrado, la síntesis al abrir, lo que persiste tras escribir y lo que cada búsqueda expone como asociación/contexto. La lista de vecinos no es una medida de procedencia por sí sola.
- **Etiquetas de prueba:** los 14 marcadores `pendiente hueco 1` siguen siendo QA; no entran en estas hipótesis de metadatos ni se reetiquetan.

### Hipótesis de trabajo H-E3-ETQ-01 (todavía no una decisión)

**Si el contenido y el grafo se mantienen idénticos, conservar un término histórico en `sustantivos_clave` aumentará su recuperabilidad o su score MCP aunque el recuerdo contradiga ese término en su historia; por tanto, el campo etiqueta codifica una pista temática, no la vigencia/validez de la afirmación.** En un historial útil, la predicción es que un término antiguo ausente del texto solo dará acceso al nodo cuando la etiqueta esté presente. En uno contradicho cuyo texto conserva ambos lados, la predicción es que la búsqueda seguirá encontrando el nodo aun sin la etiqueta, y que la etiqueta puede reforzar el score sin resolver la contradicción.

La hipótesis está **parcialmente apoyada, no generalizada**, por la fixture auditada: 1) el término útil ausente del contenido no encontró el objetivo con payload de reemplazo y sí lo hizo con lista acumulada (rango 1); 2) el término contradicho encontró el objetivo en ambos brazos por contenido, con scores 0,0722 sin la etiqueta antigua y 0,2192 con ella. La auditoría de orden no encontró cambios al invertir las dos consultas en los casos medidos. Estos números pertenecen a copias sintéticas y no comparan conjuntos de datos reales.

**Cómo falsarla o delimitarla, sin elegir política:** repetir con varias familias de términos sintéticos y copias emparejadas; congelar contenido, etiquetas exactas, pesos, enlaces manuales y snapshot posterior a la apertura; variar solo el payload de etiquetas activo. Guardar todas las pistas de entrada en un manifiesto sintético inmutable, incluso las que no aparecen en el campo activo de un brazo. Ejecutar por MCP stdio las dos rutas de escritura y consultas antigua/nueva en ambos órdenes; registrar R@1/R@5, MRR, score, falsos positivos, asociaciones/contexto y deltas del grafo en handshake, primer tool, escritura y cada consulta. No borrar filas, recuerdos ni aristas. Si el texto no contiene la pista, el brazo sin etiqueta falla y con etiqueta acierta, se replica el efecto temático; si la contradicción aparece en ambas ramas, se confirma que el mecanismo de recuperación no adjudica vigencia; diferencias de rango, pistas o grafo exigirán separar esas causas antes de inferir una política.

No se prepara diff ni candidato al motor con esta hipótesis. La comparación es solo un próximo experimento en copias sintéticas; E3 permanece abierto y E4 fuera de alcance.

## Matriz de estado

| Frente E3 | Estado comprobado | Trabajo restante, sin decisión de implementación |
|---|---|---|
| CJK: OR trigramas y umbral 2 | Línea base y arnés corregido medidos en fixture; pruebas sintéticas de lista de vecinos >5 y error FTS registrado completadas. Ambos parches continúan **NO APLICAR**. | Mantener `を指す` como pista diagnóstica, nunca filtro. Revisar evidencia/diff antes de considerar cualquier cambio. |
| Falsos positivos ingleses | Investigación aislada completada: los dos negativos sintéticos tienen causas distintas (substring literal frente a substring de una expansión WordNet). No es una tasa general; no se cambió el filtro ni WordNet. | Ninguna regla de filtrado se deriva automáticamente. Si se evalúa una alternativa, medir recall y falsos positivos, además de las pistas recuperadas. |
| Marcadores de prueba `pendiente hueco 1` | 14/14 solicitudes MCP rechazadas antes de búsqueda; en baseline directo actual 7/14 esperados en top 5, siete sin resultados. No se cambiaron marcadores. | Conservar como estado de prueba. No fusionarlos con `sustantivos_clave` ni tratarlos como etiqueta gold adjudicada. |
| Etiquetas exactas y plegadas de recuerdos | Escritura/consolidación dispone de dos columnas. La búsqueda MCP pliega el término y usa FTS sobre el campo plegado; filas históricas exactas pueden ser `NULL`. Se midieron las rutas MCP de escritura/lectura y la H-E3-ETQ-01 quedó parcialmente apoyada en copias. | Es el frente distinto de «fusión de etiquetas» que requiere decisión. No hay aquí propuesta de backfill, alias, fusión entre recuerdos ni cambio del índice. Replicar la hipótesis con más familias; no adjudicar facetas reales. |
| Apertura MCP y pistas de grafo | En 16 sesiones stdio, handshake sin cambios; primer tool añadió una arista `dmn_synthesized`, mantuvo las cuatro filas manuales, y las consultas posteriores no cambiaron grafo. Invertir dos consultas no cambió resultados en esa fixture. | Repetir con distinta densidad de candidatos/vecinos y entradas de escritura. Atribuir cada pista al estado exacto del grafo antes/después de abrir, escribir y consultar. |
| Normalización de identidad Unicode | El motor actual incluye identidad NFC/ancho y el predicado de límites W/F. La investigación en copias documentó diferencias, colisiones posibles y casos no representados por la QA. | No extrapolar el corpus de 132 consultas; cualquier cambio futuro necesitaría comparar texto, ranking, escritura/recuperación y etiquetas exactas por separado. |
| Resto del inventario multilingüe | El informe E3A identifica rutas de stemming, stopwords, WordNet, hub/puentes, dimensiones, categorización, SRL, sinapsis/PPMI y aprendizaje léxico. No se midieron todas como cambios aislados. | Priorizar por hipótesis y baseline; no agrupar tokenizadores ni retirar protecciones de substrings por intuición. |

## Puerta metodológica para cualquier candidato futuro

Este documento no propone un diff. Si se selecciona un frente para intervención, presentar antes de decidir:

1. **Baseline actual:** código y hashes fijados, fixture/base sintética reconstruida y validada, cada consulta sobre copia aislada, fuentes verificadas antes/después.
2. **Diff mínimo aislado:** una sola causa/variable por candidato, aplicado solo a copia temporal; incluir también la medición sin cambio. No aplicar a motor ni a bases originales.
3. **Resultados emparejados:** R@1, R@5, MRR y falsos positivos por tipo/idioma; listado privado por caso; y medición de **pistas** (vecinos, asociaciones, orden, scores y contexto) para detectar qué se gana o pierde. Una lista vacía tras error no cuenta como abstención correcta.
4. **Etiquetas separadas:** mantener por separado marcadores de prueba, etiquetas gold y `sustantivos_clave` plegados/exactos. No fusionar ni adjudicar de forma automática.
5. **Revisión antes de avanzar:** presentar diff y evidencia para revisión. Sin autorización, no se modifica el motor; E4 queda fuera de esta etapa.

## Evidencia relacionada

- `docs/e3a_investigacion_multilingue_20261027.md` — línea base e inventario de rutas lingüísticas.
- `docs/e3_cjk_controles_sinteticos_20261101.md` — controles CJK y regresiones del arnés.
- `docs/e3_investigacion_fp_ingles_y_etiquetas_pendientes_20261102.md` — dos negativos ingleses y 14 marcadores de prueba, con resultados sanitizados.
- `scripts/diagnosticar_reemplazo_vs_acumulacion_etiquetas_sinteticas_e3.py` — sondeo reproducible solo sintético de dos políticas.
- `scripts/diagnosticar_rutas_mcp_historial_pistas_vecinos_e3.py` — sondeo previo de funciones registradas directamente, no stdio.
- `scripts/diagnosticar_mcp_stdio_apertura_orden_etiquetas_e3.py` — protocolo MCP stdio real, copias sintéticas, apertura DMN y dos órdenes de consultas.
- `scripts/qa_stdio_server_intuicion.py` — launcher stdio aislado con guardrail de ruta temporal y sin daemon global.
- `docs/e3_cambio2_investigacion_sustantivos_20261029.md` y `docs/e3_cambio2_resultados_20261029.md` — historial separado del almacenamiento exacto/plegado; deben leerse junto con el código actual.
- `docs/e3_unicode_identidad_investigacion_20261028.md` — sondas de normalización en copias, sin decisión nueva en este inventario.

**Resultado de esta entrega:** aclaración documental de límites y trabajos abiertos. No se presenta ni se aplica una mejora al motor.
