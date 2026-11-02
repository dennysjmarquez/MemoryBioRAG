# E3 — inventario de trabajo restante y separación de etiquetas

**02 nov 2026 · inventario, sin propuesta de cambio de motor.** No se aplican parches, no se hacen migraciones ni fusiones de datos y no se avanza a E4. Los detalles por consulta, etiquetas gold y crosswalk permanecen fuera de este documento.

## Distinción obligatoria de alcance

Hay dos objetos distintos que no se deben mezclar:

1. **Marcadores de la QA de prueba:** los 14 casos MCP llamados `pendiente hueco 1` son estados de llamadas de prueba que se rechazaron antes de abrir la base. Son 14 casos sin búsqueda ejecutada; no son etiquetas de memoria ni candidatas a fusionarse. Siguen intactos.
2. **Fusión/uso de etiquetas de memoria:** `sustantivos_clave` es metadato de recuerdos. El campo plegado histórico puede colapsar distinciones; existe además `sustantivos_clave_exactos` para conservar la forma NFC. La transferencia de corto a largo plazo trata las dos columnas para el mismo concepto, pero la consulta MCP reduce la entrada a la forma plegada y FTS indexa la columna plegada. La columna exacta no aparece en el `MATCH` de búsqueda. El esquema no retrorellena las filas antiguas. Por tanto, «integrar/fusionar etiquetas» es una cuestión de representación, consulta e historia de datos; no una operación sobre los 14 casos de prueba, ni permiso para fusionar etiquetas entre recuerdos distintos.

El código actual refleja esa separación: el escritor y la consolidación preservan el campo exacto; la ruta de búsqueda sigue consumiendo el plegado. Los documentos históricos de E3 Cambio 2 describen etapas distintas de su propuesta y resultado; para este inventario prevalece el código de `HEAD`, no una frase histórica aislada.

## Matriz de estado

| Frente E3 | Estado comprobado | Trabajo restante, sin decisión de implementación |
|---|---|---|
| CJK: OR trigramas y umbral 2 | Línea base y arnés corregido medidos en fixture; pruebas sintéticas de lista de vecinos >5 y error FTS registrado completadas. Ambos parches continúan **NO APLICAR**. | Mantener `を指す` como pista diagnóstica, nunca filtro. Revisar evidencia/diff antes de considerar cualquier cambio. |
| Falsos positivos ingleses | Investigación aislada completada: los dos negativos sintéticos tienen causas distintas (substring literal frente a substring de una expansión WordNet). No es una tasa general; no se cambió el filtro ni WordNet. | Ninguna regla de filtrado se deriva automáticamente. Si se evalúa una alternativa, medir recall y falsos positivos, además de las pistas recuperadas. |
| Marcadores de prueba `pendiente hueco 1` | 14/14 solicitudes MCP rechazadas antes de búsqueda; en baseline directo actual 7/14 esperados en top 5, siete sin resultados. No se cambiaron marcadores. | Conservar como estado de prueba. No fusionarlos con `sustantivos_clave` ni tratarlos como etiqueta gold adjudicada. |
| Etiquetas exactas y plegadas de recuerdos | Escritura/consolidación dispone de dos columnas. La búsqueda MCP pliega el término y usa FTS sobre el campo plegado; filas históricas exactas pueden ser `NULL`. | Es el frente distinto de «fusión de etiquetas» que requiere decisión. No hay aquí propuesta de backfill, alias, fusión entre recuerdos ni cambio del índice. |
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
- `docs/e3_cambio2_investigacion_sustantivos_20261029.md` y `docs/e3_cambio2_resultados_20261029.md` — historial separado del almacenamiento exacto/plegado; deben leerse junto con el código actual.
- `docs/e3_unicode_identidad_investigacion_20261028.md` — sondas de normalización en copias, sin decisión nueva en este inventario.

**Resultado de esta entrega:** aclaración documental de límites y trabajos abiertos. No se presenta ni se aplica una mejora al motor.
