# Resultado: snapshots de aristas MCP en DB temporal

**Fecha:** 2026-10-30

**Estado:** completado; sin errores MCP ni de transporte.

**Autorización:** Dennys autorizó la ejecución de la propuesta de commit `c7c1984`.

## Método y guardas

- Se usó MCP real por `stdio` con `MCPProcess` y el launcher `scripts/qa_stdio_server_intuicion.py`; las respuestas se extrajeron con `parse_tool_result` del arnés.
- Se capturaron snapshots SQLite de solo lectura inmediatamente antes y después de **cada llamada MCP**. Las filas conservan `origen`, `destino`, `tipo`, `peso`, `creado_en` y `ultimo_uso`; los diffs comparan la clave dirigida `(origen, destino)`.
- Cuatro recuerdos sintéticos, cuatro búsquedas previas reales antes de `aprender`, un `consolidar`, dos `vincular` y un `recordar` final: **12 llamadas**.
- Todas las llamadas `recordar` usaron `deep=False` y `forzar_rafaga=False`; no se pasó `rafaga_palabras`.
- La DB fue nueva, bajo una raíz temporal aislada; su integridad final fue `ok`. Se eliminó tras guardar la evidencia. No se accedió a la DB viva ni al snapshot original.
- Código observado: commit `c7c1984d12bbd4c90ae49a186e09481a168f3fc1`, rama `arena/9a54babb-memorybiorag`.

## Cambios por llamada

| # | Tool/fase | Filas dirigidas nuevas | Filas existentes sin cambio | Actualizadas/eliminadas |
|---:|---|---:|---:|---:|
| 1 | `recordar` — búsqueda previa 1 | 0 | 0 | 0 |
| 2 | `aprender` 1 | 0 | 0 | 0 |
| 3 | `recordar` — búsqueda previa 2 | 0 | 0 | 0 |
| 4 | `aprender` 2 | 0 | 0 | 0 |
| 5 | `recordar` — búsqueda previa 3 | 0 | 0 | 0 |
| 6 | `aprender` 3 | 0 | 0 | 0 |
| 7 | `recordar` — búsqueda previa 4 | 0 | 0 | 0 |
| 8 | `aprender` 4 | 0 | 0 | 0 |
| 9 | `consolidar` | **12** | 0 | 0 |
| 10 | `vincular` objetivo↔idempotencia | 0 | **12** | 0 |
| 11 | `vincular` objetivo↔backoff | 0 | **12** | 0 |
| 12 | `recordar` final | 0 | **12** | 0 |

Las cuatro búsquedas previas devolvieron `total=0`; los cuatro aprendizajes, `consolidar` y los dos `vincular` respondieron `status=ok`. No hubo excepciones ni errores MCP registrados.

## Filas dirigidas al terminar `consolidar`

Las doce filas aparecieron en el intervalo observado de la llamada MCP `consolidar`. La tabla presenta exactamente dirección, tipo y peso:

| Origen | Destino | Tipo | Peso |
|---|---|---|---:|
| `smoke_mcp_color_favorito` | `smoke_mcp_reintento_backoff` | `co_nombre` | 0.53 |
| `smoke_mcp_color_favorito` | `smoke_mcp_reintento_idempotencia` | `co_nombre` | 0.53 |
| `smoke_mcp_color_favorito` | `smoke_mcp_reintento_objetivo` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_backoff` | `smoke_mcp_color_favorito` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_backoff` | `smoke_mcp_reintento_idempotencia` | `co_nombre` | 0.77 |
| `smoke_mcp_reintento_backoff` | `smoke_mcp_reintento_objetivo` | `co_nombre` | 0.77 |
| `smoke_mcp_reintento_idempotencia` | `smoke_mcp_color_favorito` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_idempotencia` | `smoke_mcp_reintento_backoff` | `co_nombre` | 0.87 |
| `smoke_mcp_reintento_idempotencia` | `smoke_mcp_reintento_objetivo` | `co_nombre` | 0.77 |
| `smoke_mcp_reintento_objetivo` | `smoke_mcp_color_favorito` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_objetivo` | `smoke_mcp_reintento_backoff` | `co_nombre` | 0.87 |
| `smoke_mcp_reintento_objetivo` | `smoke_mcp_reintento_idempotencia` | `co_nombre` | 0.87 |

## Lectura acotada del resultado

En los snapshots anteriores a `consolidar` no había filas sinápticas. Las doce filas dirigidas (seis parejas no dirigidas) se observaron por primera vez inmediatamente después de esa llamada completa; todas tenían tipo `co_nombre` en ese snapshot. No se atribuye su nacimiento a una subfunción, nodo o mecanismo interno de `consolidar`.

Las dos parejas que después se pasaron a `vincular` ya tenían ambas direcciones antes de esas llamadas. `vincular` devolvió éxito, pero los snapshots no mostraron filas nuevas ni cambios de tipo o peso: permanecieron las filas automáticas existentes. `recordar` final tampoco produjo cambios de aristas.

Esto documenta lo ocurrido en esta DB sintética y esta ejecución; no evalúa ranking, umbrales ni la QA completa.

## Evidencia completa

`docs/resultados_snapshots_aristas_mcp_temporal_20261030.json` contiene, por llamada, argumentos, respuesta MCP cruda y parseada, snapshot previo y posterior completo, diffs dirigidos, errores, hashes e integridad. La base temporal se eliminó tras escribirlo.

No se modificó motor ni ranking. No se ejecutó la QA completa; sus umbrales siguen pendientes.
