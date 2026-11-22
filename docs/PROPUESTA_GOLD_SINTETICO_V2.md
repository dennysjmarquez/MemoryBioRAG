# Propuesta publicada: gold sintético v2 para smoke test

## Decisión de versión

Se publica un archivo nuevo, [`synthetic_gold_v2.jsonl`](versiones_gold_sintetico/synthetic_gold_v2.jsonl), separado del gold sintético v1 y de la evidencia de su auditoría. v2 no revisa ni reemplaza el gold original. Su manifiesto identifica como versión sintética precedente a v1 y registra el SHA-256 de ese archivo: `88c55d48a393fbc421caa455b08d92dd5c083c5e4167e31cfc229fb52397a316`.

La evidencia y resultados v1 permanecen intactos en `docs/auditoria_preparaciones_sinteticas_mcp_2026-10-30/evidencia/`; el resumen de esas dos preparaciones está en `pair_summary.json`. No se sobrescribe ninguno de esos artefactos.

## Motivo y contenido de v2

La auditoría v1 observó una conexión directa `synthetic_amber–synthetic_ivory`, además de la ruta declarada `synthetic_amber → synthetic_cobalt → synthetic_ivory`. Por eso la distancia mínima real era uno y la ruta no era única. v2 omite `ruta_2_saltos`: no reclama una ruta de dos saltos ni unicidad.

Se conservan los tres nodos, los contenidos, las dos parejas que v1 ya declaraba en `aristas_gold`, y la consulta `cobalt azure` cuyo objetivo principal es `synthetic_cobalt`. `aristas_gold` es una lista de expectativas explícitas, no una lista exhaustiva del grafo. Ninguna conexión observada se elimina, filtra ni modifica; en una futura preparación, la conexión directa adicional debe continuar siendo visible.

Para esa consulta, `relacionados_utiles` y `ruido_tonto` se dejan como `[]` **no adjudicadas**. Esto significa que v2 no aporta etiqueta evaluativa para esas categorías; no significa que se haya demostrado ausencia de pistas, de asociaciones útiles o de ruido. No deben presentarse métricas de esas dos categorías como evaluación en v2. Tampoco se etiqueta una asociación como ruido por tipo, peso o por no ser el objetivo literal.

## Cobertura prevista, si se autoriza después

El archivo está planteado para un smoke test que pueda comprobar lectura/validación del gold, llamadas MCP, nodos activos, presencia de las parejas explícitas y el objetivo principal de recuperación. La auditoría debe seguir reportando el grafo completo observado, incluidos enlaces no enumerados en `aristas_gold`.

v2 **no** probaría recuperación a dos saltos, unicidad de rutas ni una ruta con pista; tampoco evalúa categorías útiles/ruido mientras sus etiquetas sean no adjudicadas. No convierte las dos preparaciones de v1 en mediciones aprobadas.

## Estado y límites de autorización

Solo se versionó/publicó el gold sintético y esta propuesta. No se prepararon fixtures nuevas, no se ejecutaron brazos de medición ni QA completa, no se tocaron conexiones y no se aprobó ningún hash para medición. W sigue pendiente.

### Artefactos y hashes

- Gold sintético v2: `5d83616a63be7c73bbea8bb90452091316d7e238835013440a6fd939c13d16d8`
- Manifiesto v1 citado como versión sintética previa: `88c55d48a393fbc421caa455b08d92dd5c083c5e4167e31cfc229fb52397a316`
- Archivo de linaje y alcance: [`synthetic_gold_v2_manifest.json`](versiones_gold_sintetico/synthetic_gold_v2_manifest.json)
- `SHA256SUMS` en este directorio verifica los artefactos v2 publicados.
