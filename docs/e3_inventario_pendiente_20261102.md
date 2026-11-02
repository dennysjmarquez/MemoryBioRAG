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

En todos los casos donde se recuperó el objetivo, los dos vecinos sintéticos aparecieron tanto en asociaciones enriquecidas como en contexto expandido. Las escrituras de etiquetas conservaron las aristas en todas las copias; no se borraron vecinos ni recuerdos. Los casos simulados muestran que reemplazar una pista de etiqueta no equivale a borrar el historial del contenido, y que la recuperación textual puede seguir exponiendo una contradicción. No se asignó verdad a datos reales ni se aplicó un filtro manual. La ausencia de etiquetas viejas en la rama de reemplazo es solo una observación de esa ruta en la copia; no es una decisión de descartarlas. No se elige una política.

## Matriz de estado

| Frente E3 | Estado comprobado | Trabajo restante, sin decisión de implementación |
|---|---|---|
| CJK: OR trigramas y umbral 2 | Línea base y arnés corregido medidos en fixture; pruebas sintéticas de lista de vecinos >5 y error FTS registrado completadas. Ambos parches continúan **NO APLICAR**. | Mantener `を指す` como pista diagnóstica, nunca filtro. Revisar evidencia/diff antes de considerar cualquier cambio. |
| Falsos positivos ingleses | Investigación aislada completada: los dos negativos sintéticos tienen causas distintas (substring literal frente a substring de una expansión WordNet). No es una tasa general; no se cambió el filtro ni WordNet. | Ninguna regla de filtrado se deriva automáticamente. Si se evalúa una alternativa, medir recall y falsos positivos, además de las pistas recuperadas. |
| Marcadores de prueba `pendiente hueco 1` | 14/14 solicitudes MCP rechazadas antes de búsqueda; en baseline directo actual 7/14 esperados en top 5, siete sin resultados. No se cambiaron marcadores. | Conservar como estado de prueba. No fusionarlos con `sustantivos_clave` ni tratarlos como etiqueta gold adjudicada. |
| Etiquetas exactas y plegadas de recuerdos | Escritura/consolidación dispone de dos columnas. La búsqueda MCP pliega el término y usa FTS sobre el campo plegado; filas históricas exactas pueden ser `NULL`. El sondeo sintético reemplazo/acumulación quedó medido en las dos copias. | Es el frente distinto de «fusión de etiquetas» que requiere decisión. No hay aquí propuesta de backfill, alias, fusión entre recuerdos ni cambio del índice. La medición no adjudica qué facetas son vigentes. |
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
- `scripts/diagnosticar_rutas_mcp_historial_pistas_vecinos_e3.py` — rutas MCP de escritura/lectura, pistas históricas y dos vecinos en copias temporales.
- `docs/e3_cambio2_investigacion_sustantivos_20261029.md` y `docs/e3_cambio2_resultados_20261029.md` — historial separado del almacenamiento exacto/plegado; deben leerse junto con el código actual.
- `docs/e3_unicode_identidad_investigacion_20261028.md` — sondas de normalización en copias, sin decisión nueva en este inventario.

**Resultado de esta entrega:** aclaración documental de límites y trabajos abiertos. No se presenta ni se aplica una mejora al motor.
