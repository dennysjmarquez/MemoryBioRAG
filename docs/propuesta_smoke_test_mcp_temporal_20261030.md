# Propuesta: smoke test MCP real en DB temporal sintética

**Fecha:** 2026-10-30  
**Estado:** propuesta pendiente de aprobación de Dennys  
**Alcance:** validación funcional mínima de `aprender → consolidar → vincular → recordar` y de la separación de canales de salida. No es una evaluación de calidad de recuperación.

## 1. Objetivo

Comprobar, mediante una sesión MCP real por `stdio`, que unos pocos recuerdos sintéticos pueden escribirse, consolidarse, vincularse y recuperarse desde una base SQLite temporal aislada; y que la respuesta de `recordar` mantiene sus canales observables separados, en vez de confundir resultados principales con asociaciones/contexto.

## 2. Fuera de alcance y límites

- No ejecutar esta propuesta ni la QA completa sin aprobación explícita de Dennys.
- No abrir, copiar, consultar ni modificar la DB viva o snapshots; no importar datos reales.
- No cambiar motor, ranking, FTS, triggers, `MATCH`, BM25, backfill, ni lógica de asociaciones.
- No medir éxito, calidad, orden, score, recall, precisión ni establecer umbrales. Los umbrales quedan pendientes.
- No atribuir recorridos de dos saltos. La prueba usa solo vínculos directos y no afirma rutas efectivamente recorridas.
- No fusionar sustantivos entre recuerdos. Mantener contenido y `sustantivos_clave` específicos por nodo.

## 3. Aislamiento y transporte

La futura ejecución deberá:

1. Crear un directorio temporal nuevo y una ruta de DB inexistente dentro de él; definir `BIORAG_PATH` apuntando a esa DB y `BIORAG_QA_TEMP_ROOT` al directorio temporal.
2. Usar el launcher `scripts/qa_stdio_server_intuicion.py` y el cliente MCP stdio real (como referencia de transporte, `MCPProcess` en `scripts/evaluar_qa_intuicion_asociaciones_e1.py`). Las llamadas a `aprender`, `consolidar`, `vincular` y `recordar` deberán pasar por `ClientSession.call_tool`; no invocar implementaciones internas ni helpers que simulen MCP.
3. Confirmar que la DB está bajo la raíz temporal antes de abrir el cliente. Si falla esa guarda, detenerse sin iniciar el servidor.
4. Verificar antes de la ejecución que el entorno elegido tiene las dependencias MCP requeridas. En el entorno revisado durante la preparación, `mcp` no estaba disponible; si sigue ausente, detenerse y pedir aprobación para preparar un entorno compatible. No usar un fallback simulado.
5. Usar nombres con prefijo único de smoke test y eliminar el temporal solo tras finalizar y guardar el resumen mínimo, nunca apuntar a una ruta preexistente.

## 4. Fixture sintética propuesta

Cuatro recuerdos nuevos, autocontenidos y sin datos personales:

| Concepto de prueba | Rol | Contenido sintético resumido |
|---|---|---|
| `smoke_mcp_reintento_objetivo` | Objetivo | Un cliente de prueba repite una solicitud tras recibir una respuesta temporal `503`. |
| `smoke_mcp_reintento_idempotencia` | Asociación directamente útil | Una clave de idempotencia evita que el reintento cree una operación duplicada. |
| `smoke_mcp_reintento_backoff` | Asociación serendípica útil | El backoff exponencial reduce la presión sobre un servicio durante errores temporales. |
| `smoke_mcp_color_favorito` | Ruido sin valor para la consulta | Un personaje ficticio prefiere el color verde; no tiene relación con reintentos ni servicios. |

Los textos completos, `sustantivos_clave`, categoría, `syn` si se requiere y los cinco `bridges` por recuerdo se fijarán antes de ejecutar, de acuerdo con el esquema MCP vigente. Los `bridges` tendrán cinco ángulos válidos y no repetirán simplemente el nombre o el contenido. Cada llamada `aprender` incluirá `busqueda_previa=True`; cualquier cambio de contrato o validación fallida detendrá el smoke test en vez de omitir guardas.

## 5. Secuencia propuesta de llamadas MCP

1. Abrir una sesión real `stdio` contra la DB temporal nueva.
2. Llamar `aprender` una vez por cada uno de los cuatro conceptos sintéticos y verificar que cada respuesta MCP confirme `status=ok` y el concepto esperado. Ante error, detener la secuencia; no reintentar con llamadas internas.
3. Llamar `consolidar` una vez y verificar `status=ok`.
4. Llamar `vincular` para los dos vínculos directos:
   - `smoke_mcp_reintento_objetivo` ↔ `smoke_mcp_reintento_idempotencia`
   - `smoke_mcp_reintento_objetivo` ↔ `smoke_mcp_reintento_backoff`

   Verificar `status=ok` en ambas respuestas. No crear vínculo con `smoke_mcp_color_favorito`.
5. Llamar `recordar` con una consulta sintética sobre reintentar una solicitud `503` sin duplicar la operación, usando `asociados=True` y `context_window=1`. No depender del orden ni de scores; leer y verificar los campos por separado.
6. Cerrar la sesión MCP y hacer una comprobación de integridad únicamente sobre la DB temporal. No hacer lecturas SQL de ninguna otra base.

## 6. Comprobaciones observables de canales

La comprobación es de contrato y pertenencia, no de ranking:

- La respuesta MCP parsea y expone separadamente `resultados`, `asociaciones_enriquecidas` (o el campo `asociaciones` del resultado, según la respuesta real) y `contexto_expandido`.
- El objetivo sintético se busca en el canal de resultados principales; la asociación útil y la asociación serendípica se inspeccionan en sus campos de asociación/contexto cuando la respuesta los incluya.
- Registrar para cada concepto en qué campo apareció. No aplanar previamente la respuesta ni tratar la unión de canales como si fuera el canal principal.
- El recuerdo del color no debe aparecer como un vínculo introducido artificialmente por la prueba. Si aparece en un canal, registrarlo como observación; no cambiar pesos, umbrales o configuración para forzar un resultado.
- No exigir que una pista quede fuera de `resultados`, ni inferir de una aparición en contexto que hubo una expansión de dos saltos. No hay un requisito de separación mutuamente excluyente entre canales; se comprueba que la estructura los expone aparte.
- Si MCP no expone alguno de los campos previstos, documentar la forma real de la respuesta y marcar esa comprobación como no disponible, sin atribuir éxito a un canal ausente.

## 7. Criterio de cierre del smoke test

El reporte posterior —solo tras autorización— contendrá el estado de cada llamada MCP, los nombres sintéticos observados por campo, la integridad de la DB temporal y cualquier error o campo ausente. El smoke se considerará funcional únicamente si las cuatro etapas completan por MCP real y las respuestas permiten inspeccionar los canales separados. Esto no representa aprobación semántica, validación de ranking ni cumplimiento de umbrales.

**Decisión solicitada:** aprobación explícita de Dennys para preparar el entorno MCP compatible y ejecutar este smoke test limitado. Hasta recibirla, no se ejecutarán llamadas MCP, el smoke test ni la QA completa.
