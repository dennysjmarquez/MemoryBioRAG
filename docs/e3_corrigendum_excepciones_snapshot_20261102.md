# Fe de erratas E3: excepciones y alcance del snapshot

**Fecha:** 2026-11-02. Corrige el registro descriptivo de la matriz sintética de creación/densidad de `docs/e3_rutas_creacion_densidad_sinteticas_20261102.md`; no sustituye ni vuelve a ejecutar esa medición.

## Registro de excepciones y estados

Se auditó el reporte privado `e3_rutas_creacion_densidad_20261102_run02/stdio_cases_full.json`; su hash SHA-256 es `442bb6e776cc5474120b5d199b6bf42b97964e85aaa76c4736e1b46b4a65bffd`. Los hashes de la corrida de origen se verificaron antes de producir esta fe de erratas. El registro corregido es:

| Medida | Conteo |
|---|---:|
| Brazos completos / válidos | 48 / 48 |
| Excepciones Python capturadas | 0 |
| Flags MCP `isError` | 0 |
| Respuestas de herramienta con `status=error` | 0 |
| Respuestas con `status=exception` o `exception_type` | 0 |
| Errores de consulta del snapshot de grafo | 0 |
| Errores de lectura de almacenamiento | 0 |

Se realizaron 336 llamadas MCP. **96** respuestas de `recordar` (las dos por brazo) no traían un campo `status` crudo; no tenían flag ni detalle de error y el arnés las normalizó como `ok`. La ausencia de ese campo no es una excepción. En el JSON de origen también hay 48 objetos `after_initialize` sin `status`, pero son snapshots de grafo, no llamadas MCP; no deben sumarse al conteo de estados de herramientas. Esta separación se registra en el arnés actualizado.

## Descripción correcta del snapshot

Los 432 snapshots contienen filas completas de estas **nueve tablas**:

- `sinapsis`
- `sinapsis_latentes`
- `sinapsis_cuarentena`
- `largo_plazo_dimensiones`
- `grupos_semanticos`
- `nodo_grupos_semanticos`
- `concept_hubs`
- `concept_hub_nodes`
- `concept_hub_bridges`

Además guardan una sola proyección de columnas: `largo_plazo(concepto, asociaciones)`. **No son una copia completa de SQLite** ni una captura completa de `largo_plazo` o `corto_plazo`.

El reporte original conserva sus bytes y hash. Su campo descriptivo `graph_snapshot_scope.full_row_tables` enumeraba diez claves de salida del snapshot; esos nombres incluyen alias de consulta y la clave de la proyección, no diez tablas físicas. Esta fe de erratas corrige la clasificación, no las filas medidas ni sus hashes. El metadata de corrección separa `full_row_tables`, `row_projections` y `complete_sqlite_database_snapshot: false`; el reporte fuente permanece intacto.

## Trazabilidad y alcance

El detalle por corrida de la corrección se conserva en `.private_evidence/e3_corrigendum_excepciones_snapshot_20261102_run01/`, con hashes; la evidencia fuente continúa intacta en su directorio `run02`. No se publicó contenido de consultas, pistas, payloads ni trazas por caso.

El runner `scripts/diagnosticar_rutas_creacion_densidad_e3.py` ahora cuenta por separado excepciones Python, estados de error y omisiones del campo `status`; también identifica las nueve tablas físicas y la proyección. Una respuesta MCP que reporte `status=exception` ya no se considera un brazo válido. Estos cambios son solo del arnés y la documentación: **no se modificó el motor, no se eligió política de etiquetas y E4 sigue en espera**.
