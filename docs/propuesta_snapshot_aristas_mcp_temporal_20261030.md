# Propuesta: snapshots de aristas antes y después de cada llamada MCP

**Fecha:** 2026-10-30

**Estado:** propuesta; no ejecutada.

**Propósito:** observar cambios de aristas en una DB sintética temporal, manteniendo el transporte MCP real y sin instrumentar ni modificar el motor.

## Alcance y guardas

- DB SQLite nueva, vacía y ubicada bajo una raíz temporal nueva. Resolver ambas rutas y abortar antes de iniciar MCP si `BIORAG_PATH` no es descendiente de `BIORAG_QA_TEMP_ROOT`.
- Solo recuerdos sintéticos. No abrir, copiar, consultar ni modificar DB viva o snapshots.
- Todas las operaciones de la secuencia (`recordar` previo, `aprender`, `consolidar`, `vincular`, `recordar` final) pasan por la sesión real MCP `stdio`, usando `MCPProcess` y `parse_tool_result` del arnés. No llamar funciones internas para simular tools.
- El observador se limita a conexiones SQLite `mode=ro` a la DB temporal entre llamadas; no ejecuta escrituras SQL, triggers, ni altera configuración del servidor.
- No cambiar motor, ranking o fixture de la QA completa. No ejecutar esta propuesta ni la QA completa ahora; los umbrales siguen pendientes.

## Secuencia y puntos de captura

Cada llamada se ejecuta como una unidad registrada. Capturar un snapshot antes de invocarla, llamar a la tool MCP, esperar su respuesta o excepción, y capturar otro snapshot inmediatamente después. La siguiente secuencia mantiene la búsqueda previa exigida antes de cada aprendizaje:

| Secuencia | Llamada MCP | Resultado del snapshot posterior |
|---:|---|---|
| 1 | `recordar` — búsqueda previa del recuerdo 1 | Comparar con estado vacío/inicial |
| 2 | `aprender` — recuerdo 1 | Aislar cambios durante esta llamada |
| 3–4 | Repetir búsqueda previa y `aprender` para recuerdo 2 | Un diff por llamada |
| 5–6 | Repetir para recuerdo 3 | Un diff por llamada |
| 7–8 | Repetir para recuerdo 4 | Un diff por llamada |
| 9 | `consolidar` | Capturar en conjunto las aristas que aparecen/cambian durante esta tool |
| 10 | `vincular` objetivo↔asociación útil | Distinguir enlace ya existente de filas insertadas |
| 11 | `vincular` objetivo↔asociación serendípica útil | Distinguir enlace ya existente de filas insertadas |
| 12 | `recordar` final, con asociaciones y contexto solicitados | Detectar cambios asociados a esta llamada si los hubiera |

Si el servidor crea el archivo o el esquema al iniciar o en la primera tool, el snapshot inicial se registra como `db_ausente`/sin filas, sin crear manualmente la base ni tablas. Después de cada error MCP o de transporte se toma igualmente el snapshot posterior, para no perder evidencia de cambios parciales.

## Contenido de cada snapshot

Desde la DB temporal, abrir SQLite con `mode=ro` y obtener todas las filas de `sinapsis`, sin límites ni orden dependiente de la tabla. Por cada fila preservar:

```json
{
  "origen": "concepto_a",
  "destino": "concepto_b",
  "tipo": "co_nombre",
  "peso": 0.53,
  "creado_en": 1793059200.0,
  "ultimo_uso": null
}
```

Guardar también un identificador/hash del snapshot, la llamada que lo precede o sigue, ruta temporal resuelta, existencia de DB/tabla y resultado de `PRAGMA integrity_check` sobre esa DB sintética. El orden canónico de serialización sirve para hashes reproducibles; no se usa para alterar ni deduplicar las filas.

## Clasificación exacta del diff

La clave de fila es dirigida: `(origen, destino)`. Comparar cada dirección por separado y sus atributos `tipo`, `peso`, `creado_en` y `ultimo_uso`:

- **`fila_nueva_direccion`:** clave ausente antes y presente después; guardar el registro posterior completo.
- **`fila_existente_sin_cambio`:** clave presente en ambos snapshots con atributos iguales.
- **`fila_existente_actualizada`:** clave presente en ambos con cambios; guardar valores anteriores, posteriores y campos distintos. No contarla como enlace nuevo.
- **`fila_eliminada`:** clave presente antes y ausente después.

Además, agrupar sin pérdida por pareja no dirigida `(min(origen,destino), max(origen,destino))` para resumir si la pareja ya existía en cualquiera de sus direcciones. No reemplazar el detalle dirigido por esa pareja agrupada.

Interpretación específica de `vincular`:

- Si ambas direcciones ya existían como automáticas y permanecen iguales, registrar `pareja_preexistente_sin_cambio`; una respuesta `status=ok` no significa que se haya creado una arista manual.
- Si solo faltaba la dirección inversa y aparece como `manual`, registrar esa fila como nueva y conservar el tipo/peso original de la otra dirección.
- Si ambas filas aparecen nuevas, registrar ambas direcciones y sus tipos observados.
- No inferir causalidad a partir del nombre del tipo ni del éxito MCP: el diff prueba el intervalo de llamada y el estado final de las filas, no el subpaso interno que las escribió.

## Registro MCP y paquete de auditoría

Para cada llamada, guardar de forma append-only en el JSON de resultado: número secuencial, nombre de tool, argumentos sintéticos, snapshot previo, respuesta MCP cruda, objeto parseado por `parse_tool_result`, indicador `isError`, excepción/traceback si ocurre, snapshot posterior y diff. Adjuntar la extracción de canales con los helpers del arnés cuando la llamada sea `recordar`, sin mezclar esos campos con el diff de grafo.

Guardar aparte un resumen Markdown con cantidad de llamadas, errores, integridad final, número de filas nuevas/actualizadas/eliminadas por llamada y observaciones sin umbrales. Eliminar la DB temporal solo después de escribir y validar los artefactos de auditoría.

## Límite de atribución

Un snapshot antes/después de `consolidar` localiza cambios en el intervalo MCP `consolidar`, pero esa tool procesa varios nodos y fases internas antes de responder. Sin instrumentación adicional —que queda fuera de esta propuesta— no se afirmará qué nodo o subfunción interna creó cada fila. Si el tipo aparece como `co_nombre`, el reporte dirá únicamente que la fila quedó con ese tipo al terminar la llamada observada; no afirmará cuándo ni por qué se originó.

Para comparar específicamente prefijos, una extensión futura podría usar dos DB temporales independientes, contenidos y parámetros idénticos y nombres sintéticos que difieran solo en tener/no tener el prefijo. Los snapshots y diffs se aplicarían igual en ambos brazos. Esa comparación también queda pendiente de aprobación y no se ejecuta ahora.
